from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from events.models import Event


class AttendanceSession(TimeStampedModel):
    """The specific gathering currently accepting attendance. Every scan
    is recorded against exactly one session."""

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        CLOSED = 'CLOSED', 'Closed'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendance_sessions')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['-opened_at']

    def __str__(self):
        return f"{self.event} ({self.status})"


class AttendanceRecord(TimeStampedModel):
    """One person's attendance for a session. Launch model keeps exactly
    one record per person/session - null signed_out_at means the person is
    currently considered ON SITE. There is no separate is_on_site flag."""

    class Source(models.TextChoices):
        QR = 'QR', 'QR Scan'
        MANUAL = 'MANUAL', 'Manual'

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendance_records'
    )

    signed_in_at = models.DateTimeField(null=True, blank=True)
    signed_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    sign_in_source = models.CharField(max_length=10, choices=Source.choices, blank=True)

    signed_out_at = models.DateTimeField(null=True, blank=True)
    signed_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    sign_out_source = models.CharField(max_length=10, choices=Source.choices, blank=True)

    correction_note = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['session', 'person'], name='unique_person_per_session'),
        ]
        ordering = ['-signed_in_at']

    @property
    def is_on_site(self):
        return bool(self.signed_in_at and not self.signed_out_at)

    def __str__(self):
        return f"{self.person} @ {self.session}"
