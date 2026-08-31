from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Group(TimeStampedModel):
    """A single flexible model backs Connect Groups, volunteer/service
    teams and other ministry groupings - deliberately not one model per
    group type."""

    class GroupType(models.TextChoices):
        CONNECT = 'CONNECT', 'Connect Group'
        VOLUNTEER = 'VOLUNTEER', 'Volunteer / Service Team'
        MINISTRY = 'MINISTRY', 'Ministry Team'

    name = models.CharField(max_length=150)
    group_type = models.CharField(max_length=20, choices=GroupType.choices)
    description = models.TextField(blank=True)
    schedule = models.CharField(max_length=150, blank=True, help_text='e.g. Fridays 7:00pm')
    location = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='GroupMembership', related_name='ministry_groups'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class GroupMembership(TimeStampedModel):
    class MembershipRole(models.TextChoices):
        MEMBER = 'MEMBER', 'Member'
        LEADER = 'LEADER', 'Leader'

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_memberships'
    )
    membership_role = models.CharField(max_length=10, choices=MembershipRole.choices, default=MembershipRole.MEMBER)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['group', 'person'], name='unique_group_membership'),
        ]
        ordering = ['-membership_role', 'person__first_name']

    def __str__(self):
        return f"{self.person} in {self.group} ({self.membership_role})"
