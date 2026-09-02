from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from groups.models import Group, GroupMembership
from notifications.models import Notification

from .models import InboxMessage

User = get_user_model()


class InboxMessageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.other_leader = User.objects.create_user(
            username='other_leader', email='other_leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.admin = User.objects.create_user(
            username='admin', email='admin@example.com', password='pass12345', role=User.Role.ADMIN
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

    def send(self, recipient, body='Hi there!'):
        return self.client.post('/api/inbox/messages/', {
            'recipient_id': recipient.id, 'body': body,
        }, format='json')

    def test_leader_can_message_managed_person(self):
        self.client.force_authenticate(self.leader)
        response = self.send(self.managed_youth)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Notification.objects.filter(person=self.managed_youth, notification_type='MESSAGE_RECEIVED').exists()
        )

    def test_leader_can_message_person_outside_their_groups(self):
        # Leaders/admins may contact everyone, not just people they manage.
        self.client.force_authenticate(self.leader)
        response = self.send(self.other_youth)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_can_message_anyone(self):
        self.client.force_authenticate(self.admin)
        response = self.send(self.other_youth)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_youth_can_message_connected_leader(self):
        self.client.force_authenticate(self.managed_youth)
        response = self.send(self.leader)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_youth_cannot_message_unconnected_leader(self):
        self.client.force_authenticate(self.managed_youth)
        response = self.send(self.other_leader)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_youth_cannot_message_another_youth(self):
        self.client.force_authenticate(self.managed_youth)
        response = self.send(self.other_youth)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_message_self(self):
        self.client.force_authenticate(self.managed_youth)
        response = self.send(self.managed_youth)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_youth_can_reply_once_a_conversation_exists(self):
        # An unconnected leader reaches out first (e.g. a prayer response) -
        # the youth may then reply even though they aren't "connected".
        self.client.force_authenticate(self.other_leader)
        first = self.send(self.managed_youth, 'Praying for you.')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(self.managed_youth)
        reply = self.send(self.other_leader, 'Thank you!')
        self.assertEqual(reply.status_code, status.HTTP_201_CREATED)

    def test_recipient_can_mark_read_but_others_cannot(self):
        self.client.force_authenticate(self.leader)
        create_resp = self.send(self.managed_youth)
        message_id = create_resp.data['id']

        self.client.force_authenticate(self.other_youth)
        denied = self.client.post(f'/api/inbox/messages/{message_id}/read/')
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(self.managed_youth)
        allowed = self.client.post(f'/api/inbox/messages/{message_id}/read/')
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(allowed.data['read_at'])

    def test_thread_view_is_chronological_and_marks_read(self):
        self.client.force_authenticate(self.leader)
        self.send(self.managed_youth, 'First!')
        self.client.force_authenticate(self.managed_youth)
        self.send(self.leader, 'Second!')

        self.client.force_authenticate(self.leader)
        thread = self.client.get('/api/inbox/messages/', {'with': self.managed_youth.id})
        bodies = [message['body'] for message in thread.data['results']]
        self.assertEqual(bodies, ['First!', 'Second!'])

        # Opening the thread marked the youth's reply read.
        message = InboxMessage.objects.get(sender=self.managed_youth, recipient=self.leader)
        self.assertIsNotNone(message.read_at)

    def test_conversations_list_has_last_message_and_unread_count(self):
        self.client.force_authenticate(self.leader)
        self.send(self.managed_youth, 'First!')
        self.send(self.managed_youth, 'Second!')

        self.client.force_authenticate(self.managed_youth)
        response = self.client.get('/api/inbox/messages/conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        conversation = response.data[0]
        self.assertEqual(conversation['participant']['id'], self.leader.id)
        self.assertEqual(conversation['last_message']['body'], 'Second!')
        self.assertEqual(conversation['unread_count'], 2)

    def test_contacts_scoped_by_role(self):
        self.client.force_authenticate(self.managed_youth)
        response = self.client.get('/api/inbox/messages/contacts/')
        contact_ids = {person['id'] for person in response.data['results']}
        self.assertIn(self.leader.id, contact_ids)
        self.assertNotIn(self.other_leader.id, contact_ids)
        self.assertNotIn(self.other_youth.id, contact_ids)

        self.client.force_authenticate(self.leader)
        response = self.client.get('/api/inbox/messages/contacts/')
        contact_ids = {person['id'] for person in response.data['results']}
        self.assertIn(self.other_youth.id, contact_ids)
        self.assertIn(self.managed_youth.id, contact_ids)

