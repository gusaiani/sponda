from django.core.management import call_command

from config.monitored_command import MonitoredCommand
from quotes.brapi import sync_tickers


class Command(MonitoredCommand):
    help = "Fetch and update the ticker list from BRAPI (BR) and FMP (US)"
    sentry_monitor_slug = "sponda-refresh-tickers"

    def run(self, *args, **options):
        self.stdout.write("Fetching BR ticker list from BRAPI...")
        try:
            count = sync_tickers()
            self.stdout.write(self.style.SUCCESS(f"Synced {count} BR tickers."))
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync BR tickers: {error}"))

        self.stdout.write("Fetching US ticker list from FMP...")
        try:
            call_command("refresh_us_tickers")
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync US tickers: {error}"))

        self.stdout.write("Syncing market caps for US tickers...")
        try:
            call_command("sync_market_caps")
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync market caps: {error}"))

        self.stdout.write("Syncing sectors for US tickers...")
        try:
            call_command("sync_us_sectors")
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync US sectors: {error}"))
