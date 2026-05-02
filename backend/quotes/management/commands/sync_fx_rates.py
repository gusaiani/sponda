"""Sync USD↔X daily FX rates from FMP.

By default, syncs the union of:
  * a baseline of major reporting currencies we expect to encounter
    (DKK, EUR, JPY, GBP, CNY, TWD, CHF, CAD, AUD, MXN, INR, KRW, SGD,
    HKD, NOK, SEK)
  * any currency that appears in `Ticker.reported_currency` other than
    USD/BRL (so a newly-added ticker reporting in PLN gets picked up
    automatically)

Pass `--currencies XXX,YYY` to override the list.
"""
from django.core.management.base import BaseCommand

from quotes.fmp import sync_fx_rates
from quotes.models import Ticker


BASELINE_CURRENCIES = [
    "DKK", "EUR", "JPY", "GBP", "CNY", "TWD",
    "CHF", "CAD", "AUD", "MXN", "INR", "KRW",
    "SGD", "HKD", "NOK", "SEK",
]


class Command(BaseCommand):
    help = "Fetch and persist daily USD↔X FX rates from FMP, back to 2010."

    def add_arguments(self, parser):
        parser.add_argument(
            "--currencies",
            help="Comma-separated ISO codes; overrides the auto-discovered set.",
        )

    def handle(self, *args, **options):
        if options.get("currencies"):
            currencies = [c.strip().upper() for c in options["currencies"].split(",") if c.strip()]
        else:
            discovered = set(
                Ticker.objects
                .exclude(reported_currency__in=("", "USD", "BRL"))
                .values_list("reported_currency", flat=True)
                .distinct()
            )
            currencies = sorted(set(BASELINE_CURRENCIES) | discovered)

        self.stdout.write(f"Syncing FX rates for: {', '.join(currencies)}")
        try:
            total = sync_fx_rates(currencies)
            self.stdout.write(self.style.SUCCESS(f"Synced {total} FX rows."))
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync FX rates: {error}"))
