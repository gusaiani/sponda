from django.core.management.base import BaseCommand

from quotes.fmp import sync_us_cpi


class Command(BaseCommand):
    help = "Fetch and update US CPI data from FMP"

    def handle(self, *args, **options):
        self.stdout.write("Fetching US CPI data from FMP...")
        try:
            count = sync_us_cpi()
            self.stdout.write(self.style.SUCCESS(f"Synced {count} CPI records."))
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync US CPI: {error}"))
