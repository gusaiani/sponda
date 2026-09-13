"""The stored daily market cap series, and the rules for keeping it current.

The multiples chart values each past year at the market cap the provider
observed on the day that year closed, which is what keeps an old year from
being priced with today's share count. That series used to be refetched
per company per day, 0.44 MB a time, roughly 2.5 GB a month.

It is kept in Postgres now and topped up with the days it is missing,
behind the same freshness marker the price store uses. Unlike prices, a
market cap is not adjusted after the fact · a split leaves it unchanged ·
so a day that comes back with a different number is a provider revision to
store, not a sign that the stored history is on the wrong scale.
"""
from __future__ import annotations

import logging
from datetime import date

from django.db.models import Max

from . import fmp
from .fmp import FMPError
from .models import DailyMarketCap
from .series_store import (
    HISTORY_START_DATE,
    is_fresh,
    mark_fresh,
    parse_provider_rows,
    to_chart_series,
    topup_start_date,
)

logger = logging.getLogger(__name__)

CACHE_NAMESPACE = "market_cap_store"
VALUE_KEY = "marketCap"


def _stored_series(ticker: str) -> list[tuple[date, float]]:
    rows = (
        DailyMarketCap.objects.filter(ticker=ticker)
        .order_by("date")
        .values_list("date", "market_cap")
    )
    return [(row_date, float(market_cap)) for row_date, market_cap in rows]


def _write_market_caps(ticker: str, market_caps: dict[date, float]) -> None:
    DailyMarketCap.objects.bulk_create(
        [
            DailyMarketCap(ticker=ticker, date=cap_date, market_cap=int(market_cap))
            for cap_date, market_cap in sorted(market_caps.items())
        ],
        update_conflicts=True,
        update_fields=["market_cap", "fetched_at"],
        unique_fields=["ticker", "date"],
    )


def _fetch(ticker: str, start_date: date) -> dict[date, float]:
    return parse_provider_rows(
        fmp.fetch_historical_market_caps(ticker, start_date=start_date),
        value_keys=(VALUE_KEY,),
    )


def get_daily_market_caps(ticker: str) -> list[dict]:
    """Daily reported market caps for `ticker`, oldest first, kept current.

    Raises :class:`FMPError` only when there is nothing to serve, which for
    this series usually means the provider does not cover the symbol. The
    multiples view already treats that as "chart without this enrichment".
    """
    ticker = ticker.upper()
    stored = _stored_series(ticker)

    if stored and is_fresh(CACHE_NAMESPACE, ticker):
        return to_chart_series(stored, VALUE_KEY)

    if not stored:
        fetched = _fetch(ticker, HISTORY_START_DATE)
        if not fetched:
            raise FMPError(f"No historical market cap data for ticker {ticker}")
        _write_market_caps(ticker, fetched)
        mark_fresh(CACHE_NAMESPACE, ticker)
        return to_chart_series(sorted(fetched.items()), VALUE_KEY)

    newest_stored_date = DailyMarketCap.objects.filter(ticker=ticker).aggregate(
        Max("date")
    )["date__max"]

    try:
        fetched = _fetch(ticker, topup_start_date(newest_stored_date))
    except FMPError as error:
        # The stored series is the whole point: a provider outage or a spent
        # quota costs freshness, not the chart.
        logger.warning("Market cap top-up failed for %s: %s", ticker, error)
        return to_chart_series(stored, VALUE_KEY)

    if fetched:
        _write_market_caps(ticker, fetched)

    mark_fresh(CACHE_NAMESPACE, ticker)
    return to_chart_series(_stored_series(ticker), VALUE_KEY)
