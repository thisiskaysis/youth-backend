from datetime import time

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from .catalog import CATEGORY_DEFAULTS, Category, NotificationType


class NotificationPreference(TimeStampedModel):
    """One row per person. Master toggles gate everything; per-category
    overrides layer on top of CATEGORY_DEFAULTS."""

    person = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preference'
    )
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)

    quiet_hours_enabled = models.BooleanField(default=True)
    quiet_hours_start = models.TimeField(default=time(21, 30))
    quiet_hours_end = models.TimeField(default=time(7, 0))

    # e.g. {"RIDES": {"push": false}} - only the keys a person has changed
    # from the launch default need to be present.
    category_overrides = models.JSONField(default=dict, blank=True)

    def channels_for(self, category):
        defaults = CATEGORY_DEFAULTS.get(category, {'push': True, 'email': False})
        override = self.category_overrides.get(category, {})
        return {
            'push': self.push_enabled and override.get('push', defaults['push']),
            'email': self.email_enabled and override.get('email', defaults['email']),
        }

    def is_quiet_now(self, at=None):
        if not self.quiet_hours_enabled:
            return False
        current = timezone.localtime(at or timezone.now()).time()
        start, end = self.quiet_hours_start, self.quiet_hours_end
        if start <= end:
            return start <= current < end
        return current >= start or current < end  # window wraps past midnight

    def __str__(self):
        return f'Notification preferences for {self.person}'


class DeviceToken(TimeStampedModel):
    class Platform(models.TextChoices):
        IOS = 'IOS', 'iOS'
        ANDROID = 'ANDROID', 'Android'

    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.person} ({self.platform})'


class Notification(TimeStampedModel):
    """One row per recipient/channel delivery attempt - doubles as the
    in-app notification history/inbox."""

    class Channel(models.TextChoices):
        PUSH = 'PUSH', 'Push'
        EMAIL = 'EMAIL', 'Email'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'
        SKIPPED = 'SKIPPED', 'Skipped'

    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    category = models.CharField(max_length=30, choices=Category.choices)
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    channel = models.CharField(max_length=10, choices=Channel.choices)

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    deep_link_type = models.CharField(max_length=50, blank=True)
    deep_link_id = models.CharField(max_length=64, blank=True)
    data = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    scheduled_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-scheduled_at']
        indexes = [
            models.Index(fields=['person', 'read_at']),
            models.Index(fields=['status', 'scheduled_at']),
        ]

    def __str__(self):
        return f'{self.notification_type} -> {self.person} ({self.channel})'
