from django.core.management.base import BaseCommand

from notifications.services import dispatch_due_notifications


class Command(BaseCommand):
    help = (
        'Dispatch PENDING notifications whose scheduled_at has passed. '
        'Intended to run on a short interval (e.g. every minute) via cron/systemd timer.'
    )

    def handle(self, *args, **options):
        sent = dispatch_due_notifications()
        self.stdout.write(self.style.SUCCESS(f'Dispatched {sent} notification(s).'))
