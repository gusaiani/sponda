"""Fetch market cap data for tickers that don't have it yet.

Routes Brazilian tickers (e.g., PETR4) to BRAPI and US tickers (e.g., AAPL)
to FMP via the provider layer. Processes tickers one at a time with a short
delay to respect rate limits. Safe to interrupt and re-run — only fetches
tickers with NULL market_cap.
"""
import time

from django.core.management.base import BaseCommand

from quotes.models import Ticker
from quotes.providers import ProviderError, fetch_quote

DELAY_BETWEEN_REQUESTS = 0.25  # seconds


class Command(BaseCommand):
    help = "Fetch market cap from BRAPI (BR) or FMP (US) for tickers missing it"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of tickers to process (default: 1000)",
        )

    def handle(self, *args, **options):
        batch_limit = options["limit"]

        pending_tickers = list(
            Ticker.objects.filter(type="stock", market_cap__isnull=True)
            .order_by("symbol")
            .values_list("symbol", flat=True)
            [:batch_limit]
        )

        if not pending_tickers:
            self.stdout.write("All tickers already have market cap data.")
            return

        self.stdout.write(f"Fetching market caps for {len(pending_tickers)} tickers...")

        updated_count = 0
        failed_count = 0
        missing_count = 0

        for index, symbol in enumerate(pending_tickers):
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
                    missing_count += 1
            except ProviderError:
                failed_count += 1
            except Exception:
                failed_count += 1

            if (index + 1) % 100 == 0:
                self.stdout.write(
                    f"  Progress: {index + 1}/{len(pending_tickers)} "
                    f"(updated={updated_count}, missing={missing_count}, failed={failed_count})"
                )

            time.sleep(DELAY_BETWEEN_REQUESTS)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated {updated_count}, missing {missing_count}, "
                f"failed {failed_count}, total processed {len(pending_tickers)}."
            )
        )
