from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from attendance.models import AttendanceSession
from attendance.services import sign_in
from decisions.services import assign_follow_up, create_decision
from events.models import Event
from forms_app.models import FormAssignment, FormDefinition
from groups.models import Group, GroupMembership
from prayer.services import create_request as create_prayer_request
from prayer.models import PrayerRequest
from rides.services import create_ride_request
from rides.models import RideRequest
from volunteers.services import assign_draft, get_or_create_roster, publish_requests

User = get_user_model()


class ReportingPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )

    def test_youth_cannot_access_dashboard(self):
        self.client.force_authenticate(self.youth)
        response = self.client.get('/api/reporting/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DashboardAggregateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pastor = User.objects.create_user(
            username='pastor', email='pastor@example.com', password='pass12345', role=User.Role.PASTOR
        )
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.year_9 = User.objects.create_user(
            username='year9', email='year9@example.com', password='pass12345', school_year=9
        )
        self.year_12 = User.objects.create_user(
            username='year12', email='year12@example.com', password='pass12345', school_year=12
        )
        self.visitor = User.objects.create_user(
            username='visitor1', email='visitor1@example.com', password='pass12345', is_provisional=True
        )
        self.unassigned_youth = User.objects.create_user(
            username='unassigned', email='unassigned@example.com', password='pass12345'
        )
        self.client.force_authenticate(self.pastor)

        self.event = Event.objects.create(name='Friday Youth', starts_at=timezone.now())
        self.session = AttendanceSession.objects.create(event=self.event, opened_by=self.leader)
        for person in (self.year_9, self.year_12, self.visitor):
            sign_in(self.session, person, self.leader, 'MANUAL')

        self.group = Group.objects.create(name='Connect', group_type=Group.GroupType.CONNECT)
        GroupMembership.objects.create(group=self.group, person=self.year_9)

    def test_attendance_summary(self):
        response = self.client.get('/api/reporting/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        attendance = response.data['attendance']
        self.assertEqual(attendance['total_attended'], 3)
        self.assertEqual(attendance['unique_youth'], 3)
        self.assertEqual(attendance['first_time_visitors'], 1)

    def test_school_year_breakdown(self):
        response = self.client.get('/api/reporting/dashboard/')
        breakdown = {row['person__school_year']: row['count'] for row in response.data['school_year_breakdown']}
        self.assertEqual(breakdown.get(9), 1)
        self.assertEqual(breakdown.get(12), 1)

    def test_group_participation_and_unassigned_youth(self):
        response = self.client.get('/api/reporting/dashboard/')
        participation = response.data['group_participation']
        # year_12 + visitor + unassigned_youth (the visitor is YOUTH-role
        # and not in any group, so it counts here too).
        self.assertEqual(participation['unassigned_youth'], 3)

        drilldown = self.client.get('/api/reporting/unassigned-youth/')
        ids = {row['id'] for row in drilldown.data['results']}
        self.assertEqual(ids, {self.year_12.id, self.visitor.id, self.unassigned_youth.id})

    def test_first_time_visitors_drilldown(self):
        response = self.client.get('/api/reporting/first-time-visitors/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.visitor.id)

    def test_decisions_summary_and_outstanding_followups(self):
        decision = create_decision(
            person=self.year_9, recorded_by=self.leader, decision_type='FIRST_TIME', event=self.event,
        )
        assign_follow_up(decision, assignee=self.leader, actor=self.leader)

        response = self.client.get('/api/reporting/dashboard/')
        decisions = response.data['decisions']
        self.assertEqual(decisions['total'], 1)
        self.assertEqual(decisions['outstanding_follow_ups'], 1)

        drilldown = self.client.get('/api/reporting/outstanding-followups/')
        self.assertEqual(drilldown.data['count'], 1)

    def test_prayer_volume_never_exposes_body(self):
        create_prayer_request(
            author=self.year_9, body='Secret prayer detail', visibility=PrayerRequest.Visibility.PUBLIC,
        )
        response = self.client.get('/api/reporting/dashboard/')
        prayer = response.data['prayer']
        self.assertEqual(prayer['total'], 1)
        self.assertNotIn('Secret prayer detail', str(response.data))

    def test_rides_summary(self):
        create_ride_request(person=self.year_9, direction=RideRequest.Direction.HOME, area='Northside')
        response = self.client.get('/api/reporting/dashboard/')
        self.assertEqual(response.data['rides']['total'], 1)
        by_status = {row['status']: row['count'] for row in response.data['rides']['by_status']}
        self.assertEqual(by_status.get('REQUESTED'), 1)

    def test_outstanding_consent(self):
        form = FormDefinition.objects.create(title='Camp Consent', created_by=self.leader)
        FormAssignment.objects.create(form=form, person=self.year_9)
        response = self.client.get('/api/reporting/dashboard/')
        self.assertEqual(response.data['outstanding_consent'], 1)

        drilldown = self.client.get('/api/reporting/outstanding-consent/')
        self.assertEqual(drilldown.data['count'], 1)

    def test_attendance_trend_buckets_current_week(self):
        response = self.client.get('/api/reporting/attendance-trend/?weeks=4')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(sum(bucket['unique_youth'] for bucket in response.data['trend']), 3)


class RosterSummaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pastor = User.objects.create_user(
            username='pastor2', email='pastor2@example.com', password='pass12345', role=User.Role.PASTOR
        )
        self.volunteer = User.objects.create_user(
            username='vol1', email='vol1@example.com', password='pass12345'
        )
        self.client.force_authenticate(self.pastor)
        self.event = Event.objects.create(name='Friday Youth', starts_at=timezone.now() + timedelta(days=2))

    def test_roster_summary_requires_event_param(self):
        response = self.client.get('/api/reporting/roster-summary/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_roster_summary_with_no_roster_yet(self):
        response = self.client.get(f'/api/reporting/roster-summary/?event={self.event.id}')
        self.assertEqual(response.data, {'filled': 0, 'pending': 0, 'accepted': 0, 'declined': 0, 'unfilled': 0})

    def test_roster_summary_computes_filled_and_unfilled(self):
        from volunteers.models import VolunteerPosition

        worship = Group.objects.create(name='Worship', group_type=Group.GroupType.VOLUNTEER)
        GroupMembership.objects.create(group=worship, person=self.volunteer)
        mc1 = VolunteerPosition.objects.create(group=worship, name='MC1')
        VolunteerPosition.objects.create(group=worship, name='MC2')  # left unfilled

        roster = get_or_create_roster(self.event, self.pastor)
        assignment = assign_draft(roster=roster, position=mc1, person=self.volunteer, actor=self.pastor)
        publish_requests(roster, [assignment.id])

        response = self.client.get(f'/api/reporting/roster-summary/?event={self.event.id}')
        self.assertEqual(response.data, {'filled': 1, 'pending': 1, 'accepted': 0, 'declined': 0, 'unfilled': 1})
