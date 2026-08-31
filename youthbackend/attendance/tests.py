from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from events.models import Event

User = get_user_model()


class AttendanceFlowTests(TestCase):
    """End-to-end sign-in/out/close rehearsal, matching the QR attendance
    spec's reconciliation requirement (cannot casually close with people
    still marked on site)."""

    def setUp(self):
        self.client = APIClient()
        self.leader = User.objects.create_user(
            username='leader', email='leader@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth1', email='youth1@example.com', password='pass12345'
        )
        self.event = Event.objects.create(name='Friday Youth', starts_at=timezone.now())

    def test_youth_cannot_open_session(self):
        self.client.force_authenticate(self.youth)
        response = self.client.post('/api/attendance/sessions/', {'event': self.event.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_full_sign_in_sign_out_cycle(self):
        self.client.force_authenticate(self.leader)

        open_resp = self.client.post('/api/attendance/sessions/', {'event': self.event.id}, format='json')
        self.assertEqual(open_resp.status_code, status.HTTP_201_CREATED)
        session_id = open_resp.data['id']

        sign_in_resp = self.client.post(
            f'/api/attendance/sessions/{session_id}/sign-in/',
            {'qr_token': self.youth.qr_token, 'source': 'QR'},
            format='json',
        )
        self.assertEqual(sign_in_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(sign_in_resp.data['result'], 'SIGNED_IN')

        duplicate_resp = self.client.post(
            f'/api/attendance/sessions/{session_id}/sign-in/',
            {'qr_token': self.youth.qr_token, 'source': 'QR'},
            format='json',
        )
        self.assertEqual(duplicate_resp.data['result'], 'ALREADY_SIGNED_IN')

        live_resp = self.client.get(f'/api/attendance/sessions/{session_id}/live/')
        self.assertEqual(live_resp.data['currently_on_site'], 1)

        blocked_close = self.client.post(f'/api/attendance/sessions/{session_id}/close/', {}, format='json')
        self.assertEqual(blocked_close.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(blocked_close.data['code'], 'REMAINING_ON_SITE')

        sign_out_resp = self.client.post(
            f'/api/attendance/sessions/{session_id}/sign-out/',
            {'qr_token': self.youth.qr_token, 'source': 'QR'},
            format='json',
        )
        self.assertEqual(sign_out_resp.status_code, status.HTTP_200_OK)

        final_close = self.client.post(f'/api/attendance/sessions/{session_id}/close/', {}, format='json')
        self.assertEqual(final_close.status_code, status.HTTP_200_OK)
        self.assertEqual(final_close.data['status'], 'CLOSED')
