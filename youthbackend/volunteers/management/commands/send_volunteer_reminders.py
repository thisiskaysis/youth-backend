"""Volunteer-facing serving reminders (NOTIFICATIONS.xlsx sheet 04).
Cron-able; each reminder type is sent at most once per assignment, detected
via an existing Notification with a matching type + assignment id rather
than a dedicated flag field (same pattern as send_attendance_reminders).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.catalog import Category, NotificationType
from notifications.models import Notification
from notifications.services import notify

from ...models import VolunteerAssignment

PENDING_REMINDER_AFTER_HOURS = 48
SERVING_SOON_BEFORE_HOURS = 48
SERVING_TODAY_WITHIN_HOURS = 12


def _already_sent(notification_type, assignment_id):
    return Notification.objects.filter(
        notification_type=notification_type, data__assignment_id=assignment_id
    ).exists()


class Command(BaseCommand):
    help = 'Send volunteer serving reminders for pending/upcoming roster assignments.'

    def handle(self, *args, **options):
        now = timezone.now()
        sent = 0

        pending_cutoff = now - timezone.timedelta(hours=PENDING_REMINDER_AFTER_HOURS)
        pending = VolunteerAssignment.objects.filter(
            status=VolunteerAssignment.Status.PENDING, requested_at__lte=pending_cutoff,
        ).select_related('position', 'roster__event', 'person')
        for assignment in pending:
            if _already_sent(NotificationType.VOLUNTEER_RESPONSE_REMINDER, assignment.id):
                continue
            notify(
                assignment.person, Category.VOLUNTEER_REMINDERS, NotificationType.VOLUNTEER_RESPONSE_REMINDER,
                title=f'Still waiting on your response: {assignment.position.name}',
                body=f'{assignment.roster.event.name} needs to know if you can serve.',
                deep_link_type='volunteer_assignment', deep_link_id=assignment.id,
                data={'assignment_id': assignment.id},
            )
            sent += 1

        accepted = VolunteerAssignment.objects.filter(
            status=VolunteerAssignment.Status.ACCEPTED,
        ).select_related('position', 'roster__event', 'person')
        for assignment in accepted:
            call_time = assignment.call_start or assignment.roster.event.starts_at
            hours_until = (call_time - now).total_seconds() / 3600
            if hours_until < 0:
                continue

            if hours_until <= SERVING_TODAY_WITHIN_HOURS:
                notification_type = NotificationType.VOLUNTEER_SERVING_TODAY
            elif hours_until <= SERVING_SOON_BEFORE_HOURS:
                notification_type = NotificationType.VOLUNTEER_SERVING_SOON
            else:
                continue

            if _already_sent(notification_type, assignment.id):
                continue
            notify(
                assignment.person, Category.VOLUNTEER_REMINDERS, notification_type,
                title=f"You're serving: {assignment.position.name}",
                body=f'{assignment.roster.event.name} - call time {call_time:%a %d %b, %I:%M %p}.',
                deep_link_type='volunteer_assignment', deep_link_id=assignment.id,
                data={'assignment_id': assignment.id},
            )
            sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} volunteer reminder notification(s).'))
