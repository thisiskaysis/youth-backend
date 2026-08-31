from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification

from .models import FormAssignment, FormDefinition

User = get_user_model()


class FormWorkflowTests(TestCase):
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

    def _create_form(self):
        self.client.force_authenticate(self.leader)
        return self.client.post('/api/forms/definitions/', {
            'title': 'Camp Consent Form', 'description': 'Required for camp.',
        }, format='json')

    def test_youth_cannot_create_form_definition(self):
        self.client.force_authenticate(self.youth)
        response = self.client.post('/api/forms/definitions/', {'title': 'Sneaky Form'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assign_creates_assignment_and_notifies(self):
        form = self._create_form()
        response = self.client.post(f"/api/forms/definitions/{form.data['id']}/assign/", {
            'person_ids': [self.youth.id],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 1)
        self.assertTrue(
            Notification.objects.filter(person=self.youth, notification_type='FORM_ASSIGNED').exists()
        )

    def test_assign_is_idempotent_no_duplicate(self):
        form = self._create_form()
        self.client.post(f"/api/forms/definitions/{form.data['id']}/assign/", {
            'person_ids': [self.youth.id],
        }, format='json')
        second = self.client.post(f"/api/forms/definitions/{form.data['id']}/assign/", {
            'person_ids': [self.youth.id],
        }, format='json')
        self.assertEqual(second.data, [])
        self.assertEqual(FormAssignment.objects.filter(form_id=form.data['id'], person=self.youth).count(), 1)

    def test_assigned_person_can_submit_but_not_twice(self):
        form = self._create_form()
        self.client.post(f"/api/forms/definitions/{form.data['id']}/assign/", {
            'person_ids': [self.youth.id],
        }, format='json')
        assignment = FormAssignment.objects.get(form_id=form.data['id'], person=self.youth)

        self.client.force_authenticate(self.youth)
        response = self.client.post(f'/api/forms/assignments/{assignment.id}/submit/', {
            'answers': {'medical_notes': 'None'},
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'SUBMITTED')

        again = self.client.post(f'/api/forms/assignments/{assignment.id}/submit/', {}, format='json')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(again.data['code'], 'ALREADY_SUBMITTED')

    def test_cannot_submit_others_assignment(self):
        form = self._create_form()
        self.client.post(f"/api/forms/definitions/{form.data['id']}/assign/", {
            'person_ids': [self.youth.id],
        }, format='json')
        assignment = FormAssignment.objects.get(form_id=form.data['id'], person=self.youth)

        self.client.force_authenticate(self.other_youth)
        response = self.client.post(f'/api/forms/assignments/{assignment.id}/submit/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_youth_only_sees_own_assignments(self):
        form = self._create_form()
        self.client.post(f"/api/forms/definitions/{form.data['id']}/assign/", {
            'person_ids': [self.youth.id, self.other_youth.id],
        }, format='json')

        self.client.force_authenticate(self.youth)
        response = self.client.get('/api/forms/assignments/')
        self.assertEqual(len(response.data['results']), 1)

        self.client.force_authenticate(self.leader)
        response = self.client.get('/api/forms/assignments/')
        self.assertEqual(len(response.data['results']), 2)


class FormReminderCommandTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(
            username='leader2', email='leader2@example.com', password='pass12345', role=User.Role.LEADER
        )
        self.youth = User.objects.create_user(
            username='youth3', email='youth3@example.com', password='pass12345'
        )
        self.form = FormDefinition.objects.create(title='Consent Form', created_by=self.leader)

    def test_due_soon_and_overdue_reminders(self):
        other_form = FormDefinition.objects.create(title='Photo Permission', created_by=self.leader)
        due_soon = FormAssignment.objects.create(
            form=self.form, person=self.youth, due_at=timezone.now() + timezone.timedelta(hours=24),
        )
        overdue = FormAssignment.objects.create(
            form=other_form, person=self.youth, due_at=timezone.now() - timezone.timedelta(days=1),
        )

        call_command('send_form_reminders')
        self.assertTrue(
            Notification.objects.filter(
                person=self.youth, notification_type='FORM_DUE_REMINDER', data__assignment_id=due_soon.id
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                person=self.youth, notification_type='FORM_OVERDUE', data__assignment_id=overdue.id
            ).exists()
        )

        call_command('send_form_reminders')
        # FORMS defaults to both push+email, so one triggered reminder
        # produces two Notification rows (one per channel).
        self.assertEqual(
            Notification.objects.filter(notification_type='FORM_DUE_REMINDER', data__assignment_id=due_soon.id).count(), 2
        )
