from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification

from .models import ContentItem

User = get_user_model()


class ContentVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345', school_year=11
        )
        self.other_youth = User.objects.create_user(
            username='youth2', email='youth2@example.com', password='pass12345', school_year=9
        )

    def test_youth_cannot_create_content(self):
        self.client.force_authenticate(self.youth)
        response = self.client.post('/api/content/', {'title': 'Sneaky post'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_draft_content_hidden_from_youth(self):
        ContentItem.objects.create(title='Draft post')
        self.client.force_authenticate(self.youth)
        response = self.client.get('/api/content/')
        self.assertEqual(response.data['count'], 0)

    def test_published_everyone_content_visible_to_youth(self):
        ContentItem.objects.create(title='Published post', status=ContentItem.Status.PUBLISHED)
        self.client.force_authenticate(self.youth)
        response = self.client.get('/api/content/')
        self.assertEqual(response.data['count'], 1)

    def test_school_year_targeting_restricts_visibility(self):
        ContentItem.objects.create(
            title='Year 11 retreat', status=ContentItem.Status.PUBLISHED,
            audience_everyone=False, audience_school_years=[11],
        )
        self.client.force_authenticate(self.youth)
        self.assertEqual(self.client.get('/api/content/').data['count'], 1)

        self.client.force_authenticate(self.other_youth)
        self.assertEqual(self.client.get('/api/content/').data['count'], 0)

    def test_publish_action_immediate(self):
        self.client.force_authenticate(self.leader)
        create_resp = self.client.post('/api/content/', {'title': 'Friday recap'}, format='json')
        response = self.client.post(f"/api/content/{create_resp.data['id']}/publish/")
        self.assertEqual(response.data['status'], 'PUBLISHED')

    def test_publish_action_schedules_future_publish_at(self):
        self.client.force_authenticate(self.leader)
        future = timezone.now() + timedelta(days=2)
        create_resp = self.client.post('/api/content/', {
            'title': 'Camp registration', 'publish_at': future.isoformat(),
        }, format='json')
        response = self.client.post(f"/api/content/{create_resp.data['id']}/publish/")
        self.assertEqual(response.data['status'], 'SCHEDULED')


class ContentScheduleCommandTests(TestCase):
    def test_publishes_when_due_and_expires_past_window(self):
        due = ContentItem.objects.create(
            title='Due now', status=ContentItem.Status.SCHEDULED,
            publish_at=timezone.now() - timedelta(minutes=5),
        )
        stale = ContentItem.objects.create(
            title='Old news', status=ContentItem.Status.PUBLISHED,
            expire_at=timezone.now() - timedelta(days=1),
        )
        not_yet = ContentItem.objects.create(
            title='Future post', status=ContentItem.Status.SCHEDULED,
            publish_at=timezone.now() + timedelta(days=1),
        )

        call_command('publish_scheduled_content')

        due.refresh_from_db()
        stale.refresh_from_db()
        not_yet.refresh_from_db()
        self.assertEqual(due.status, ContentItem.Status.PUBLISHED)
        self.assertEqual(stale.status, ContentItem.Status.EXPIRED)
        self.assertEqual(not_yet.status, ContentItem.Status.SCHEDULED)
        self.assertFalse(Notification.objects.filter(notification_type='CONTENT_PUBLISH_FAILED').exists())
