from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class InboxMessage(TimeStampedModel):
    """A controlled one-way direct message - not full chat at launch (see
    BACKEND PLAN.xlsx sheet 02: "Realtime chat/presence at launch" is
    explicitly what this module should NOT own)."""

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)

    # Optional link back to whatever prompted this message (e.g. a prayer
    # request) so other domains can reuse Inbox without adding a new FK.
    related_type = models.CharField(max_length=50, blank=True)
    related_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.sender} -> {self.recipient}'
