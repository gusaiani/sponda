from django.core.management.base import BaseCommand

from quotes.brapi import sync_ipca


class Command(BaseCommand):
    help = "Fetch and update IPCA index data from BRAPI"

    def handle(self, *args, **options):
        self.stdout.write("Fetching IPCA data from BRAPI...")
        try:
            count = sync_ipca()
            self.stdout.write(self.style.SUCCESS(f"Synced {count} IPCA records."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to sync IPCA: {e}"))
