from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import NavigationItem

User = get_user_model()


class NavigationVisibilityAndOrderingTests(TestCase):
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

    def test_youth_only_sees_published_items(self):
        NavigationItem.objects.create(
            label='Draft item', destination_type=NavigationItem.DestinationType.INTERNAL_SCREEN,
            destination_value='home',
        )
        NavigationItem.objects.create(
            label='Live item', destination_type=NavigationItem.DestinationType.INTERNAL_SCREEN,
            destination_value='events', status=NavigationItem.Status.PUBLISHED,
        )
        self.client.force_authenticate(self.youth)
        response = self.client.get('/api/navigation/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['label'], 'Live item')

    def test_new_item_gets_next_sort_order(self):
        self.client.force_authenticate(self.leader)
        first = self.client.post('/api/navigation/', {
            'label': 'First', 'destination_type': 'INTERNAL_SCREEN', 'destination_value': 'home',
        }, format='json')
        second = self.client.post('/api/navigation/', {
            'label': 'Second', 'destination_type': 'INTERNAL_SCREEN', 'destination_value': 'events',
        }, format='json')
        self.assertLess(first.data['sort_order'], second.data['sort_order'])

    def test_reorder_updates_sort_order(self):
        self.client.force_authenticate(self.leader)
        a = self.client.post('/api/navigation/', {
            'label': 'A', 'destination_type': 'INTERNAL_SCREEN', 'destination_value': 'a',
        }, format='json').data
        b = self.client.post('/api/navigation/', {
            'label': 'B', 'destination_type': 'INTERNAL_SCREEN', 'destination_value': 'b',
        }, format='json').data

        response = self.client.patch('/api/navigation/reorder/', {
            'ordered_ids': [b['id'], a['id']],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['label'], 'B')
        self.assertEqual(response.data[1]['label'], 'A')

    def test_only_admin_can_create_protected_item(self):
        self.client.force_authenticate(self.leader)
        response = self.client.post('/api/navigation/', {
            'label': 'Core', 'destination_type': 'INTERNAL_SCREEN', 'destination_value': 'home',
            'is_protected': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/navigation/', {
            'label': 'Core', 'destination_type': 'INTERNAL_SCREEN', 'destination_value': 'home',
            'is_protected': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_protected_item_cannot_be_deleted_even_by_admin(self):
        item = NavigationItem.objects.create(
            label='Core', destination_type=NavigationItem.DestinationType.INTERNAL_SCREEN,
            destination_value='home', is_protected=True,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.delete(f'/api/navigation/{item.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(NavigationItem.objects.filter(pk=item.id).exists())

    def test_leader_cannot_change_protection_flag(self):
        item = NavigationItem.objects.create(
            label='Item', destination_type=NavigationItem.DestinationType.INTERNAL_SCREEN, destination_value='home',
        )
        self.client.force_authenticate(self.leader)
        response = self.client.patch(f'/api/navigation/{item.id}/', {'is_protected': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_external_url_must_be_valid(self):
        self.client.force_authenticate(self.leader)
        response = self.client.post('/api/navigation/', {
            'label': 'Sign up', 'destination_type': 'EXTERNAL_URL', 'destination_value': 'not-a-url',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_event_destination_requires_destination_id(self):
        self.client.force_authenticate(self.leader)
        response = self.client.post('/api/navigation/', {
            'label': 'Winter Camp', 'destination_type': 'EVENT',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class NavigationScheduleCommandTests(TestCase):
    def test_publishes_when_due_and_expires_past_window(self):
        due = NavigationItem.objects.create(
            label='Due now', destination_type=NavigationItem.DestinationType.INTERNAL_SCREEN,
            destination_value='home', status=NavigationItem.Status.SCHEDULED,
            publish_at=timezone.now() - timedelta(minutes=5),
        )
        stale = NavigationItem.objects.create(
            label='Old link', destination_type=NavigationItem.DestinationType.INTERNAL_SCREEN,
            destination_value='home', status=NavigationItem.Status.PUBLISHED,
            expire_at=timezone.now() - timedelta(days=1),
        )

        call_command('publish_scheduled_navigation')

        due.refresh_from_db()
        stale.refresh_from_db()
        self.assertEqual(due.status, NavigationItem.Status.PUBLISHED)
        self.assertEqual(stale.status, NavigationItem.Status.EXPIRED)
