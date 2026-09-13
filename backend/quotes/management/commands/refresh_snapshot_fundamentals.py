"""Weekly statement refresh and full snapshot recompute.

Two jobs, with very different costs:

* **Refetch statements.** Expensive · three provider calls and about
  400 KB per company. Only companies that could plausibly have filed
  something get this, which FMP's earnings calendar answers in one call.
  Refetching all 18,158 every week spent 7.3 GB to discover that almost
  nobody had reported, and half of every run was rejected by the provider's
  rate limit on the way.
* **Recompute snapshots.** Cheap · database reads and arithmetic. Every
  company gets this on every run, because the inflation indices and the
  price the multiples are taken against move even when the filings do not.

Quotes are read in batches of a hundred rather than one call per company:
the same 18,158 market caps for 182 calls instead of 18,158.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from config.monitored_command import MonitoredCommand
from quotes.derived_data import invalidate_statement_caches
from quotes.fmp import FMPError, fetch_recent_reporters
from quotes.indicators import compute_company_indicators
from quotes.models import IndicatorSnapshot, Ticker
from quotes.providers import (
    ProviderError,
    fetch_quotes_batch,
    sync_balance_sheets,
    sync_cash_flows,
    sync_earnings,
)
from quotes.statement_refresh import symbols_needing_statement_refresh

logger = logging.getLogger(__name__)

# How far back the earnings calendar is read. The command runs weekly, so a
# fortnight covers the window plus a missed run, and costs about 100 KB.
CALENDAR_LOOKBACK_DAYS = 14


class Command(MonitoredCommand):
    help = "Refetch statements for companies that reported, recompute every snapshot"
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
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help=(
                "Refetch statements for every ticker, ignoring the earnings "
                "calendar. The old behaviour, kept for backfills."
            ),
        )

    def run(self, *args, **options):
        ticker_filter = options.get("ticker")
        batch_limit = options.get("limit")
        refresh_every_statement = options.get("all", False)

        tickers = Ticker.objects.exclude(market_cap__isnull=True).exclude(market_cap=0)
        if ticker_filter:
            tickers = tickers.filter(symbol__iexact=ticker_filter)
        tickers = tickers.order_by("symbol")
        if batch_limit is not None:
            tickers = tickers[:batch_limit]

        symbols = list(tickers.values_list("symbol", flat=True))
        if not symbols:
            self.stdout.write("No tickers to refresh.")
            return

        symbols_to_resync = self._select_statement_resyncs(
            symbols, refresh_every_statement
        )
        self.stdout.write(
            f"Recomputing snapshots for {len(symbols)} ticker(s); "
            f"refetching statements for {len(symbols_to_resync)}."
        )

        quotes = self._fetch_quotes(symbols)
        success_count = 0
        failure_count = 0

        for symbol in symbols:
            try:
                if symbol in symbols_to_resync:
                    self._resync_statements(symbol)

                quote = quotes.get(symbol)
                if quote is None:
                    logger.warning("No quote returned for %s in batch response", symbol)
                    failure_count += 1
                    continue

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
                # The snapshot above already used this run's fresh quote, so
                # only the cached payloads still need dropping.
                invalidate_statement_caches(symbol)
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
                f"(total processed: {len(symbols)})."
            )
        )

    def _select_statement_resyncs(
        self, symbols: list[str], refresh_every_statement: bool
    ) -> set[str]:
        """Which companies get their three statements refetched this run."""
        if refresh_every_statement:
            return set(symbols)

        today = timezone.localdate()
        try:
            recent_reporters = fetch_recent_reporters(
                today - timedelta(days=CALENDAR_LOOKBACK_DAYS), today
            )
        except FMPError as error:
            # Without the calendar there is no way to tell who reported.
            # Refetching everything is expensive; refetching nothing would
            # quietly stop updating the data, which is worse.
            logger.warning(
                "Earnings calendar unavailable (%s); refetching every statement",
                error,
            )
            return set(symbols)

        return symbols_needing_statement_refresh(symbols, recent_reporters)

    def _fetch_quotes(self, symbols: list[str]) -> dict[str, dict]:
        try:
            return fetch_quotes_batch(symbols)
        except ProviderError as error:
            self.stderr.write(f"Batch quote fetch failed: {error}")
            return {}

    def _resync_statements(self, symbol: str) -> None:
        """Each sync is independent · one failing must not skip the other two.

        The attempt is stamped whatever comes back. A provider with nothing
        for this company writes no rows, so without the stamp the next run
        cannot tell "never asked" from "asked, and there is nothing there",
        and 1,848 such companies would be asked again every week.
        """
        syncs = (
            ("sync_earnings", sync_earnings),
            ("sync_cash_flows", sync_cash_flows),
            ("sync_balance_sheets", sync_balance_sheets),
        )
        for sync_name, sync in syncs:
            try:
                sync(symbol)
            except ProviderError as error:
                logger.warning("%s failed for %s: %s", sync_name, symbol, error)
        Ticker.objects.filter(symbol=symbol).update(
            statements_last_attempted_at=timezone.now()
        )
