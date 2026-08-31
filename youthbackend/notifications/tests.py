from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .catalog import Category, NotificationType
from .models import DeviceToken, Notification, NotificationPreference
from .services import get_or_create_preference, notify

User = get_user_model()


class NotificationPreferenceTests(TestCase):
    def setUp(self):
        self.person = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )

    def test_preference_created_lazily_with_launch_defaults(self):
        preference = get_or_create_preference(self.person)
        self.assertTrue(preference.push_enabled)
        self.assertTrue(preference.email_enabled)
        self.assertTrue(NotificationPreference.objects.filter(person=self.person).exists())

    def test_category_default_respected(self):
        preference = get_or_create_preference(self.person)
        # GROUPS defaults to push off / email off.
        channels = preference.channels_for(Category.GROUPS)
        self.assertFalse(channels['push'])
        self.assertFalse(channels['email'])
        # EVENTS defaults to push on / email off.
        channels = preference.channels_for(Category.EVENTS)
        self.assertTrue(channels['push'])
        self.assertFalse(channels['email'])

    def test_category_override_wins_over_default(self):
        preference = get_or_create_preference(self.person)
        preference.category_overrides = {Category.EVENTS: {'push': False}}
        preference.save()
        channels = preference.channels_for(Category.EVENTS)
        self.assertFalse(channels['push'])

    def test_master_toggle_off_disables_every_category(self):
        preference = get_or_create_preference(self.person)
        preference.push_enabled = False
        preference.save()
        channels = preference.channels_for(Category.EVENTS)
        self.assertFalse(channels['push'])

    def test_quiet_hours_detects_overnight_window(self):
        preference = get_or_create_preference(self.person)
        preference.quiet_hours_start = time(21, 30)
        preference.quiet_hours_end = time(7, 0)
        preference.save()
        late_night = timezone.now().replace(hour=23, minute=0)
        midday = timezone.now().replace(hour=12, minute=0)
        self.assertTrue(preference.is_quiet_now(late_night))
        self.assertFalse(preference.is_quiet_now(midday))


class NotifyServiceTests(TestCase):
    def setUp(self):
        self.person = User.objects.create_user(
            username='youth2', email='youth2@example.com', password='pass12345'
        )

    def test_disabled_category_creates_no_notification(self):
        created = notify(
            self.person, Category.GROUPS, NotificationType.GROUP_ADDED,
            title='Added to group', body='',
        )
        self.assertEqual(created, [])
        self.assertEqual(Notification.objects.count(), 0)

    def test_enabled_category_dispatches_immediately(self):
        # FORMS defaults push+email both on, so this exercises both dispatch
        # paths in one go.
        created = notify(
            self.person, Category.FORMS, NotificationType.FORM_ASSIGNED,
            title='New form assigned', body='Please complete this form.',
        )
        self.assertEqual(len(created), 2)
        email_notification = Notification.objects.get(person=self.person, channel=Notification.Channel.EMAIL)
        self.assertEqual(email_notification.status, Notification.Status.SENT)
        self.assertIsNotNone(email_notification.sent_at)
        # No device token registered, so push is correctly skipped rather
        # than silently reported as sent.
        push_notification = Notification.objects.get(person=self.person, channel=Notification.Channel.PUSH)
        self.assertEqual(push_notification.status, Notification.Status.SKIPPED)

    def test_non_urgent_send_during_quiet_hours_is_deferred(self):
        preference = get_or_create_preference(self.person)
        preference.quiet_hours_enabled = True
        preference.quiet_hours_start = time(0, 0)
        preference.quiet_hours_end = time(23, 59)
        preference.save()

        created = notify(
            self.person, Category.EVENTS, NotificationType.EVENT_ANNOUNCED,
            title='Winter Camp', body='Details inside.', urgent=False,
        )
        self.assertEqual(len(created), 1)
        notification = Notification.objects.get(pk=created[0].pk)
        self.assertEqual(notification.status, Notification.Status.PENDING)
        self.assertGreater(notification.scheduled_at, timezone.now())

    def test_urgent_send_ignores_quiet_hours(self):
        DeviceToken.objects.create(person=self.person, token='tok-urgent', platform=DeviceToken.Platform.IOS)
        preference = get_or_create_preference(self.person)
        preference.quiet_hours_enabled = True
        preference.quiet_hours_start = time(0, 0)
        preference.quiet_hours_end = time(23, 59)
        preference.save()

        created = notify(
            self.person, Category.LEADER_ATTENDANCE, NotificationType.ATTENDANCE_RECONCILIATION_REMINDER,
            title='Still open', body='', urgent=True,
        )
        self.assertEqual(len(created), 1)
        notification = Notification.objects.get(pk=created[0].pk)
        self.assertEqual(notification.status, Notification.Status.SENT)


class NotificationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.person = User.objects.create_user(
            username='youth3', email='youth3@example.com', password='pass12345'
        )
        self.client.force_authenticate(self.person)

    def test_preferences_get_and_patch(self):
        response = self.client.get('/api/notifications/preferences/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            '/api/notifications/preferences/me/', {'email_enabled': False}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['email_enabled'])

    def test_device_token_registration_upserts(self):
        payload = {'token': 'expo-token-123', 'platform': 'IOS'}
        first = self.client.post('/api/notifications/device-tokens/', payload, format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post('/api/notifications/device-tokens/', payload, format='json')
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DeviceToken.objects.filter(token='expo-token-123').count(), 1)

    def test_inbox_list_and_mark_read(self):
        notify(
            self.person, Category.EVENTS, NotificationType.EVENT_ANNOUNCED,
            title='Winter Camp', body='Details inside.',
        )
        list_response = self.client.get('/api/notifications/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        notification_id = list_response.data['results'][0]['id']
        self.assertIsNone(list_response.data['results'][0]['read_at'])

        read_response = self.client.post(f'/api/notifications/{notification_id}/read/')
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(read_response.data['read_at'])

    def test_cannot_see_another_persons_notifications(self):
        other = User.objects.create_user(username='other', email='other@example.com', password='pass12345')
        notify(other, Category.EVENTS, NotificationType.EVENT_ANNOUNCED, title='Not yours', body='')
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.data['count'], 0)
