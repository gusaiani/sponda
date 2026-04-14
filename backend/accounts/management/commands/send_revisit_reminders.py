from django.core.management.base import BaseCommand

from accounts.tasks import send_revisit_reminders


class Command(BaseCommand):
    help = "Send email reminders for due/overdue revisit schedules."

    def handle(self, *args, **options):
        sent_count = send_revisit_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} revisit reminder(s)."))
