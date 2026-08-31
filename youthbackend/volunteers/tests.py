from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from events.models import Event
from groups.models import Group, GroupMembership
from notifications.models import Notification

from .models import VolunteerPosition

User = get_user_model()


class VolunteerRosterTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.team_leader = User.objects.create_user(
            username='teamleader', email='teamleader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.other_leader = User.objects.create_user(
            username='otherleader', email='otherleader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.volunteer = User.objects.create_user(
            username='volunteer1', email='volunteer1@example.com', password='pass12345'
        )
        self.outsider = User.objects.create_user(
            username='outsider1', email='outsider1@example.com', password='pass12345'
        )

        self.worship = Group.objects.create(name='Worship', group_type=Group.GroupType.VOLUNTEER)
        GroupMembership.objects.create(
            group=self.worship, person=self.team_leader, membership_role=GroupMembership.MembershipRole.LEADER
        )
        GroupMembership.objects.create(group=self.worship, person=self.volunteer)

        self.position = VolunteerPosition.objects.create(group=self.worship, name='MC1')
        self.event = Event.objects.create(name='Friday Youth', starts_at=timezone.now() + timedelta(days=2))


class PositionPermissionTests(VolunteerRosterTestCase):
    def test_leader_cannot_create_position_for_team_they_dont_lead(self):
        self.client.force_authenticate(self.other_leader)
        response = self.client.post('/api/volunteers/positions/', {
            'group': self.worship.id, 'name': 'Drums',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_leader_can_create_position_for_own_team(self):
        self.client.force_authenticate(self.team_leader)
        response = self.client.post('/api/volunteers/positions/', {
            'group': self.worship.id, 'name': 'Drums',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class AssignmentCreationTests(VolunteerRosterTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.team_leader)

    def _create(self, **overrides):
        payload = {'event': self.event.id, 'position': self.position.id, 'person': self.volunteer.id}
        payload.update(overrides)
        return self.client.post('/api/volunteers/assignments/', payload, format='json')

    def test_draft_assignment_sends_no_notification(self):
        response = self._create()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['assignment']['status'], 'DRAFT')
        self.assertEqual(Notification.objects.count(), 0)

    def test_cannot_assign_outsider_without_add_to_group_flag(self):
        response = self._create(person=self.outsider.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['code'], 'NOT_IN_TEAM')

    def test_add_to_group_flag_creates_membership_and_assignment(self):
        response = self._create(person=self.outsider.id, add_to_group=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            GroupMembership.objects.filter(group=self.worship, person=self.outsider, is_active=True).exists()
        )

    def test_other_leader_cannot_assign_into_this_team(self):
        self.client.force_authenticate(self.other_leader)
        response = self._create()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_double_assign_active_position(self):
        first = self._create()
        self.client.post('/api/volunteers/assignments/publish/', {
            'event': self.event.id, 'assignment_ids': [first.data['assignment']['id']],
        }, format='json')

        second = self.client.post('/api/volunteers/assignments/', {
            'event': self.event.id, 'position': self.position.id, 'person': self.outsider.id, 'add_to_group': True,
        }, format='json')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second.data['code'], 'POSITION_FILLED')

    def test_reassigning_a_draft_position_updates_it_in_place(self):
        first = self._create()
        second = self.client.post('/api/volunteers/assignments/', {
            'event': self.event.id, 'position': self.position.id, 'person': self.outsider.id, 'add_to_group': True,
        }, format='json')
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.data['assignment']['id'], first.data['assignment']['id'])
        self.assertEqual(second.data['assignment']['person']['id'], self.outsider.id)

    def test_conflict_detection_flags_overlapping_assignment(self):
        call_start = timezone.now() + timedelta(days=2)
        call_end = call_start + timedelta(hours=2)
        other_position = VolunteerPosition.objects.create(group=self.worship, name='MC2')

        first = self._create(call_start=call_start.isoformat(), call_end=call_end.isoformat())
        # Publish so the assignment is PENDING and therefore conflict-eligible.
        self.client.post('/api/volunteers/assignments/publish/', {
            'event': self.event.id, 'assignment_ids': [first.data['assignment']['id']],
        }, format='json')

        second = self.client.post('/api/volunteers/assignments/', {
            'event': self.event.id, 'position': other_position.id, 'person': self.volunteer.id,
            'call_start': call_start.isoformat(), 'call_end': call_end.isoformat(),
        }, format='json')
        self.assertEqual(len(second.data['conflicts']), 1)


class PublishAndRespondTests(VolunteerRosterTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.team_leader)
        create_resp = self.client.post('/api/volunteers/assignments/', {
            'event': self.event.id, 'position': self.position.id, 'person': self.volunteer.id,
        }, format='json')
        self.assignment_id = create_resp.data['assignment']['id']

    def test_publish_moves_draft_to_pending_and_notifies(self):
        response = self.client.post('/api/volunteers/assignments/publish/', {'event': self.event.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['status'], 'PENDING')
        self.assertTrue(
            Notification.objects.filter(
                person=self.volunteer, notification_type='VOLUNTEER_ASSIGNMENT_REQUESTED'
            ).exists()
        )

    def test_volunteer_can_accept_own_pending_assignment(self):
        self.client.post('/api/volunteers/assignments/publish/', {'event': self.event.id}, format='json')
        self.client.force_authenticate(self.volunteer)
        response = self.client.post(f'/api/volunteers/assignments/{self.assignment_id}/respond/', {
            'accept': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ACCEPTED')

    def test_leader_cannot_respond_on_behalf_of_their_volunteer(self):
        self.client.post('/api/volunteers/assignments/publish/', {'event': self.event.id}, format='json')
        # team_leader can see this assignment (they manage the team) but
        # must not be able to accept/decline it for someone else.
        response = self.client.post(f'/api/volunteers/assignments/{self.assignment_id}/respond/', {
            'accept': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['code'], 'NOT_YOUR_ASSIGNMENT')

    def test_unrelated_user_cannot_see_or_respond_to_assignment(self):
        self.client.post('/api/volunteers/assignments/publish/', {'event': self.event.id}, format='json')
        self.client.force_authenticate(self.outsider)
        response = self.client.post(f'/api/volunteers/assignments/{self.assignment_id}/respond/', {
            'accept': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_decline_notifies_team_leaders(self):
        self.client.post('/api/volunteers/assignments/publish/', {'event': self.event.id}, format='json')
        self.client.force_authenticate(self.volunteer)
        self.client.post(f'/api/volunteers/assignments/{self.assignment_id}/respond/', {
            'accept': False, 'decline_reason': 'Sick',
        }, format='json')
        self.assertTrue(
            Notification.objects.filter(person=self.team_leader, notification_type='ROSTER_DECLINED').exists()
        )

    def test_replacement_assignment_allowed_after_decline(self):
        self.client.post('/api/volunteers/assignments/publish/', {'event': self.event.id}, format='json')
        self.client.force_authenticate(self.volunteer)
        self.client.post(f'/api/volunteers/assignments/{self.assignment_id}/respond/', {'accept': False}, format='json')

        self.client.force_authenticate(self.team_leader)
        response = self.client.post('/api/volunteers/assignments/', {
            'event': self.event.id, 'position': self.position.id, 'person': self.team_leader.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cancel_notified_assignment_notifies_volunteer(self):
        self.client.post('/api/volunteers/assignments/publish/', {'event': self.event.id}, format='json')
        response = self.client.post(f'/api/volunteers/assignments/{self.assignment_id}/cancel/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Notification.objects.filter(
                person=self.volunteer, notification_type='VOLUNTEER_ASSIGNMENT_CANCELLED'
            ).exists()
        )


class VolunteerReminderCommandTests(VolunteerRosterTestCase):
    def test_pending_reminder_sent_after_48_hours_and_is_idempotent(self):
        from .services import assign_draft, get_or_create_roster, publish_requests
        roster = get_or_create_roster(self.event, self.team_leader)
        draft = assign_draft(roster=roster, position=self.position, person=self.volunteer, actor=self.team_leader)
        publish_requests(roster, [draft.id])
        draft.requested_at = timezone.now() - timedelta(hours=49)
        draft.save(update_fields=['requested_at'])

        call_command('send_volunteer_reminders')
        self.assertTrue(
            Notification.objects.filter(
                person=self.volunteer, notification_type='VOLUNTEER_RESPONSE_REMINDER'
            ).exists()
        )
        first_count = Notification.objects.filter(notification_type='VOLUNTEER_RESPONSE_REMINDER').count()

        call_command('send_volunteer_reminders')
        second_count = Notification.objects.filter(notification_type='VOLUNTEER_RESPONSE_REMINDER').count()
        self.assertEqual(first_count, second_count)

    def test_serving_soon_reminder_for_accepted_assignment(self):
        from .services import assign_draft, get_or_create_roster, publish_requests, respond
        roster = get_or_create_roster(self.event, self.team_leader)
        draft = assign_draft(
            roster=roster, position=self.position, person=self.volunteer, actor=self.team_leader,
            call_start=timezone.now() + timedelta(hours=24), call_end=timezone.now() + timedelta(hours=26),
        )
        publish_requests(roster, [draft.id])
        draft.refresh_from_db()
        respond(draft, self.volunteer, True)

        call_command('send_volunteer_reminders')
        self.assertTrue(
            Notification.objects.filter(
                person=self.volunteer, notification_type='VOLUNTEER_SERVING_SOON'
            ).exists()
        )
