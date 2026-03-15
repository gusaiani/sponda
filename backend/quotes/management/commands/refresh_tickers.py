from django.core.management.base import BaseCommand

from quotes.brapi import sync_tickers


class Command(BaseCommand):
    help = "Fetch and update the ticker list from BRAPI"

    def handle(self, *args, **options):
        self.stdout.write("Fetching ticker list from BRAPI...")
        try:
            count = sync_tickers()
            self.stdout.write(self.style.SUCCESS(f"Synced {count} tickers."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to sync tickers: {e}"))
