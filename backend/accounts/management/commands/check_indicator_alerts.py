"""Evaluate every active :class:`IndicatorAlert` against the latest snapshots.

Runs from a systemd timer right after ``refresh_indicator_snapshots`` so the
alerts always compare against fresh numbers. One-shot: triggered alerts are
emailed, saved as notifications, and deleted.
"""
from accounts.tasks import check_indicator_alerts
from config.monitored_command import MonitoredCommand


class Command(MonitoredCommand):
    help = "Evaluate IndicatorAlert rows and email users when thresholds are crossed."
    sentry_monitor_slug = "sponda-check-alerts"

    def run(self, *args, **options):
        summary = check_indicator_alerts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Alert check complete — triggered: {summary['triggered']}, "
                f"emails sent: {summary['emails_sent']}."
            )
        )
