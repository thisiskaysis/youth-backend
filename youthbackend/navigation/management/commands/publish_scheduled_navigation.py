from django.core.management.base import BaseCommand

from ...services import process_scheduled


class Command(BaseCommand):
    help = 'Publish scheduled navigation items and expire ones past their expire_at.'

    def handle(self, *args, **options):
        result = process_scheduled()
        self.stdout.write(self.style.SUCCESS(
            f"Published {result['published']}, expired {result['expired']}, failed {result['failed']}."
        ))
