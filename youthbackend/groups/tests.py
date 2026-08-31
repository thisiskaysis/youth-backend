from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import Group, GroupMembership

User = get_user_model()


class GroupMembershipPermissionTests(TestCase):
    """A Leader may only manage membership for groups they actually lead -
    generic Leader status alone must not grant cross-group access."""

    def setUp(self):
        self.client = APIClient()
        self.leader_a = User.objects.create_user(
            username='leadera', email='leadera@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.leader_b = User.objects.create_user(
            username='leaderb', email='leaderb@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )

        self.group_a = Group.objects.create(name='Group A', group_type=Group.GroupType.CONNECT)
        GroupMembership.objects.create(
            group=self.group_a, person=self.leader_a, membership_role=GroupMembership.MembershipRole.LEADER
        )
        self.group_b = Group.objects.create(name='Group B', group_type=Group.GroupType.CONNECT)
        GroupMembership.objects.create(
            group=self.group_b, person=self.leader_b, membership_role=GroupMembership.MembershipRole.LEADER
        )

    def test_leader_cannot_add_member_to_group_they_dont_lead(self):
        self.client.force_authenticate(self.leader_b)
        response = self.client.post('/api/groups/memberships/', {
            'group': self.group_a.id,
            'person_id': self.youth.id,
            'membership_role': 'MEMBER',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_leader_can_add_member_to_own_group(self):
        self.client.force_authenticate(self.leader_a)
        response = self.client.post('/api/groups/memberships/', {
            'group': self.group_a.id,
            'person_id': self.youth.id,
            'membership_role': 'MEMBER',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            GroupMembership.objects.filter(group=self.group_a, person=self.youth, is_active=True).exists()
        )
