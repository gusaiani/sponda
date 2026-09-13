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
  wholesale.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from django.core.cache import cache
from django.db.models import Max

from . import fmp
from .fmp import FMPError
from .models import DailyClosePrice

logger = logging.getLogger(__name__)

HISTORY_START_DATE = date(2000, 1, 1)

# How far back a top-up reaches past the newest stored day. Long enough to
# cover a long weekend plus a holiday, and to give split detection several
# days of overlap to compare rather than betting on a single close.
TOPUP_OVERLAP_DAYS = 5

# How long a successful check keeps a ticker off the provider. Closes move
# once a day, so four checks a day is already generous; the point is that
# request volume cannot drive provider volume.
TOPUP_INTERVAL_SECONDS = 6 * 60 * 60

# Two closes for the same day are "the same price" within this relative
# tolerance. Anything larger is a re-adjustment (a split), not rounding.
SPLIT_DETECTION_TOLERANCE = 0.001


def _freshness_cache_key(ticker: str) -> str:
    return f"price_store:checked:{ticker.upper()}"


def _stored_series(ticker: str) -> list[tuple[date, float]]:
    rows = (
        DailyClosePrice.objects.filter(ticker=ticker)
        .order_by("date")
        .values_list("date", "close")
    )
    return [(row_date, float(close)) for row_date, close in rows]


def _to_chart_series(series: list[tuple[date, float]]) -> list[dict]:
    """The shape the views and `price_history` read: unix date, adjusted close."""
    return [
        {
            "date": int(
                datetime(
                    close_date.year,
                    close_date.month,
                    close_date.day,
                    tzinfo=timezone.utc,
                ).timestamp()
            ),
            "adjustedClose": close,
        }
        for close_date, close in series
    ]


def _parse_provider_rows(rows: list[dict]) -> dict[date, float]:
    """Provider rows as {date: close}, dropping anything incomplete."""
    parsed: dict[date, float] = {}
    for row in rows or []:
        raw_date = row.get("date")
        # `light` calls the column `price`; `full` called it `close`. Reading
        # both keeps this working if the endpoint is ever switched back.
        close = row.get("price", row.get("close"))
        if not raw_date or close is None:
            continue
        try:
            parsed[date.fromisoformat(str(raw_date)[:10])] = float(close)
        except (TypeError, ValueError):
            continue
    return parsed


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


def _fetch_full_history(ticker: str) -> dict[date, float]:
    return _parse_provider_rows(
        fmp.fetch_historical_prices(ticker, start_date=HISTORY_START_DATE)
    )


def get_daily_closes(ticker: str) -> list[dict]:
    """Daily adjusted closes for `ticker`, oldest first, kept current.

    Raises :class:`FMPError` only when there is nothing to serve: no stored
    rows and no rows from the provider either. A provider failure with a
    stored series behind it degrades to the stored series, which is a day
    or two stale at worst.
    """
    ticker = ticker.upper()
    stored = _stored_series(ticker)

    if stored and cache.get(_freshness_cache_key(ticker)):
        return _to_chart_series(stored)

    if not stored:
        fetched = _fetch_full_history(ticker)
        if not fetched:
            raise FMPError(f"No historical price data for ticker {ticker}")
        _write_closes(ticker, fetched)
        cache.set(_freshness_cache_key(ticker), True, TOPUP_INTERVAL_SECONDS)
        return _to_chart_series(sorted(fetched.items()))

    newest_stored_date = (
        DailyClosePrice.objects.filter(ticker=ticker).aggregate(Max("date"))["date__max"]
    )
    topup_start = newest_stored_date - timedelta(days=TOPUP_OVERLAP_DAYS)

    try:
        fetched = _parse_provider_rows(
            fmp.fetch_historical_prices(ticker, start_date=topup_start)
        )
    except FMPError as error:
        # The stored series is the whole point: a provider outage or a spent
        # quota costs freshness, not the page.
        logger.warning("Price top-up failed for %s: %s", ticker, error)
        return _to_chart_series(stored)

    if _overlap_disagrees(ticker, stored, fetched):
        try:
            fetched = _fetch_full_history(ticker)
        except FMPError as error:
            logger.warning("Price refetch failed for %s: %s", ticker, error)
            return _to_chart_series(stored)
        if fetched:
            DailyClosePrice.objects.filter(ticker=ticker).delete()
            _write_closes(ticker, fetched)
            cache.set(_freshness_cache_key(ticker), True, TOPUP_INTERVAL_SECONDS)
            return _to_chart_series(sorted(fetched.items()))

    if fetched:
        _write_closes(ticker, fetched)

    cache.set(_freshness_cache_key(ticker), True, TOPUP_INTERVAL_SECONDS)
    return _to_chart_series(_stored_series(ticker))
