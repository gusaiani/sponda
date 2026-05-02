"""Sync per-country monthly CPI data from FRED.

Mirrors `sync_fx_rates`: covers the same baseline set of major reporting
currencies plus any currency observed on `Ticker.reported_currency`.
Currencies without a FRED series mapping in `quotes.fred.CURRENCY_TO_SERIES_ID`
are skipped with a warning so the operator can extend the mapping.
"""
from django.core.management.base import BaseCommand

from quotes.fred import CURRENCY_TO_SERIES_ID, sync_country_cpi
from quotes.models import Ticker


BASELINE_CURRENCIES = [
    "DKK", "EUR", "JPY", "GBP", "CNY", "TWD",
    "CHF", "CAD", "AUD", "MXN", "INR", "KRW",
    "SGD", "HKD", "NOK", "SEK",
]


class Command(BaseCommand):
    help = "Fetch and persist monthly per-country CPI YoY rates from FRED."

    def add_arguments(self, parser):
        parser.add_argument(
            "--currencies",
            help="Comma-separated ISO codes; overrides the auto-discovered set.",
        )

    def handle(self, *args, **options):
        if options.get("currencies"):
            requested = [c.strip().upper() for c in options["currencies"].split(",") if c.strip()]
        else:
            discovered = set(
                Ticker.objects
                .exclude(reported_currency__in=("", "USD", "BRL"))
                .values_list("reported_currency", flat=True)
                .distinct()
            )
            requested = sorted(set(BASELINE_CURRENCIES) | discovered)

        supported = [c for c in requested if c in CURRENCY_TO_SERIES_ID]
        unsupported = [c for c in requested if c not in CURRENCY_TO_SERIES_ID]
        if unsupported:
            self.stderr.write(self.style.WARNING(
                "No FRED mapping for: " + ", ".join(unsupported) +
                " — add them to CURRENCY_TO_SERIES_ID in quotes/fred.py."
            ))

        if not supported:
            self.stdout.write("Nothing to sync.")
            return

        self.stdout.write(f"Syncing country CPI for: {', '.join(supported)}")
        try:
            total = sync_country_cpi(supported)
            self.stdout.write(self.style.SUCCESS(f"Synced {total} CPI rows."))
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync country CPI: {error}"))
