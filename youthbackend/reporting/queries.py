"""Read-only aggregation queries for the leadership dashboard. This app
owns no models of its own - every "Must-have" launch metric from
OVERVIEW.xlsx sheet 05 / BACKEND PLAN.xlsx sheet 11 is a plain function
here operating on other apps' models. Deliberately NOT group-scoped for
most metrics (attendance/decisions/prayer/rides aren't group-scoped
anywhere else in this codebase either - see architecture.md); group
participation and roster summary are the two genuinely per-group metrics.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.utils import timezone

from attendance.models import AttendanceRecord
from decisions.models import Decision, FollowUp
from forms_app.models import FormAssignment
from groups.models import Group, GroupMembership
from prayer.models import PrayerRequest
from rides.models import RideRequest
from volunteers.models import Roster, VolunteerAssignment, VolunteerPosition

User = get_user_model()


def parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def get_filters(request):
    return {
        'start_date': parse_date(request.query_params.get('start_date')),
        'end_date': parse_date(request.query_params.get('end_date')),
        'event': request.query_params.get('event'),
        'group': request.query_params.get('group'),
        'school_year': request.query_params.get('school_year'),
    }


def attendance_queryset(filters):
    qs = AttendanceRecord.objects.filter(signed_in_at__isnull=False).select_related('person', 'session__event')
    if filters.get('event'):
        qs = qs.filter(session__event_id=filters['event'])
    if filters.get('start_date'):
        qs = qs.filter(signed_in_at__date__gte=filters['start_date'])
    if filters.get('end_date'):
        qs = qs.filter(signed_in_at__date__lte=filters['end_date'])
    if filters.get('school_year'):
        qs = qs.filter(person__school_year=filters['school_year'])
    if filters.get('group'):
        qs = qs.filter(
            person__group_memberships__group_id=filters['group'], person__group_memberships__is_active=True
        )
    return qs.distinct()


def attendance_summary(filters):
    qs = attendance_queryset(filters)
    return {
        'total_attended': qs.count(),
        'unique_youth': qs.values('person_id').distinct().count(),
        'first_time_visitors': qs.filter(person__is_provisional=True).values('person_id').distinct().count(),
    }


def school_year_breakdown(filters):
    qs = attendance_queryset(filters).exclude(person__school_year__isnull=True)
    return list(
        qs.values('person__school_year')
        .annotate(count=Count('person_id', distinct=True))
        .order_by('person__school_year')
    )


def attendance_trend(weeks=8):
    weeks = max(1, min(weeks, 52))
    since = timezone.now() - timezone.timedelta(weeks=weeks)
    qs = AttendanceRecord.objects.filter(signed_in_at__gte=since, signed_in_at__isnull=False)
    buckets = (
        qs.annotate(week=TruncWeek('signed_in_at'))
        .values('week')
        .annotate(count=Count('person_id', distinct=True))
        .order_by('week')
    )
    return [{'week': b['week'].date().isoformat(), 'unique_youth': b['count']} for b in buckets]


def group_participation(filters):
    qs = GroupMembership.objects.filter(is_active=True)
    if filters.get('group'):
        qs = qs.filter(group_id=filters['group'])
    by_type = list(
        qs.values('group__group_type').annotate(count=Count('person_id', distinct=True)).order_by('group__group_type')
    )
    member_ids = qs.values_list('person_id', flat=True).distinct()
    unassigned_youth = User.objects.filter(status=User.Status.ACTIVE, role=User.Role.YOUTH).exclude(
        id__in=member_ids
    ).count()
    return {'by_group_type': by_type, 'unassigned_youth': unassigned_youth}


def unassigned_youth_queryset():
    member_ids = GroupMembership.objects.filter(is_active=True).values_list('person_id', flat=True)
    return User.objects.filter(status=User.Status.ACTIVE, role=User.Role.YOUTH).exclude(
        id__in=member_ids
    ).order_by('first_name', 'last_name')


def decisions_queryset(filters):
    qs = Decision.objects.select_related('person', 'event', 'recorded_by', 'follow_up__assignee')
    if filters.get('event'):
        qs = qs.filter(event_id=filters['event'])
    if filters.get('start_date'):
        qs = qs.filter(occurred_at__date__gte=filters['start_date'])
    if filters.get('end_date'):
        qs = qs.filter(occurred_at__date__lte=filters['end_date'])
    return qs


def decisions_summary(filters):
    qs = decisions_queryset(filters)
    by_type = list(qs.values('decision_type').annotate(count=Count('id')).order_by('decision_type'))
    outstanding = FollowUp.objects.filter(
        decision__in=qs, status__in=[FollowUp.Status.OUTSTANDING, FollowUp.Status.IN_PROGRESS]
    ).count()
    return {'total': qs.count(), 'by_type': by_type, 'outstanding_follow_ups': outstanding}


def outstanding_follow_ups_queryset():
    return FollowUp.objects.filter(
        status__in=[FollowUp.Status.OUTSTANDING, FollowUp.Status.IN_PROGRESS]
    ).select_related('decision__person', 'assignee')


def prayer_volume(filters):
    qs = PrayerRequest.objects.all()
    if filters.get('start_date'):
        qs = qs.filter(created_at__date__gte=filters['start_date'])
    if filters.get('end_date'):
        qs = qs.filter(created_at__date__lte=filters['end_date'])
    return {
        'total': qs.count(),
        # Aggregate only - never expose prayer body content in a broad report.
        'by_category': list(qs.values('category').annotate(count=Count('id')).order_by('-count')),
        'by_status': list(qs.values('status').annotate(count=Count('id')).order_by('status')),
    }


def rides_queryset(filters):
    qs = RideRequest.objects.select_related('person', 'assigned_leader', 'event')
    if filters.get('start_date'):
        qs = qs.filter(created_at__date__gte=filters['start_date'])
    if filters.get('end_date'):
        qs = qs.filter(created_at__date__lte=filters['end_date'])
    if filters.get('event'):
        qs = qs.filter(event_id=filters['event'])
    return qs


def rides_summary(filters):
    qs = rides_queryset(filters)
    return {
        'total': qs.count(),
        'by_status': list(qs.values('status').annotate(count=Count('id')).order_by('status')),
    }


def outstanding_consent_queryset(filters):
    qs = FormAssignment.objects.filter(status=FormAssignment.Status.OUTSTANDING).select_related('form', 'person')
    if filters.get('school_year'):
        qs = qs.filter(person__school_year=filters['school_year'])
    return qs


def roster_summary(event_id):
    roster = Roster.objects.filter(event_id=event_id).first()
    if not roster:
        return {'filled': 0, 'pending': 0, 'accepted': 0, 'declined': 0, 'unfilled': 0}

    assignments = roster.assignments.exclude(status=VolunteerAssignment.Status.CANCELLED)
    active = assignments.exclude(status=VolunteerAssignment.Status.DECLINED)
    relevant_group_ids = assignments.values_list('group_id', flat=True).distinct()
    total_positions = VolunteerPosition.objects.filter(group_id__in=relevant_group_ids, is_active=True).count()
    filled = active.values('position_id').distinct().count()

    return {
        'filled': filled,
        'pending': assignments.filter(status=VolunteerAssignment.Status.PENDING).count(),
        'accepted': assignments.filter(status=VolunteerAssignment.Status.ACCEPTED).count(),
        'declined': assignments.filter(status=VolunteerAssignment.Status.DECLINED).count(),
        'unfilled': max(total_positions - filled, 0),
    }
