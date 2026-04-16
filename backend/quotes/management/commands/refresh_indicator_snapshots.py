"""Recompute :class:`IndicatorSnapshot` rows for every ticker with a market cap.

Runs daily from a systemd timer. The screener endpoint reads snapshots directly
so a user filtering on PE10 / leverage ratios never triggers a live calculation.

The command is resilient: if a single ticker raises, we log and keep going so
one bad ticker cannot poison the whole refresh.
"""
import logging

from django.core.management.base import BaseCommand

from quotes.indicators import compute_company_indicators
from quotes.models import IndicatorSnapshot, Ticker

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Recompute IndicatorSnapshot rows from the latest financial data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ticker",
            type=str,
            default=None,
            help="Only refresh a single ticker (case-insensitive)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of tickers to refresh (default: no limit)",
        )

    def handle(self, *args, **options):
        ticker_filter = options.get("ticker")
        batch_limit = options.get("limit")

        # Tickers without a market cap produce no valuation indicators — skip
        # them entirely so the screener never returns half-empty rows.
        tickers = Ticker.objects.exclude(market_cap__isnull=True).exclude(market_cap=0)
        if ticker_filter:
            tickers = tickers.filter(symbol__iexact=ticker_filter)
        tickers = tickers.order_by("symbol")
        if batch_limit is not None:
            tickers = tickers[:batch_limit]

        total = tickers.count()
        if total == 0:
            self.stdout.write("No tickers to refresh.")
            return

        self.stdout.write(f"Refreshing indicator snapshots for {total} ticker(s)...")

        success_count = 0
        failure_count = 0

        for ticker in tickers:
            symbol = ticker.symbol
            try:
                indicators = compute_company_indicators(
                    symbol, market_cap=ticker.market_cap,
                )
                IndicatorSnapshot.objects.update_or_create(
                    ticker=symbol, defaults=indicators,
                )
                success_count += 1
            except Exception:
                logger.exception("Failed to refresh indicator snapshot for %s", symbol)
                failure_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Refreshed {success_count} snapshots, {failure_count} failures "
                f"(total processed: {total})."
            )
        )
