"""Decision follow-up reminders (NOTIFICATIONS.xlsx sheets 03/04): due
reminder ~24h before due_at, then overdue once it passes. Cron-able.

Uses a 'stage' key in Notification.data (assigned/due_soon/overdue) so
the immediate "you've been assigned" notice from assign_follow_up() never
collides with this command's own idempotency checks - see the
send_form_reminders stage-ordering write-up in roadmap-status.md for why
that distinction matters.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.catalog import Category, NotificationType
from notifications.models import Notification
from notifications.services import notify

from ...models import FollowUp

DUE_SOON_WINDOW = timezone.timedelta(hours=24)


def _already_sent(notification_type, follow_up_id, stage):
    return Notification.objects.filter(
        notification_type=notification_type, data__follow_up_id=follow_up_id, data__stage=stage,
    ).exists()


class Command(BaseCommand):
    help = 'Send decision follow-up due-soon and overdue reminders.'

    def handle(self, *args, **options):
        now = timezone.now()
        sent = 0

        open_follow_ups = FollowUp.objects.exclude(status=FollowUp.Status.COMPLETED).filter(
            due_at__isnull=False,
        ).select_related('decision__person', 'assignee')

        for follow_up in open_follow_ups:
            if follow_up.due_at <= now:
                if _already_sent(NotificationType.FOLLOWUP_OVERDUE, follow_up.id, 'overdue'):
                    continue
                notify(
                    follow_up.assignee, Category.LEADER_FOLLOWUP, NotificationType.FOLLOWUP_OVERDUE,
                    title='Follow-up overdue',
                    body=f'Follow-up for {follow_up.decision.person} is overdue.',
                    deep_link_type='follow_up', deep_link_id=follow_up.id,
                    data={'follow_up_id': follow_up.id, 'stage': 'overdue'}, urgent=True,
                )
                sent += 1
                continue

            if follow_up.due_at - now <= DUE_SOON_WINDOW:
                if _already_sent(NotificationType.FOLLOWUP_DUE, follow_up.id, 'due_soon'):
                    continue
                notify(
                    follow_up.assignee, Category.LEADER_FOLLOWUP, NotificationType.FOLLOWUP_DUE,
                    title='Follow-up due soon',
                    body=f'Follow-up for {follow_up.decision.person} is due soon.',
                    deep_link_type='follow_up', deep_link_id=follow_up.id,
                    data={'follow_up_id': follow_up.id, 'stage': 'due_soon'},
                )
                sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} follow-up reminder notification(s).'))
