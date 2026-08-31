from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from groups.audience import AudienceTargetMixin


class NavigationItem(TimeStampedModel, AudienceTargetMixin):
    """A custom menu item added on top of the app's built-in navigation -
    this model only represents the dynamic/custom layer, never the
    hard-coded core tabs the frontend ships with."""

    class DestinationType(models.TextChoices):
        INTERNAL_SCREEN = 'INTERNAL_SCREEN', 'Internal app screen'
        EXTERNAL_URL = 'EXTERNAL_URL', 'External URL'
        EVENT = 'EVENT', 'Event'
        CONTENT = 'CONTENT', 'Content item'
        GROUP = 'GROUP', 'Group'
        FORM = 'FORM', 'Form'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        PUBLISHED = 'PUBLISHED', 'Published'
        EXPIRED = 'EXPIRED', 'Expired'
        ARCHIVED = 'ARCHIVED', 'Archived'

    label = models.CharField(max_length=100)
    icon = models.CharField(max_length=100, blank=True)
    destination_type = models.CharField(max_length=20, choices=DestinationType.choices)
    # Loosely-typed by design (not a real FK) - matches the docs'
    # "destinationRef" concept; a stale reference is a dead link the
    # frontend handles gracefully, not a referential-integrity concern.
    destination_value = models.CharField(max_length=255, blank=True, help_text='URL or internal screen key')
    destination_id = models.CharField(max_length=64, blank=True, help_text='PK of the Event/Content/Group/Form target')

    sort_order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    publish_at = models.DateTimeField(null=True, blank=True)
    expire_at = models.DateTimeField(null=True, blank=True)
    is_protected = models.BooleanField(default=False, help_text='Protected items cannot be deleted via the API.')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.label

    def is_visible_to(self, user):
        if self.status != self.Status.PUBLISHED:
            return user.is_authenticated and (user.is_leader_or_admin or user.is_superuser)
        return self.is_in_audience(user)
