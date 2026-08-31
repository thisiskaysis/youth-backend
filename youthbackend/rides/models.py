from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from events.models import Event


class RideRequest(TimeStampedModel):
    class Direction(models.TextChoices):
        TO_CHURCH = 'TO_CHURCH', 'To church'
        HOME = 'HOME', 'Home'
        BOTH = 'BOTH', 'Both'

    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', 'Requested'
        ARRANGING = 'ARRANGING', 'Arranging'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_requests')
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name='ride_requests')
    requested_date = models.DateField(null=True, blank=True)
    direction = models.CharField(max_length=10, choices=Direction.choices, default=Direction.BOTH)
    # Deliberately coarse (suburb/area), never a precise address - avoid
    # unnecessary location exposure per QR/BACKEND PLAN safeguarding notes.
    area = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    assigned_leader = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_rides'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Ride for {self.person} ({self.status})'
