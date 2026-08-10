"""Keep cached and precomputed artifacts in step with statement writes.

Writing a quarter is only half the job. Three payloads are cached for 24h
(``FUNDAMENTALS_CACHE_TTL`` and friends) and the screener reads a precomputed
:class:`~quotes.models.IndicatorSnapshot` rather than recomputing per request.
A correct write that skips this module stays invisible for a day and leaves
the screener disagreeing with the detail page in the meantime.

Only the three statement-derived caches are touched. Company metadata
(``ticker_detail_*``) and peer lists (``ticker_peers_*``) hold names, sectors
and logos, none of which a statement can change.

The cache keys live here rather than inline in the views so the two cannot
drift apart: an invalidator that clears a key nobody sets is silent, and
therefore the worst kind of broken.
"""
import logging

from django.core.cache import cache

from .indicators import compute_company_indicators
from .models import IndicatorSnapshot, Ticker

logger = logging.getLogger(__name__)

FUNDAMENTALS_CACHE_KEY_TEMPLATE = "fundamentals:{ticker}"
PE10_CACHE_KEY_TEMPLATE = "pe10:{ticker}"
MULTIPLES_HISTORY_CACHE_KEY_TEMPLATE = "multiples_history:{ticker}"

STATEMENT_DERIVED_CACHE_KEY_TEMPLATES = (
    FUNDAMENTALS_CACHE_KEY_TEMPLATE,
    PE10_CACHE_KEY_TEMPLATE,
    MULTIPLES_HISTORY_CACHE_KEY_TEMPLATE,
)

# How long the edge and the browser may hold a statement-derived payload.
#
# The server-side caches above are now dropped the moment a quarter is
# written, so this header is the only remaining staleness in the path from
# filing to page. It used to be an hour, which put a floor under how fresh
# the site could ever be no matter how fast ingestion got.
#
# Five minutes is safe here because the quota that limits anonymous traffic
# counts *distinct tickers per day*, not requests, so extra origin hits
# cannot exhaust anyone's allowance. Measured origin load for the three
# affected endpoints is ~48 requests/hour, so even the theoretical 12x
# worst case stays far below one request per second.
STATEMENT_DERIVED_CLIENT_CACHE_TTL = 5 * 60
STATEMENT_DERIVED_CACHE_CONTROL = (
    f"public, max-age={STATEMENT_DERIVED_CLIENT_CACHE_TTL}"
)


def fundamentals_cache_key(ticker: str) -> str:
    return FUNDAMENTALS_CACHE_KEY_TEMPLATE.format(ticker=ticker.upper())


def pe10_cache_key(ticker: str) -> str:
    return PE10_CACHE_KEY_TEMPLATE.format(ticker=ticker.upper())


def multiples_history_cache_key(ticker: str) -> str:
    return MULTIPLES_HISTORY_CACHE_KEY_TEMPLATE.format(ticker=ticker.upper())


def statement_derived_cache_keys(ticker: str) -> list[str]:
    """Every cache key whose contents a statement write invalidates."""
    return [
        template.format(ticker=ticker.upper())
        for template in STATEMENT_DERIVED_CACHE_KEY_TEMPLATES
    ]


def invalidate_statement_caches(ticker: str) -> None:
    """Drop the cached payloads that were computed from this ticker's statements."""
    cache.delete_many(statement_derived_cache_keys(ticker))


def _known_market_data(ticker: str) -> tuple[int | None, object | None]:
    """Best available market cap and price, without calling a provider.

    Statements changed; market data did not. Reusing what is already stored
    keeps this off the provider path and avoids blanking a snapshot's market
    cap just because a filing landed.
    """
    snapshot = IndicatorSnapshot.objects.filter(ticker=ticker).first()
    if snapshot is not None and snapshot.market_cap:
        return snapshot.market_cap, snapshot.current_price

    ticker_row = Ticker.objects.filter(symbol=ticker).first()
    if ticker_row is not None and ticker_row.market_cap:
        current_price = snapshot.current_price if snapshot is not None else None
        return ticker_row.market_cap, current_price

    return None, None


def recompute_indicator_snapshot(ticker: str) -> bool:
    """Recompute the screener's precomputed row for one ticker.

    Returns False without writing when no market cap is known, since every
    valuation multiple would be null and a snapshot of nulls is worse than
    no snapshot at all.
    """
    symbol = ticker.upper()
    market_cap, current_price = _known_market_data(symbol)
    if not market_cap:
        logger.debug("No market cap for %s; skipping snapshot recompute", symbol)
        return False

    indicators = compute_company_indicators(
        symbol, market_cap=market_cap, current_price=current_price,
    )
    IndicatorSnapshot.objects.update_or_create(ticker=symbol, defaults=indicators)
    return True


def refresh_derived_data(ticker: str) -> None:
    """Bring every derived artifact back in line after a statement write.

    Snapshot first, caches second. A request arriving in the gap either hits
    a cache that is still warm (stale by seconds) or rebuilds from a snapshot
    that is already correct. Reversing the order would let a request repopulate
    the cache from a snapshot that has not caught up yet.
    """
    recompute_indicator_snapshot(ticker)
    invalidate_statement_caches(ticker)
