"""Daily quote-only refresh for :class:`IndicatorSnapshot`.

Fetches the current quote for every ticker with a market cap and recomputes
only the price-dependent indicators (PE10, PFCF10, PEG, P/FCF PEG) against
existing DB fundamentals. Leverage and debt-coverage fields are left alone
because they depend on balance-sheet / cash-flow data, which is refreshed
weekly by ``refresh_snapshot_fundamentals``.

This split keeps API usage within the BRAPI Pro and FMP Starter monthly
budgets: ~1 call per ticker per day instead of ~4.
"""
import logging
from decimal import Decimal

from django.core.management.base import BaseCommand

from quotes.models import IndicatorSnapshot, Ticker
from quotes.pe10 import calculate_pe10
from quotes.peg import calculate_peg
from quotes.pfcf10 import calculate_pfcf10
from quotes.pfcf_peg import calculate_pfcf_peg
from quotes.providers import (
    ProviderError,
    fetch_quote,
    sync_balance_sheets,  # imported for test isolation; never called here
    sync_cash_flows,
    sync_earnings,
)

logger = logging.getLogger(__name__)

# ``sync_*`` are imported but deliberately unused — the daily price job must
# never hit the quarterly statement endpoints. The imports let tests patch
# the symbols on this module and assert they stay untouched.
_ = (sync_balance_sheets, sync_cash_flows, sync_earnings)


def _to_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class Command(BaseCommand):
    help = "Refresh price-dependent IndicatorSnapshot fields (daily cadence)"

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
            f"Refreshing snapshot prices for {total} ticker(s)..."
        )

        success_count = 0
        failure_count = 0

        for ticker_row in tickers:
            symbol = ticker_row.symbol
            try:
                quote = fetch_quote(symbol)
                market_cap = quote.get("marketCap")
                current_price = quote.get("regularMarketPrice")
                if not market_cap:
                    # Upstream returned no market cap; skip silently.
                    continue

                market_cap_decimal = Decimal(str(market_cap))

                pe10_result = calculate_pe10(symbol, market_cap_decimal, max_years=10)
                pfcf10_result = calculate_pfcf10(
                    symbol, market_cap_decimal, max_years=10,
                )
                pe10_value = pe10_result.get("pe10")
                pfcf10_value = pfcf10_result.get("pfcf10")

                peg_result = (
                    calculate_peg(symbol, pe10_value, max_years=10)
                    if pe10_value is not None
                    else {"peg": None}
                )
                pfcf_peg_result = (
                    calculate_pfcf_peg(symbol, pfcf10_value, max_years=10)
                    if pfcf10_value is not None
                    else {"pfcfPeg": None}
                )

                defaults = {
                    "market_cap": int(market_cap),
                    "current_price": _to_decimal(current_price),
                    "pe10": _to_decimal(pe10_value),
                    "pfcf10": _to_decimal(pfcf10_value),
                    "peg": _to_decimal(peg_result.get("peg")),
                    "pfcf_peg": _to_decimal(pfcf_peg_result.get("pfcfPeg")),
                }

                snapshot, created = IndicatorSnapshot.objects.get_or_create(
                    ticker=symbol, defaults=defaults,
                )
                if not created:
                    for field, value in defaults.items():
                        setattr(snapshot, field, value)
                    snapshot.save(update_fields=list(defaults.keys()) + ["computed_at"])

                Ticker.objects.filter(symbol=symbol).update(market_cap=int(market_cap))
                success_count += 1
            except ProviderError as error:
                logger.warning("Price refresh failed for %s: %s", symbol, error)
                failure_count += 1
            except Exception:
                logger.exception("Price refresh raised unexpectedly for %s", symbol)
                failure_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Refreshed {success_count} snapshots, {failure_count} failures "
                f"(total processed: {total})."
            )
        )
