from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base adding created/updated timestamps to a model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditEntry(models.Model):
    """Append-only record of who changed what, used for sensitive domains
    such as attendance corrections, profile edits and role changes."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_entries',
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64)
    reason = models.TextField(blank=True)
    changes = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Audit entries'

    def __str__(self):
        return f"{self.actor} {self.action} {self.entity_type}:{self.entity_id}"
