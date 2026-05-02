"""Bulk-backfill Ticker.reported_currency for every FMP-known ticker.

The cross-currency rollout populates the field as a side-effect of
``fmp.sync_earnings``, which is one API call per ticker — slow at 27K
tickers, and fragile (one bad row would crash the whole sweep). FMP
exposes ``/stable/financial-statement-symbol-list`` which returns the
trading and reporting currency for every company in a single response.
This command consumes that list and updates ``Ticker.reported_currency``
in bulk, no per-ticker API calls required.

Brazilian tickers are skipped — sync_tickers eagerly stamps "BRL" for
those, and BRAPI's universe is independent of FMP.
"""
from django.core.management.base import BaseCommand

from quotes.fmp import fetch_currency_map
from quotes.models import Ticker
from quotes.providers import is_brazilian_ticker


class Command(BaseCommand):
    help = "Bulk-stamp Ticker.reported_currency from FMP's financial-statement symbol list."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print the (symbol, current → new) deltas without writing.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Fetching FMP financial-statement-symbol-list...")
        currency_map = fetch_currency_map()
        self.stdout.write(f"Got {len(currency_map)} symbols from FMP.")

        candidates = (
            Ticker.objects
            .exclude(symbol__regex=r"\d+$")  # Brazilian tickers end in digits
            .only("symbol", "reported_currency")
        )

        updated = 0
        unchanged = 0
        skipped_no_data = 0
        for ticker in candidates.iterator(chunk_size=2000):
            if is_brazilian_ticker(ticker.symbol):
                continue
            entry = currency_map.get(ticker.symbol)
            if not entry or not entry.get("reporting"):
                skipped_no_data += 1
                continue
            new_value = entry["reporting"]
            if ticker.reported_currency == new_value:
                unchanged += 1
                continue
            if not options["dry_run"]:
                Ticker.objects.filter(symbol=ticker.symbol).update(
                    reported_currency=new_value,
                )
            updated += 1

        action = "would update" if options["dry_run"] else "updated"
        self.stdout.write(self.style.SUCCESS(
            f"{action} {updated}; unchanged {unchanged}; "
            f"skipped (no FMP currency data) {skipped_no_data}."
        ))
