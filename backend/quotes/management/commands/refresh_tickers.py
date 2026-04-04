from django.core.management import call_command
from django.core.management.base import BaseCommand

from quotes.brapi import sync_tickers


class Command(BaseCommand):
    help = "Fetch and update the ticker list from BRAPI (BR) and FMP (US)"

    def handle(self, *args, **options):
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
