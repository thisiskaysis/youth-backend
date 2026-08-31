"""Leader-facing reminder that an attendance session is still open with
people marked ON SITE at/after its event's scheduled end (NOTIFICATIONS.xlsx
sheet 03/04). Intended to run on a short interval via cron; each threshold
is only ever sent once per session, detected by checking for a prior
Notification with the same type/session rather than a dedicated flag field.

There's no per-session "attendance manager" assignment yet, so this
notifies every Leader/Pastor rather than a scoped subset - see repo memory
(architecture.md) for that simplification.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import AttendanceSession
from notifications.catalog import Category, NotificationType
from notifications.models import Notification
from notifications.services import notify

User = get_user_model()

RECONCILIATION_THRESHOLD_MINUTES = 15
NOT_CLOSED_THRESHOLD_MINUTES = 45


class Command(BaseCommand):
    help = 'Remind Leaders/Pastors about attendance sessions still open with people on site.'

    def handle(self, *args, **options):
        now = timezone.now()
        sent = 0

        sessions = AttendanceSession.objects.filter(
            status=AttendanceSession.Status.OPEN,
            event__ends_at__isnull=False,
            event__ends_at__lte=now,
        ).select_related('event')

        for session in sessions:
            minutes_since_end = (now - session.event.ends_at).total_seconds() / 60
            on_site_count = session.records.filter(
                signed_in_at__isnull=False, signed_out_at__isnull=True
            ).count()
            if on_site_count == 0:
                continue

            if minutes_since_end >= NOT_CLOSED_THRESHOLD_MINUTES:
                notification_type = NotificationType.ATTENDANCE_NOT_CLOSED
            elif minutes_since_end >= RECONCILIATION_THRESHOLD_MINUTES:
                notification_type = NotificationType.ATTENDANCE_RECONCILIATION_REMINDER
            else:
                continue

            already_sent = Notification.objects.filter(
                notification_type=notification_type, data__session_id=session.id
            ).exists()
            if already_sent:
                continue

            staff = User.objects.filter(role__in=[User.Role.LEADER, User.Role.PASTOR])
            for person in staff:
                notify(
                    person, Category.LEADER_ATTENDANCE, notification_type,
                    title='Attendance session still open',
                    body=f'{session.event.name}: {on_site_count} still marked on site.',
                    deep_link_type='attendance_session', deep_link_id=session.id,
                    data={'session_id': session.id, 'on_site_count': on_site_count},
                    urgent=True,
                )
                sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} attendance reminder notification(s).'))
