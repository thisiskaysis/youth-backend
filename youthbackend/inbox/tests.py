from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from groups.models import Group, GroupMembership
from notifications.models import Notification

User = get_user_model()


class InboxMessageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.managed_youth = User.objects.create_user(
            username='managed', email='managed@example.com', password='pass12345'
        )
        self.other_youth = User.objects.create_user(
            username='other', email='other@example.com', password='pass12345'
        )
        group = Group.objects.create(name='Connect', group_type=Group.GroupType.CONNECT)
        GroupMembership.objects.create(group=group, person=self.leader, membership_role=GroupMembership.MembershipRole.LEADER)
        GroupMembership.objects.create(group=group, person=self.managed_youth)

    def test_leader_can_message_managed_person(self):
        self.client.force_authenticate(self.leader)
        response = self.client.post('/api/inbox/messages/', {
            'recipient_id': self.managed_youth.id, 'body': 'Hi there!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Notification.objects.filter(person=self.managed_youth, notification_type='MESSAGE_RECEIVED').exists()
        )

    def test_leader_cannot_message_unmanaged_person(self):
        self.client.force_authenticate(self.leader)
        response = self.client.post('/api/inbox/messages/', {
            'recipient_id': self.other_youth.id, 'body': 'Hi there!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_youth_cannot_send_message(self):
        self.client.force_authenticate(self.managed_youth)
        response = self.client.post('/api/inbox/messages/', {
            'recipient_id': self.other_youth.id, 'body': 'Hi!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_recipient_can_mark_read_but_others_cannot(self):
        self.client.force_authenticate(self.leader)
        create_resp = self.client.post('/api/inbox/messages/', {
            'recipient_id': self.managed_youth.id, 'body': 'Hi there!',
        }, format='json')
        message_id = create_resp.data['id']

        self.client.force_authenticate(self.other_youth)
        denied = self.client.post(f'/api/inbox/messages/{message_id}/read/')
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(self.managed_youth)
        allowed = self.client.post(f'/api/inbox/messages/{message_id}/read/')
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(allowed.data['read_at'])
