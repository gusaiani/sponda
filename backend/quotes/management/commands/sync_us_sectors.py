"""Populate sector data for US tickers from FMP company profiles.

FMP's stock-list endpoint does not include sector data, so this command
fetches it from the /stable/profile endpoint one ticker at a time.
Processes a configurable batch per run to stay within API rate limits.
"""
from django.core.management.base import BaseCommand
from django.db.models import F, Value
from django.db.models.functions import Coalesce

from quotes.fmp import FMPError, fetch_profile
from quotes.models import Ticker

DEFAULT_BATCH_SIZE = 5000


class Command(BaseCommand):
    help = "Fetch sector data from FMP profiles for US tickers missing sectors"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Maximum number of tickers to process per run (default: {DEFAULT_BATCH_SIZE})",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]

        # US tickers without sector, prioritized by market cap (popular tickers first)
        tickers = list(
            Ticker.objects.filter(type="stock", sector="")
            .exclude(symbol__regex=r"^[A-Z]+\d+$")
            .order_by(F("market_cap").desc(nulls_last=True))
            .values_list("symbol", flat=True)[:batch_size]
        )

        if not tickers:
            self.stdout.write("All US tickers already have sector data.")
            return

        self.stdout.write(f"Fetching sectors for {len(tickers)} US tickers...")

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

            sector = profile.get("sector") or ""
            if not sector:
                continue

            Ticker.objects.filter(symbol=symbol).update(sector=sector)
            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated_count} sectors ({failed_count} failed, "
                f"{len(tickers) - updated_count - failed_count} had no sector in profile)."
            )
        )
