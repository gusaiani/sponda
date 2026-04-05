"""Fetch market cap data from FMP for US tickers that don't have it yet.

Processes tickers one at a time with a short delay to respect rate limits.
Safe to interrupt and re-run — only fetches tickers with NULL market_cap.
"""
import time

from django.core.management.base import BaseCommand

from quotes.fmp import FMPError, fetch_quote
from quotes.models import Ticker

DELAY_BETWEEN_REQUESTS = 0.25  # seconds


class Command(BaseCommand):
    help = "Fetch market cap from FMP for US tickers missing it"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of tickers to process (default: 1000)",
        )

    def handle(self, *args, **options):
        batch_limit = options["limit"]

        # US tickers: don't match Brazilian pattern (letters + digits like PETR4)
        pending_tickers = (
            Ticker.objects.filter(type="stock", market_cap__isnull=True)
            .exclude(symbol__regex=r"^[A-Z]+\d+$")
            .values_list("symbol", flat=True)
            [:batch_limit]
        )
        pending_list = list(pending_tickers)

        if not pending_list:
            self.stdout.write("All US tickers already have market cap data.")
            return

        self.stdout.write(f"Fetching market caps for {len(pending_list)} tickers...")

        updated_count = 0
        failed_count = 0

        for index, symbol in enumerate(pending_list):
            try:
                quote = fetch_quote(symbol)
                market_cap = quote.get("marketCap")
                if market_cap is not None:
                    Ticker.objects.filter(symbol=symbol).update(
                        market_cap=int(market_cap)
                    )
                    updated_count += 1
                else:
                    # Mark as 0 so we don't re-fetch next time
                    Ticker.objects.filter(symbol=symbol).update(market_cap=0)
            except (FMPError, Exception):
                failed_count += 1

            if (index + 1) % 100 == 0:
                self.stdout.write(f"  Progress: {index + 1}/{len(pending_list)} (updated={updated_count}, failed={failed_count})")

            time.sleep(DELAY_BETWEEN_REQUESTS)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated {updated_count}, failed {failed_count}, "
                f"total processed {len(pending_list)}."
            )
        )
