"""Weekly full-statement refresh for :class:`IndicatorSnapshot`.

For each ticker with a market cap, resyncs quarterly earnings, cash flows,
and balance sheets, then recomputes the complete indicator set. This is the
expensive half of the two-cadence refresh strategy — ~4 API calls per ticker,
so it runs weekly rather than daily.

The price-only half (``refresh_snapshot_prices``) runs daily to keep
valuation multiples fresh without hammering the statement endpoints.
"""
import logging

from config.monitored_command import MonitoredCommand
from quotes.indicators import compute_company_indicators
from quotes.models import IndicatorSnapshot, Ticker
from quotes.providers import (
    ProviderError,
    fetch_quote,
    sync_balance_sheets,
    sync_cash_flows,
    sync_earnings,
)

logger = logging.getLogger(__name__)


class Command(MonitoredCommand):
    help = "Resync quarterly statements and recompute IndicatorSnapshot (weekly cadence)"
    sentry_monitor_slug = "sponda-refresh-snapshot-fundamentals"

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

    def run(self, *args, **options):
        ticker_filter = options.get("ticker")
        batch_limit = options.get("limit")

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

        self.stdout.write(
            f"Refreshing fundamentals + snapshots for {total} ticker(s)..."
        )

        success_count = 0
        failure_count = 0

        for ticker_row in tickers:
            symbol = ticker_row.symbol
            try:
                # Resync quarterly statements first. Each sync is independent —
                # a failure in one shouldn't abort the other two.
                for sync in (sync_earnings, sync_cash_flows, sync_balance_sheets):
                    try:
                        sync(symbol)
                    except ProviderError as error:
                        logger.warning(
                            "%s failed for %s: %s", sync.__name__, symbol, error,
                        )

                # Then fetch fresh quote + recompute full indicator set.
                quote = fetch_quote(symbol)
                market_cap = quote.get("marketCap")
                current_price = quote.get("regularMarketPrice")

                if not market_cap:
                    continue

                indicators = compute_company_indicators(
                    symbol, market_cap=market_cap, current_price=current_price,
                )
                IndicatorSnapshot.objects.update_or_create(
                    ticker=symbol, defaults=indicators,
                )
                Ticker.objects.filter(symbol=symbol).update(market_cap=int(market_cap))
                success_count += 1
            except ProviderError as error:
                logger.warning("Fundamentals refresh failed for %s: %s", symbol, error)
                failure_count += 1
            except Exception:
                logger.exception(
                    "Fundamentals refresh raised unexpectedly for %s", symbol,
                )
                failure_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Refreshed {success_count} snapshots, {failure_count} failures "
                f"(total processed: {total})."
            )
        )
