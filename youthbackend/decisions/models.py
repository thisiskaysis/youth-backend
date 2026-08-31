from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from events.models import Event


class Decision(TimeStampedModel):
    """A structured ministry outcome (e.g. decision for Jesus) - treated as
    accountable pastoral data, not a free-text note. Not editable/deletable
    via the API once recorded; only its follow-up moves."""

    class DecisionType(models.TextChoices):
        FIRST_TIME = 'FIRST_TIME', 'First-time decision'
        RECOMMITMENT = 'RECOMMITMENT', 'Recommitment'
        BAPTISM_INTEREST = 'BAPTISM_INTEREST', 'Baptism interest'
        BAPTISM = 'BAPTISM', 'Baptism'
        NEW_TO_CHURCH = 'NEW_TO_CHURCH', 'New to church'
        OTHER = 'OTHER', 'Other'

    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='decisions')
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name='decisions')
    decision_type = models.CharField(max_length=20, choices=DecisionType.choices)
    occurred_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f'{self.get_decision_type_display()} - {self.person}'


class FollowUp(TimeStampedModel):
    """One accountable follow-up per decision. Reassigning just updates the
    assignee in place rather than spawning parallel follow-up threads."""

    class Status(models.TextChoices):
        OUTSTANDING = 'OUTSTANDING', 'Outstanding'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        COMPLETED = 'COMPLETED', 'Completed'

    decision = models.OneToOneField(Decision, on_delete=models.CASCADE, related_name='follow_up')
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_follow_ups'
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OUTSTANDING)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['due_at']

    def __str__(self):
        return f'Follow-up for {self.decision} -> {self.assignee} ({self.status})'
