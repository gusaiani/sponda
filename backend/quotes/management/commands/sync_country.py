"""Backfill country data for tickers from FMP company profiles.

The deploy-time data migration sets ``country='BR'`` for every ticker
matching the Brazilian symbol pattern, so this command only ever needs
to fetch profiles for non-Brazilian tickers that are still missing
country. Mirrors :mod:`sync_us_sectors` exactly — same batch model,
same prioritization by market cap, same error handling — so an
operator who already runs the sector backfill knows what to expect.
"""
from django.core.management.base import BaseCommand
from django.db.models import F

from quotes.fmp import FMPError, fetch_profile
from quotes.models import Ticker

DEFAULT_BATCH_SIZE = 5000


class Command(BaseCommand):
    help = "Fetch country data from FMP profiles for tickers missing country"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Maximum number of tickers to process per run (default: {DEFAULT_BATCH_SIZE})",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]

        tickers = list(
            Ticker.objects.filter(type="stock", country="")
            .exclude(symbol__regex=r"^[A-Z]+\d+$")
            .order_by(F("market_cap").desc(nulls_last=True))
            .values_list("symbol", flat=True)[:batch_size]
        )

        if not tickers:
            self.stdout.write("All tickers already have country data.")
            return

        self.stdout.write(f"Fetching country for {len(tickers)} tickers...")

        updated_count = 0
        failed_count = 0

        for symbol in tickers:
            try:
                profile = fetch_profile(symbol)
            except FMPError:
                failed_count += 1
                continue

            if profile is None:
                failed_count += 1
                continue

            country = (profile.get("country") or "").strip().upper()
            if not country:
                continue

            Ticker.objects.filter(symbol=symbol).update(country=country)
            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated_count} countries ({failed_count} failed, "
                f"{len(tickers) - updated_count - failed_count} had no country in profile)."
            )
        )
