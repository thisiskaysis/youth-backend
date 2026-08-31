from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from events.models import Event
from groups.models import Group


class VolunteerPosition(TimeStampedModel):
    """A configurable role inside one team, e.g. Worship > MC1/Drums/Guitar.
    Positions belong to a team, not to a global catalogue."""

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='volunteer_positions')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['group_id', 'sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['group', 'name'], name='unique_position_name_per_group'),
        ]

    def __str__(self):
        return f'{self.name} ({self.group})'


class Roster(TimeStampedModel):
    """One roster per Event under the launch model. This is just a
    container/lifecycle marker - the real state machine lives on
    VolunteerAssignment."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'

    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='roster')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    def __str__(self):
        return f'Roster for {self.event}'


class VolunteerAssignment(TimeStampedModel):
    """One person requested/assigned to one position for one event."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        DECLINED = 'DECLINED', 'Declined'
        CANCELLED = 'CANCELLED', 'Cancelled'
        COMPLETED = 'COMPLETED', 'Completed'

    roster = models.ForeignKey(Roster, on_delete=models.CASCADE, related_name='assignments')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='volunteer_assignments')
    position = models.ForeignKey(VolunteerPosition, on_delete=models.CASCADE, related_name='assignments')
    person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='volunteer_assignments'
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    call_start = models.DateTimeField(null=True, blank=True)
    call_end = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    requested_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.CharField(max_length=100, blank=True)
    decline_note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['position__sort_order', 'id']
        constraints = [
            # A position holds at most one currently-active assignment;
            # declined/cancelled rows don't block a replacement being made.
            models.UniqueConstraint(
                fields=['roster', 'position'],
                condition=~models.Q(status__in=['CANCELLED', 'DECLINED']),
                name='unique_active_assignment_per_position',
            ),
        ]

    def __str__(self):
        return f'{self.person} - {self.position} ({self.status})'


class VolunteerAvailability(TimeStampedModel):
    """A period a volunteer has flagged themselves unavailable. Informs the
    candidate picker as a warning only - never silently blocks/changes
    membership or an assignment."""

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='availability_periods'
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['starts_at']

    def __str__(self):
        return f'{self.person} unavailable {self.starts_at:%d %b} - {self.ends_at:%d %b}'
