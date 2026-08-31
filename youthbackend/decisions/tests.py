from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification

from .models import Decision, FollowUp
from .services import assign_follow_up, create_decision

User = get_user_model()


class DecisionPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pastor = User.objects.create_user(
            username='pastor', email='pastor@example.com', password='pass12345', role=User.Role.PASTOR
        )
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.other_leader = User.objects.create_user(
            username='otherleader', email='otherleader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )

    def test_youth_cannot_create_decision(self):
        self.client.force_authenticate(self.youth)
        response = self.client.post('/api/decisions/', {
            'person': self.youth.id, 'decision_type': Decision.DecisionType.FIRST_TIME,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_youth_cannot_list_decisions(self):
        self.client.force_authenticate(self.youth)
        response = self.client.get('/api/decisions/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_leader_can_record_decision(self):
        self.client.force_authenticate(self.leader)
        response = self.client.post('/api/decisions/', {
            'person': self.youth.id, 'decision_type': Decision.DecisionType.FIRST_TIME, 'notes': 'Prayed at youth night',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['person']['id'], self.youth.id)
        self.assertIsNone(response.data['follow_up'])

    def test_leader_who_didnt_record_cannot_see_or_assign_follow_up(self):
        decision = create_decision(
            person=self.youth, recorded_by=self.leader, decision_type=Decision.DecisionType.FIRST_TIME,
        )
        self.client.force_authenticate(self.other_leader)
        # Queryset-level scoping already hides decisions this Leader has no
        # relation to - same info-hiding precedent as the volunteers app.
        response = self.client.post(f'/api/decisions/{decision.id}/follow-up/', {
            'assignee_id': self.other_leader.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_recorder_can_assign_follow_up_and_assignee_is_notified(self):
        decision = create_decision(
            person=self.youth, recorded_by=self.leader, decision_type=Decision.DecisionType.FIRST_TIME,
        )
        self.client.force_authenticate(self.leader)
        response = self.client.post(f'/api/decisions/{decision.id}/follow-up/', {
            'assignee_id': self.other_leader.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'OUTSTANDING')
        self.assertTrue(
            Notification.objects.filter(person=self.other_leader, notification_type='FOLLOWUP_DUE').exists()
        )

    def test_assignee_can_reassign_to_someone_else(self):
        decision = create_decision(
            person=self.youth, recorded_by=self.leader, decision_type=Decision.DecisionType.FIRST_TIME,
        )
        assign_follow_up(decision, assignee=self.other_leader, actor=self.leader)

        self.client.force_authenticate(self.other_leader)
        response = self.client.post(f'/api/decisions/{decision.id}/follow-up/', {
            'assignee_id': self.pastor.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['assignee']['id'], self.pastor.id)

    def test_cannot_assign_follow_up_to_a_youth(self):
        decision = create_decision(
            person=self.youth, recorded_by=self.leader, decision_type=Decision.DecisionType.FIRST_TIME,
        )
        self.client.force_authenticate(self.leader)
        response = self.client.post(f'/api/decisions/{decision.id}/follow-up/', {
            'assignee_id': self.youth.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FollowUpStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pastor = User.objects.create_user(
            username='pastor2', email='pastor2@example.com', password='pass12345', role=User.Role.PASTOR
        )
        self.leader = User.objects.create_user(
            username='leader2', email='leader2@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.other_leader = User.objects.create_user(
            username='otherleader2', email='otherleader2@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth2', email='youth2@example.com', password='pass12345'
        )
        self.decision = create_decision(
            person=self.youth, recorded_by=self.pastor, decision_type=Decision.DecisionType.RECOMMITMENT,
        )
        self.follow_up = assign_follow_up(self.decision, assignee=self.leader, actor=self.pastor)

    def test_assignee_can_update_own_status(self):
        self.client.force_authenticate(self.leader)
        response = self.client.post(f'/api/decisions/follow-ups/{self.follow_up.id}/status/', {
            'status': 'COMPLETED', 'notes': 'Met for coffee',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'COMPLETED')
        self.assertIsNotNone(response.data['completed_at'])

    def test_other_leader_cannot_see_or_update_someone_elses_follow_up(self):
        self.client.force_authenticate(self.other_leader)
        # Same info-hiding precedent: queryset scoping (assignee=self)
        # already hides it before the service's NOT_YOUR_FOLLOWUP check
        # would ever run - see test_service_rejects_non_assignee below for
        # that check exercised directly.
        response = self.client.post(f'/api/decisions/follow-ups/{self.follow_up.id}/status/', {
            'status': 'COMPLETED',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_service_rejects_non_assignee(self):
        from .services import FollowUpError, update_follow_up_status
        with self.assertRaises(FollowUpError) as ctx:
            update_follow_up_status(self.follow_up, self.other_leader, 'COMPLETED')
        self.assertEqual(ctx.exception.code, 'NOT_YOUR_FOLLOWUP')

    def test_pastor_can_update_any_follow_up(self):
        self.client.force_authenticate(self.pastor)
        response = self.client.post(f'/api/decisions/follow-ups/{self.follow_up.id}/status/', {
            'status': 'IN_PROGRESS',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_leader_sees_only_own_follow_ups_pastor_sees_all(self):
        self.client.force_authenticate(self.leader)
        response = self.client.get('/api/decisions/follow-ups/')
        self.assertEqual(len(response.data['results']), 1)

        self.client.force_authenticate(self.other_leader)
        response = self.client.get('/api/decisions/follow-ups/')
        self.assertEqual(len(response.data['results']), 0)

        self.client.force_authenticate(self.pastor)
        response = self.client.get('/api/decisions/follow-ups/')
        self.assertEqual(len(response.data['results']), 1)


class FollowUpReminderCommandTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(
            username='leader3', email='leader3@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth3', email='youth3@example.com', password='pass12345'
        )

    def _decision_with_follow_up(self, due_at):
        decision = create_decision(
            person=self.youth, recorded_by=self.leader, decision_type=Decision.DecisionType.FIRST_TIME,
        )
        follow_up = assign_follow_up(decision, assignee=self.leader, actor=self.leader, due_at=due_at)
        # The immediate "assigned" notice must not be mistaken for the
        # reminder command's own due_soon/overdue notifications.
        return follow_up

    def test_due_soon_and_overdue_and_idempotent(self):
        due_soon = self._decision_with_follow_up(timezone.now() + timedelta(hours=12))
        overdue = self._decision_with_follow_up(timezone.now() - timedelta(days=1))

        call_command('send_followup_reminders')
        self.assertTrue(
            Notification.objects.filter(
                notification_type='FOLLOWUP_DUE', data__follow_up_id=due_soon.id, data__stage='due_soon'
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                notification_type='FOLLOWUP_OVERDUE', data__follow_up_id=overdue.id
            ).exists()
        )

        call_command('send_followup_reminders')
        self.assertEqual(
            Notification.objects.filter(
                notification_type='FOLLOWUP_DUE', data__follow_up_id=due_soon.id, data__stage='due_soon'
            ).count(),
            2,  # push + email, not duplicated by the second command run
        )

    def test_no_reminder_once_completed(self):
        follow_up = self._decision_with_follow_up(timezone.now() - timedelta(hours=1))
        follow_up.status = FollowUp.Status.COMPLETED
        follow_up.save(update_fields=['status'])

        call_command('send_followup_reminders')
        self.assertFalse(Notification.objects.filter(notification_type='FOLLOWUP_OVERDUE').exists())
