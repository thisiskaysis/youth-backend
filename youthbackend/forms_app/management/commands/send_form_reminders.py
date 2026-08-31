"""Form/consent due reminders (NOTIFICATIONS.xlsx sheets 02/04): 7 days
before due, 48 hours before due, then once the morning after overdue.
Cron-able. Idempotency is stage-aware: if an assignment is already within
the 48h window the first time the command ever sees it (e.g. assigned
late, or the command missed a run), we send only the most urgent
applicable stage rather than firing the 7-day reminder retroactively and
then the 48-hour one moments later.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.catalog import Category, NotificationType
from notifications.models import Notification
from notifications.services import notify

from ...models import FormAssignment

# Most urgent first - the first one whose window matches "now" wins.
STAGE_WINDOWS = [
    ('48h', timezone.timedelta(hours=48)),
    ('7d', timezone.timedelta(days=7)),
]
STAGE_RANK = {stage: rank for rank, (stage, _window) in enumerate(reversed(STAGE_WINDOWS))}


def _most_urgent_stage_sent(assignment_id):
    sent_stages = set(
        Notification.objects.filter(
            notification_type=NotificationType.FORM_DUE_REMINDER, data__assignment_id=assignment_id,
        ).values_list('data__stage', flat=True)
    )
    applicable = [stage for stage, _ in STAGE_WINDOWS if stage in sent_stages]
    return applicable[0] if applicable else None


class Command(BaseCommand):
    help = 'Send outstanding form/consent due and overdue reminders.'

    def handle(self, *args, **options):
        now = timezone.now()
        sent = 0

        outstanding = FormAssignment.objects.filter(
            status=FormAssignment.Status.OUTSTANDING, due_at__isnull=False,
        ).select_related('form', 'person')

        for assignment in outstanding:
            if assignment.due_at <= now:
                if Notification.objects.filter(
                    notification_type=NotificationType.FORM_OVERDUE, data__assignment_id=assignment.id
                ).exists():
                    continue
                notify(
                    assignment.person, Category.FORMS, NotificationType.FORM_OVERDUE,
                    title=f'Overdue: {assignment.form.title}',
                    body='This form is now overdue - please complete it as soon as possible.',
                    deep_link_type='form_assignment', deep_link_id=assignment.id,
                    data={'assignment_id': assignment.id, 'stage': 'overdue'},
                )
                sent += 1
                continue

            applicable_stage = next(
                (stage for stage, window in STAGE_WINDOWS if assignment.due_at - now <= window), None
            )
            if applicable_stage is None:
                continue

            already_sent = _most_urgent_stage_sent(assignment.id)
            if already_sent is not None and STAGE_RANK[already_sent] >= STAGE_RANK[applicable_stage]:
                continue

            notify(
                assignment.person, Category.FORMS, NotificationType.FORM_DUE_REMINDER,
                title=f'Due soon: {assignment.form.title}',
                body=f'Due {assignment.due_at:%a %d %b}.',
                deep_link_type='form_assignment', deep_link_id=assignment.id,
                data={'assignment_id': assignment.id, 'stage': applicable_stage},
            )
            sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} form reminder notification(s).'))
