from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification

from .models import PrayerRequest

User = get_user_model()


class PrayerRequestTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin', email='admin@example.com', password='pass12345', role=User.Role.ADMIN
        )
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )
        self.other_youth = User.objects.create_user(
            username='youth2', email='youth2@example.com', password='pass12345'
        )

    def _create(self, user, **overrides):
        payload = {'body': 'Please pray for my exams', 'visibility': PrayerRequest.Visibility.PUBLIC}
        payload.update(overrides)
        self.client.force_authenticate(user)
        return self.client.post('/api/prayer/requests/', payload, format='json')

    def test_public_request_starts_pending_moderation(self):
        response = self._create(self.youth)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'PENDING')

    def test_leaders_only_request_auto_approved_and_notifies_staff(self):
        response = self._create(self.youth, visibility=PrayerRequest.Visibility.LEADERS_ONLY)
        self.assertEqual(response.data['status'], 'APPROVED')
        self.assertTrue(
            Notification.objects.filter(person=self.leader, notification_type='PRIVATE_PRAYER_NEW').exists()
        )

    def test_anonymous_request_hides_author_from_everyone(self):
        response = self._create(self.youth, is_anonymous=True)
        self.assertIsNone(response.data['author'])

        request_id = response.data['id']
        self.client.force_authenticate(self.admin)
        detail = self.client.get(f'/api/prayer/requests/{request_id}/')
        self.assertIsNone(detail.data['author'])

    def test_wall_only_shows_approved_public_requests(self):
        pending = self._create(self.youth)
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/prayer/requests/{pending.data['id']}/moderate/", {'status': 'APPROVED'}, format='json')

        self.client.force_authenticate(self.other_youth)
        wall = self.client.get('/api/prayer/requests/?wall=true')
        self.assertEqual(len(wall.data['results']), 1)
        self.assertEqual(wall.data['results'][0]['id'], pending.data['id'])

    def test_youth_cannot_see_others_leaders_only_request(self):
        created = self._create(self.youth, visibility=PrayerRequest.Visibility.LEADERS_ONLY)
        self.client.force_authenticate(self.other_youth)
        response = self.client.get(f"/api/prayer/requests/{created.data['id']}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_leader_sees_leaders_only_queue(self):
        self._create(self.youth, visibility=PrayerRequest.Visibility.LEADERS_ONLY)
        self.client.force_authenticate(self.leader)
        response = self.client.get('/api/prayer/requests/')
        self.assertEqual(len(response.data['results']), 1)

    def test_youth_cannot_moderate(self):
        created = self._create(self.youth)
        self.client.force_authenticate(self.youth)
        response = self.client.post(
            f"/api/prayer/requests/{created.data['id']}/moderate/", {'status': 'APPROVED'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_escalate_notifies_admins(self):
        created = self._create(self.youth)
        self.client.force_authenticate(self.leader)
        response = self.client.post(
            f"/api/prayer/requests/{created.data['id']}/moderate/",
            {'status': 'ESCALATED', 'note': 'Needs pastoral care'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Notification.objects.filter(person=self.admin, notification_type='PRAYER_ESCALATED').exists()
        )

    def test_pray_action_toggles_and_is_idempotent_per_person(self):
        created = self._create(self.youth)
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/prayer/requests/{created.data['id']}/moderate/", {'status': 'APPROVED'}, format='json')

        self.client.force_authenticate(self.other_youth)
        first = self.client.post(f"/api/prayer/requests/{created.data['id']}/pray/")
        self.assertEqual(first.data, {'prayed': True, 'prayed_count': 1})

        second = self.client.post(f"/api/prayer/requests/{created.data['id']}/pray/")
        self.assertEqual(second.data, {'prayed': False, 'prayed_count': 0})

    def test_respond_sends_inbox_message_and_notifies(self):
        created = self._create(self.youth, visibility=PrayerRequest.Visibility.LEADERS_ONLY)
        self.client.force_authenticate(self.leader)
        response = self.client.post(
            f"/api/prayer/requests/{created.data['id']}/respond/", {'body': 'Praying for you!'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Notification.objects.filter(person=self.youth, notification_type='PRAYER_RESPONSE_AVAILABLE').exists()
        )
