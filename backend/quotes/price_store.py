"""The stored daily close series, and the rules for keeping it current.

A company page reads twenty-five years of daily closes. Fetching that from
FMP costs 1.09 MB, and the only copy used to live in a one-hour cache, so
roughly three hundred company views a day were spending a third of a
gigabyte on prices that had not changed. The series lives in Postgres now:
a ticker nobody has asked for yet costs one full fetch, and every request
after that costs the days that are genuinely missing.

Two rules keep it honest:

* **Top-ups are bounded, not free.** A successful check marks the ticker
  fresh for a few hours, so a page hammered by crawlers cannot turn into
  one provider call per request.
* **Splits invalidate the past.** The provider's series is split-adjusted,
  so a 4-for-1 split rewrites every close before it. Each top-up refetches
  a short overlap it already holds; when the overlap comes back at a
  different price, the stored series is on the old scale and is replaced
  wholesale. This is the one thing the market cap store does not need: a
  split leaves a company's market cap alone.

The machinery both stores share lives in :mod:`quotes.series_store`.
"""
from __future__ import annotations

import logging
from datetime import date

from django.db.models import Max

from . import fmp
from .fmp import FMPError
from .models import DailyClosePrice
from .series_store import (
    HISTORY_START_DATE,
    is_fresh,
    mark_fresh,
    parse_provider_rows,
    to_chart_series,
    topup_start_date,
)

logger = logging.getLogger(__name__)

CACHE_NAMESPACE = "price_store"
VALUE_KEY = "adjustedClose"

# `light` calls the close `price`; `full` called it `close`. Reading both
# keeps this working if the endpoint is ever switched back.
PROVIDER_VALUE_KEYS = ("price", "close")

# Two closes for the same day are "the same price" within this relative
# tolerance. Anything larger is a re-adjustment (a split), not rounding.
SPLIT_DETECTION_TOLERANCE = 0.001


def _stored_series(ticker: str) -> list[tuple[date, float]]:
    rows = (
        DailyClosePrice.objects.filter(ticker=ticker)
        .order_by("date")
        .values_list("date", "close")
    )
    return [(row_date, float(close)) for row_date, close in rows]


def _write_closes(ticker: str, closes: dict[date, float]) -> None:
    DailyClosePrice.objects.bulk_create(
        [
            DailyClosePrice(ticker=ticker, date=close_date, close=close)
            for close_date, close in sorted(closes.items())
        ],
        update_conflicts=True,
        update_fields=["close", "fetched_at"],
        unique_fields=["ticker", "date"],
    )


def _fetch(ticker: str, start_date: date) -> dict[date, float]:
    return parse_provider_rows(
        fmp.fetch_historical_prices(ticker, start_date=start_date),
        value_keys=PROVIDER_VALUE_KEYS,
    )


def _overlap_disagrees(
    ticker: str, stored: list[tuple[date, float]], fetched: dict[date, float]
) -> bool:
    """True when a day held in both copies comes back at a different price."""
    stored_by_date = dict(stored)
    for close_date, fetched_close in fetched.items():
        stored_close = stored_by_date.get(close_date)
        if stored_close is None or stored_close == 0:
            continue
        relative_difference = abs(fetched_close - stored_close) / abs(stored_close)
        if relative_difference > SPLIT_DETECTION_TOLERANCE:
            logger.info(
                "Price series for %s re-adjusted on %s (%s to %s); refetching history",
                ticker,
                close_date,
                stored_close,
                fetched_close,
            )
            return True
    return False


def get_daily_closes(ticker: str) -> list[dict]:
    """Daily adjusted closes for `ticker`, oldest first, kept current.

    Raises :class:`FMPError` only when there is nothing to serve: no stored
    rows and no rows from the provider either. A provider failure with a
    stored series behind it degrades to the stored series, which is a day
    or two stale at worst.
    """
    ticker = ticker.upper()
    stored = _stored_series(ticker)

    if stored and is_fresh(CACHE_NAMESPACE, ticker):
        return to_chart_series(stored, VALUE_KEY)

    if not stored:
        fetched = _fetch(ticker, HISTORY_START_DATE)
        if not fetched:
            raise FMPError(f"No historical price data for ticker {ticker}")
        _write_closes(ticker, fetched)
        mark_fresh(CACHE_NAMESPACE, ticker)
        return to_chart_series(sorted(fetched.items()), VALUE_KEY)

    newest_stored_date = DailyClosePrice.objects.filter(ticker=ticker).aggregate(
        Max("date")
    )["date__max"]

    try:
        fetched = _fetch(ticker, topup_start_date(newest_stored_date))
    except FMPError as error:
        # The stored series is the whole point: a provider outage or a spent
        # quota costs freshness, not the page.
        logger.warning("Price top-up failed for %s: %s", ticker, error)
        return to_chart_series(stored, VALUE_KEY)

    if _overlap_disagrees(ticker, stored, fetched):
        try:
            fetched = _fetch(ticker, HISTORY_START_DATE)
        except FMPError as error:
            logger.warning("Price refetch failed for %s: %s", ticker, error)
            return to_chart_series(stored, VALUE_KEY)
        if fetched:
            DailyClosePrice.objects.filter(ticker=ticker).delete()
            _write_closes(ticker, fetched)
            mark_fresh(CACHE_NAMESPACE, ticker)
            return to_chart_series(sorted(fetched.items()), VALUE_KEY)

    if fetched:
        _write_closes(ticker, fetched)

    mark_fresh(CACHE_NAMESPACE, ticker)
    return to_chart_series(_stored_series(ticker), VALUE_KEY)
