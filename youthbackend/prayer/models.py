from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class PrayerRequest(TimeStampedModel):
    class Visibility(models.TextChoices):
        PUBLIC = 'PUBLIC', 'Public prayer wall'
        LEADERS_ONLY = 'LEADERS_ONLY', 'Leaders only'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending moderation'
        APPROVED = 'APPROVED', 'Approved'
        HIDDEN = 'HIDDEN', 'Hidden'
        ESCALATED = 'ESCALATED', 'Escalated'

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prayer_requests')
    body = models.TextField()
    category = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=150, blank=True)
    visibility = models.CharField(max_length=15, choices=Visibility.choices, default=Visibility.LEADERS_ONLY)
    # Hides the author from every API response, including to Leaders/Pastors -
    # the DB record still keeps the real author for safeguarding traceability.
    is_anonymous = models.BooleanField(default=False)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)

    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Prayer request from {self.author} ({self.status})'

    def save(self, *args, **kwargs):
        if self._state.adding:
            # Leaders-only requests are already restricted enough that they
            # don't need a moderation gate before staff can see them; only
            # the public wall requires approval first.
            if self.visibility == self.Visibility.LEADERS_ONLY and self.status == self.Status.PENDING:
                self.status = self.Status.APPROVED
        super().save(*args, **kwargs)


class PrayerSupport(TimeStampedModel):
    """One 'I prayed' tap per person per request - a through model instead
    of a denormalised counter so repeat taps can't inflate the count."""

    prayer_request = models.ForeignKey(PrayerRequest, on_delete=models.CASCADE, related_name='supporters')
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['prayer_request', 'person'], name='unique_prayer_support'),
        ]
