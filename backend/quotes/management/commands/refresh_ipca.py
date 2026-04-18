from config.monitored_command import MonitoredCommand
from quotes.brapi import sync_ipca


class Command(MonitoredCommand):
    help = "Fetch and update IPCA index data from BRAPI"
    sentry_monitor_slug = "sponda-refresh-ipca"

    def run(self, *args, **options):
        self.stdout.write("Fetching IPCA data from BRAPI...")
        try:
            count = sync_ipca()
            self.stdout.write(self.style.SUCCESS(f"Synced {count} IPCA records."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to sync IPCA: {e}"))
