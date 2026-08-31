"""Volunteer rostering domain logic. Permission/team-scope checks
("does this actor manage this group?") live in views.py, matching the
groups app convention. This module owns the assignment state machine and
raises VolunteerError for business-rule violations - it never raises DRF
exceptions directly, matching the attendance app convention.
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from groups.models import GroupMembership
from notifications.catalog import Category, NotificationType
from notifications.services import notify, notify_many

from .models import Roster, VolunteerAssignment

User = get_user_model()


class VolunteerError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def get_or_create_roster(event, actor):
    roster, _ = Roster.objects.get_or_create(event=event, defaults={'created_by': actor})
    return roster


def team_leaders(group):
    """Every Leader who leads this specific group, plus all Admins -
    the practical stand-in for a proper "attendance managers" assignment
    concept, which doesn't exist yet."""
    leader_ids = GroupMembership.objects.filter(
        group=group, membership_role=GroupMembership.MembershipRole.LEADER, is_active=True
    ).values_list('person_id', flat=True)
    return User.objects.filter(id__in=leader_ids) | User.objects.filter(role=User.Role.ADMIN)


def find_conflicts(person, call_start, call_end, exclude_assignment_id=None):
    """Other PENDING/ACCEPTED assignments for this person that overlap the
    given call window - a warning surfaced to the roster manager, never a
    hard block (see VOLUNTEERS.xlsx sheet 11)."""
    if not (call_start and call_end):
        return VolunteerAssignment.objects.none()
    queryset = VolunteerAssignment.objects.filter(
        person=person,
        status__in=[VolunteerAssignment.Status.PENDING, VolunteerAssignment.Status.ACCEPTED],
        call_start__lt=call_end,
        call_end__gt=call_start,
    ).select_related('position', 'group')
    if exclude_assignment_id:
        queryset = queryset.exclude(pk=exclude_assignment_id)
    return queryset


@transaction.atomic
def assign_draft(*, roster, position, person, actor, call_start=None, call_end=None, notes='', add_to_group=False):
    group = position.group
    is_member = GroupMembership.objects.filter(group=group, person=person, is_active=True).exists()
    if not is_member and not add_to_group:
        raise VolunteerError(
            'NOT_IN_TEAM',
            'This person is not in the team - pass add_to_group=true to confirm assigning them anyway.',
        )
    if not is_member and add_to_group:
        GroupMembership.objects.get_or_create(
            group=group, person=person, defaults={'membership_role': GroupMembership.MembershipRole.MEMBER}
        )

    existing = VolunteerAssignment.objects.filter(roster=roster, position=position).exclude(
        status__in=[VolunteerAssignment.Status.CANCELLED, VolunteerAssignment.Status.DECLINED]
    ).first()
    if existing and existing.status != VolunteerAssignment.Status.DRAFT:
        raise VolunteerError('POSITION_FILLED', 'This position already has an active assignment.')

    if existing:
        existing.person = person
        existing.call_start = call_start
        existing.call_end = call_end
        existing.notes = notes
        existing.save()
        return existing

    return VolunteerAssignment.objects.create(
        roster=roster, group=group, position=position, person=person,
        call_start=call_start, call_end=call_end, notes=notes, created_by=actor,
    )


@transaction.atomic
def publish_requests(roster, assignment_ids):
    """Move the given DRAFT assignments to PENDING and notify each
    volunteer. Draft construction stays silent until this is called -
    publishing is always an explicit, separate step."""
    queryset = roster.assignments.filter(
        status=VolunteerAssignment.Status.DRAFT, id__in=assignment_ids
    ).select_related('position', 'person', 'roster__event')

    published = []
    for assignment in queryset:
        assignment.status = VolunteerAssignment.Status.PENDING
        assignment.requested_at = timezone.now()
        assignment.save(update_fields=['status', 'requested_at'])
        published.append(assignment)

    if published and roster.status != Roster.Status.PUBLISHED:
        roster.status = Roster.Status.PUBLISHED
        roster.published_at = timezone.now()
        roster.save(update_fields=['status', 'published_at'])

    for assignment in published:
        notify(
            assignment.person, Category.VOLUNTEER_REQUESTS, NotificationType.VOLUNTEER_ASSIGNMENT_REQUESTED,
            title=f'Serving request: {assignment.position.name}',
            body=f'{assignment.roster.event.name} needs you as {assignment.position.name}.',
            deep_link_type='volunteer_assignment', deep_link_id=assignment.id,
            data={'assignment_id': assignment.id},
        )
    return published


@transaction.atomic
def respond(assignment, person, accept, decline_reason='', decline_note=''):
    if assignment.person_id != person.id:
        raise VolunteerError('NOT_YOUR_ASSIGNMENT', 'This assignment does not belong to you.')
    if assignment.status != VolunteerAssignment.Status.PENDING:
        raise VolunteerError('NOT_PENDING', 'This assignment is no longer awaiting a response.')

    assignment.status = VolunteerAssignment.Status.ACCEPTED if accept else VolunteerAssignment.Status.DECLINED
    assignment.responded_at = timezone.now()
    if not accept:
        assignment.decline_reason = decline_reason
        assignment.decline_note = decline_note
    assignment.save()

    if not accept:
        notify_many(
            team_leaders(assignment.group), Category.LEADER_ROSTER, NotificationType.ROSTER_DECLINED,
            title=f'{person} declined {assignment.position.name}',
            body=f'{assignment.roster.event.name} needs a replacement for {assignment.position.name}.',
            deep_link_type='volunteer_assignment', deep_link_id=assignment.id,
            data={'assignment_id': assignment.id},
        )
    return assignment


@transaction.atomic
def cancel_assignment(assignment, reason=''):
    if assignment.status == VolunteerAssignment.Status.CANCELLED:
        raise VolunteerError('ALREADY_CANCELLED', 'This assignment is already cancelled.')

    was_notified = assignment.status in (VolunteerAssignment.Status.PENDING, VolunteerAssignment.Status.ACCEPTED)
    assignment.status = VolunteerAssignment.Status.CANCELLED
    assignment.save(update_fields=['status'])

    if was_notified:
        notify(
            assignment.person, Category.VOLUNTEER_CHANGES, NotificationType.VOLUNTEER_ASSIGNMENT_CANCELLED,
            title=f'{assignment.position.name} - assignment cancelled',
            body=f'You are no longer needed for {assignment.roster.event.name}.',
            deep_link_type='volunteer_assignment', deep_link_id=assignment.id,
            data={'assignment_id': assignment.id}, urgent=True,
        )
    return assignment
