from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification

from .models import RideRequest

User = get_user_model()


class RideRequestTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )
        self.other_youth = User.objects.create_user(
            username='youth2', email='youth2@example.com', password='pass12345'
        )

    def _create_ride(self):
        self.client.force_authenticate(self.youth)
        return self.client.post('/api/rides/requests/', {
            'direction': RideRequest.Direction.HOME, 'area': 'Northside',
        }, format='json')

    def test_create_ride_notifies_leaders(self):
        response = self._create_ride()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'REQUESTED')
        self.assertTrue(
            Notification.objects.filter(person=self.leader, notification_type='RIDE_REQUEST_NEW').exists()
        )

    def test_youth_only_sees_own_rides(self):
        self._create_ride()
        self.client.force_authenticate(self.other_youth)
        response = self.client.get('/api/rides/requests/')
        self.assertEqual(len(response.data['results']), 0)

    def test_youth_cannot_update_ride_status(self):
        created = self._create_ride()
        response = self.client.patch(f"/api/rides/requests/{created.data['id']}/", {'status': 'CONFIRMED'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_leader_confirms_ride_notifies_person(self):
        created = self._create_ride()
        self.client.force_authenticate(self.leader)
        response = self.client.patch(
            f"/api/rides/requests/{created.data['id']}/", {'status': 'CONFIRMED'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Notification.objects.filter(person=self.youth, notification_type='RIDE_CONFIRMED').exists()
        )

    def test_leader_cancels_ride_notifies_person_urgently(self):
        created = self._create_ride()
        self.client.force_authenticate(self.leader)
        response = self.client.patch(
            f"/api/rides/requests/{created.data['id']}/", {'status': 'CANCELLED'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # RIDES defaults to both push+email, so one notify() call fans out
        # to two rows - assert on the push one specifically.
        notification = Notification.objects.get(
            person=self.youth, notification_type='RIDE_CHANGED_CANCELLED', channel=Notification.Channel.PUSH,
        )
        # Urgent dispatch is attempted immediately; SKIPPED (not PENDING) confirms that, since no device token is registered.
        self.assertEqual(notification.status, Notification.Status.SKIPPED)
