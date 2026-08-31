from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification

from .models import Event

User = get_user_model()


class EventPublishNotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )
        self.client.force_authenticate(self.leader)

    def test_creating_a_draft_event_sends_no_notifications(self):
        response = self.client.post('/api/events/', {
            'name': 'Winter Camp', 'starts_at': timezone.now() + timedelta(days=7),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Notification.objects.count(), 0)

    def test_publish_without_notify_flag_sends_nothing(self):
        event = Event.objects.create(name='Winter Camp', starts_at=timezone.now() + timedelta(days=7))
        response = self.client.post(f'/api/events/{event.id}/publish/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Event.Status.PUBLISHED)
        self.assertEqual(Notification.objects.count(), 0)

    def test_publish_with_notify_flag_notifies_everyone_audience(self):
        event = Event.objects.create(
            name='Winter Camp', starts_at=timezone.now() + timedelta(days=7), audience_everyone=True
        )
        response = self.client.post(
            f'/api/events/{event.id}/publish/', {'notify': True}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Notification.objects.filter(person=self.youth, notification_type='EVENT_ANNOUNCED').exists())

    def test_changing_published_event_time_notifies_audience(self):
        event = Event.objects.create(
            name='Winter Camp', starts_at=timezone.now() + timedelta(days=7),
            audience_everyone=True, status=Event.Status.PUBLISHED,
        )
        response = self.client.patch(f'/api/events/{event.id}/', {
            'starts_at': timezone.now() + timedelta(days=8),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Notification.objects.filter(person=self.youth, notification_type='EVENT_CHANGED_CANCELLED').exists()
        )

    def test_changing_draft_event_does_not_notify(self):
        event = Event.objects.create(
            name='Winter Camp', starts_at=timezone.now() + timedelta(days=7), audience_everyone=True,
        )
        response = self.client.patch(f'/api/events/{event.id}/', {
            'starts_at': timezone.now() + timedelta(days=8),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.count(), 0)
