"""Evaluate every active :class:`IndicatorAlert` against the latest snapshots.

Runs from a systemd timer right after ``refresh_indicator_snapshots`` so the
alerts always compare against fresh numbers. Alerts that newly meet their
threshold trigger an email to the user; alerts whose condition clears are
reset so the next crossing fires again.
"""
from django.core.management.base import BaseCommand

from accounts.tasks import check_indicator_alerts


class Command(BaseCommand):
    help = "Evaluate IndicatorAlert rows and email users when thresholds are crossed."

    def handle(self, *args, **options):
        summary = check_indicator_alerts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Alert check complete — triggered: {summary['triggered']}, "
                f"cleared: {summary['cleared']}, emails sent: {summary['emails_sent']}."
            )
        )
