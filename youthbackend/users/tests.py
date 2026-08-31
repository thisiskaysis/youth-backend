from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import User
from .serializers import UserSerializer


class UserRegistrationSecurityTests(TestCase):
    """Registration must never allow mass-assignment of role/status/
    superuser flags - every sign-up becomes an ordinary Youth account."""

    def setUp(self):
        self.client = APIClient()

    def test_registration_ignores_role_and_privilege_fields(self):
        response = self.client.post('/api/users/', {
            'username': 'sneaky',
            'email': 'sneaky@example.com',
            'password': 'supersecret123',
            'first_name': 'Sneaky',
            'last_name': 'User',
            'role': User.Role.ADMIN,
            'status': User.Status.ACTIVE,
            'is_superuser': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='sneaky')
        self.assertEqual(user.role, User.Role.YOUTH)
        self.assertFalse(user.is_superuser)

    def test_registration_requires_minimum_password_length(self):
        response = self.client.post('/api/users/', {
            'username': 'shortpw',
            'email': 'shortpw@example.com',
            'password': '123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserSelfUpdateSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )
        self.client.force_authenticate(self.youth)

    def test_self_cannot_escalate_own_role(self):
        response = self.client.put(
            f'/api/users/{self.youth.id}/', {'role': User.Role.ADMIN}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.youth.refresh_from_db()
        self.assertEqual(self.youth.role, User.Role.YOUTH)

    def test_self_can_update_allowed_fields(self):
        response = self.client.put(
            f'/api/users/{self.youth.id}/', {'first_name': 'Updated'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.youth.refresh_from_db()
        self.assertEqual(self.youth.first_name, 'Updated')

    def test_people_list_forbidden_for_youth(self):
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UserSerializerExposureTests(TestCase):
    def test_qr_token_excluded_from_general_serializer(self):
        youth = User.objects.create_user(
            username='youth2', email='youth2@example.com', password='pass12345'
        )
        data = UserSerializer(youth).data
        self.assertNotIn('qr_token', data)
