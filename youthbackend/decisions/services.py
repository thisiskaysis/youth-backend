"""Decision + follow-up domain logic. Permission/scope checks live in
views.py (same split as attendance/volunteers/forms_app); this module owns
data rules and notification triggers only.

Every optional field has a matching Python default here, even where the
serializer also marks it optional - DRF does not backfill a model field's
own default into validated_data when a client omits it, so relying solely
on that would crash (see roadmap-status.md session 4 write-up).
"""
from django.utils import timezone

from notifications.catalog import Category, NotificationType
from notifications.services import notify

from .models import Decision, FollowUp


class FollowUpError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def create_decision(*, person, recorded_by, decision_type, event=None, occurred_at=None, notes=''):
    return Decision.objects.create(
        person=person, event=event, decision_type=decision_type,
        occurred_at=occurred_at or timezone.now(), notes=notes, recorded_by=recorded_by,
    )


def assign_follow_up(decision, assignee, actor, due_at=None, notes=''):
    """Creates the decision's follow-up, or reassigns/updates it if one
    already exists - resets it to OUTSTANDING either way."""
    follow_up, _created = FollowUp.objects.update_or_create(
        decision=decision,
        defaults={
            'assignee': assignee, 'due_at': due_at, 'notes': notes,
            'assigned_by': actor, 'status': FollowUp.Status.OUTSTANDING, 'completed_at': None,
        },
    )
    notify(
        assignee, Category.LEADER_FOLLOWUP, NotificationType.FOLLOWUP_DUE,
        title='New follow-up assigned',
        body=f'Follow up with {decision.person} re: {decision.get_decision_type_display()}.',
        deep_link_type='follow_up', deep_link_id=follow_up.id,
        data={'follow_up_id': follow_up.id, 'stage': 'assigned'},
    )
    return follow_up


def update_follow_up_status(follow_up, actor, status, notes=None):
    if follow_up.assignee_id != actor.id and not (actor.role == actor.Role.PASTOR or actor.is_superuser):
        raise FollowUpError('NOT_YOUR_FOLLOWUP', 'This follow-up is not assigned to you.')

    follow_up.status = status
    if notes is not None:
        follow_up.notes = notes
    follow_up.completed_at = timezone.now() if status == FollowUp.Status.COMPLETED else None
    follow_up.save()
    return follow_up
