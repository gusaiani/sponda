"""Company payloads assembled from the database alone.

Every other company accessor in this codebase is expensive.
``_compute_quote_payload`` syncs statements and fetches a live quote from
BRAPI or FMP on a cache miss, which is why ``PE10View``,
``FundamentalsView`` and ``MultiplesHistoryView`` all sit behind
``LookupQuotaEnforcedView`` and its cap of
``SPONDA_ANON_LOOKUPS_PER_DAY`` distinct companies per IP per day.

The accessors here are the opposite: two indexed reads against ``Ticker``
and ``IndicatorSnapshot``, or a scan of the statement tables already in
the database. No provider is ever contacted, so no quota is needed. That
is what makes it safe to publish a markdown twin of all ~23K company
pages and let a crawler sweep the lot.

The invariant is load-bearing and pinned by
``backend/tests/test_company_snapshot.py::TestNoProviderCalls``. Anything
added here must stay pure DB.
"""
from __future__ import annotations

from typing import Iterable

from quotes.fundamentals import compute_fundamentals, compute_quarterly_balance_ratios
from quotes.json_utils import json_safe
from quotes.models import CompanyAnalysis, IndicatorSnapshot, Ticker
from quotes.providers import is_brazilian_ticker
from quotes.screener import SCREENER_FILTERABLE_FIELDS

# Identity fields every company payload opens with, before the indicators.
IDENTITY_FIELDS = ("symbol", "name", "sector", "country", "reported_currency")

# Only listed companies get a company page. Funds and ETFs have tickers and
# sometimes even snapshots, but none of the indicators mean anything for them.
COMPANY_TYPE = "stock"


def _normalize(symbol: str | None) -> str:
    return (symbol or "").strip().upper()


def _identity(ticker: Ticker) -> dict:
    return {
        "symbol": ticker.symbol,
        "name": ticker.display_name or ticker.name,
        "sector": ticker.sector,
        "country": ticker.country,
        "reported_currency": ticker.reported_currency,
    }


def _indicators(snapshot: IndicatorSnapshot) -> dict:
    return {field: getattr(snapshot, field) for field in SCREENER_FILTERABLE_FIELDS}


def _payload(ticker: Ticker, snapshot: IndicatorSnapshot) -> dict:
    return json_safe({
        **_identity(ticker),
        "market_cap": snapshot.market_cap,
        "current_price": snapshot.current_price,
        **_indicators(snapshot),
        "computed_at": snapshot.computed_at.isoformat() if snapshot.computed_at else None,
    })


def company_snapshot(symbol: str | None) -> dict | None:
    """Ticker metadata plus IndicatorSnapshot values for one stock symbol.

    Case-insensitive. Returns ``None`` for an unknown symbol, for a
    non-stock instrument, and for a listed company that has no snapshot
    row yet. ``refresh_indicator_snapshots`` only writes rows for tickers
    with a market cap, so the last case is ordinary, not exceptional.
    """
    normalized_symbol = _normalize(symbol)
    if not normalized_symbol:
        return None

    ticker = Ticker.objects.filter(
        symbol__iexact=normalized_symbol, type=COMPANY_TYPE,
    ).first()
    if ticker is None:
        return None

    snapshot = IndicatorSnapshot.objects.filter(ticker__iexact=ticker.symbol).first()
    if snapshot is None:
        return None

    return _payload(ticker, snapshot)


def company_snapshots(symbols: Iterable[str]) -> dict[str, dict]:
    """Bulk form of :func:`company_snapshot`, keyed by upper-cased symbol.

    Two queries no matter how many symbols are asked for, so the peer
    table on a comparison page costs the same as a single company. Symbols
    with no ticker, no snapshot, or the wrong type are simply absent from
    the result rather than present with a null value.
    """
    normalized_symbols = [
        symbol for symbol in (_normalize(candidate) for candidate in symbols) if symbol
    ]
    if not normalized_symbols:
        return {}

    tickers = {
        ticker.symbol.upper(): ticker
        for ticker in Ticker.objects.filter(
            symbol__in=normalized_symbols, type=COMPANY_TYPE,
        )
    }
    if not tickers:
        return {}

    snapshots = {
        snapshot.ticker.upper(): snapshot
        for snapshot in IndicatorSnapshot.objects.filter(ticker__in=list(tickers))
    }

    return {
        symbol: _payload(ticker, snapshots[symbol])
        for symbol, ticker in tickers.items()
        if symbol in snapshots
    }


def company_fundamentals(symbol: str | None) -> dict | None:
    """The per-year fundamentals table, without contacting a provider.

    ``FundamentalsView`` builds the same table but first calls
    ``_ensure_fresh_data``, ``fetch_quote``, ``fetch_historical_prices``
    and ``fetch_dividends``. Every one of those is an *input* to
    :func:`compute_fundamentals`, not a dependency of it: the year rows
    themselves come from ``QuarterlyEarnings``, ``QuarterlyCashFlow`` and
    ``BalanceSheet``, all already in the database.

    So this passes market cap and price from the snapshot and leaves the
    provider-backed inputs out. The cost is the per-year price multiples
    and the dividend column, which the caller is expected to say is
    missing rather than pass off as absent data.
    """
    snapshot_payload = company_snapshot(symbol)
    if snapshot_payload is None:
        return None

    normalized_symbol = snapshot_payload["symbol"]
    market_cap = snapshot_payload["market_cap"]
    current_price = snapshot_payload["current_price"]

    years = compute_fundamentals(
        normalized_symbol,
        market_cap=float(market_cap) if market_cap else None,
        current_price=float(current_price) if current_price else None,
        historical_prices=None,
        proventos_by_year=None,
    )

    listing_currency = "BRL" if is_brazilian_ticker(normalized_symbol) else "USD"
    return json_safe({
        "years": years,
        "quarterlyRatios": compute_quarterly_balance_ratios(normalized_symbol),
        "listingCurrency": listing_currency,
        "reportedCurrency": snapshot_payload["reported_currency"] or listing_currency,
        # Stated, not silently omitted: these two columns exist on the HTML
        # fundamentals tab and cannot be filled without a provider call.
        "omitted": ["annualPriceMultiples", "dividends"],
    })


def company_analysis(symbol: str | None) -> dict | None:
    """The latest stored analysis for a company, or None when there is none.

    ``CompanyAnalysisView`` serves the same row but 404s when a company has
    no analysis, and most do not. A 404 is not storable in the Next data
    cache, so a markdown page that asked that endpoint would re-fetch on
    every single view for the whole catalogue. Returning None lets the
    caller answer 200 with a null and have the whole page cached once.
    """
    normalized_symbol = _normalize(symbol)
    if not normalized_symbol:
        return None

    latest = (
        CompanyAnalysis.objects.filter(ticker=normalized_symbol)
        .order_by("-generated_at")
        .values("content", "data_quarter", "generated_at")
        .first()
    )
    if latest is None:
        return None

    return {
        "content": latest["content"],
        "dataQuarter": latest["data_quarter"],
        "generatedAt": latest["generated_at"].isoformat(),
    }


def covered_company_count() -> int:
    """How many listed companies we hold indicators for.

    Cached alongside the sitemap's symbol list, so the MCP handshake and the
    sitemap can never quote different numbers.
    """
    from django.core.cache import cache

    from quotes.views import SYMBOL_LIST_CACHE_KEY, TICKER_LIST_CACHE_TIMEOUT

    symbols = cache.get(SYMBOL_LIST_CACHE_KEY)
    if symbols is None:
        symbols = list(
            Ticker.objects.filter(
                type=COMPANY_TYPE,
                symbol__in=IndicatorSnapshot.objects.values("ticker"),
            )
            .exclude(symbol__regex=r"^[A-Z]+\d+F$")
            .order_by("symbol")
            .values_list("symbol", flat=True)
        )
        cache.set(SYMBOL_LIST_CACHE_KEY, symbols, TICKER_LIST_CACHE_TIMEOUT)
    return len(symbols)
