from accounts.tasks import send_revisit_reminders
from config.monitored_command import MonitoredCommand


class Command(MonitoredCommand):
    help = "Send email reminders for due/overdue revisit schedules."
    sentry_monitor_slug = "sponda-revisit-reminders"

    def run(self, *args, **options):
        sent_count = send_revisit_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} revisit reminder(s)."))
