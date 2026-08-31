from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from groups.audience import AudienceTargetMixin


class ContentItem(TimeStampedModel, AudienceTargetMixin):
    """A newsfeed/announcement post. Draft/scheduled/published/expired/
    archived lifecycle prevents unfinished posts appearing (OVERVIEW.xlsx
    sheet 04) - status is staff-editable directly, but publish_at/expire_at
    let `publish_scheduled_content` automate the SCHEDULED->PUBLISHED and
    PUBLISHED->EXPIRED transitions."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        PUBLISHED = 'PUBLISHED', 'Published'
        EXPIRED = 'EXPIRED', 'Expired'
        ARCHIVED = 'ARCHIVED', 'Archived'

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    image = models.URLField(blank=True)
    cta_label = models.CharField(max_length=100, blank=True)
    cta_url = models.URLField(blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    publish_at = models.DateTimeField(null=True, blank=True)
    expire_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def is_visible_to(self, user):
        if self.status != self.Status.PUBLISHED:
            return user.is_authenticated and (user.is_leader_or_admin or user.is_superuser)
        return self.is_in_audience(user)
