"""The parts every stored daily series shares.

Two series are kept locally rather than refetched per page view: the
closing price (:mod:`quotes.price_store`) and the market cap the provider
observed on each trading day (:mod:`quotes.market_cap_store`). Both reach
back to 2000, both are topped up with the days they are missing, both are
read by date, and both are rate-limited by the same reasoning · request
volume must not drive provider volume.

What differs between them stays in their own modules. Prices are
split-adjusted, so a changed overlap day means the whole stored history is
on the wrong scale; market caps are not, so the same change is a revision
to store and nothing more.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from django.core.cache import cache

# Both series reach back as far as the provider serves. Without an explicit
# `from`, FMP returns only the last few years; the multiples chart and the
# year-end valuations need every year that has fundamentals behind it.
HISTORY_START_DATE = date(2000, 1, 1)

# How far back a top-up reaches past the newest stored day. Long enough to
# cover a long weekend plus a holiday, and to give the price store several
# days of overlap to compare rather than betting on a single close.
TOPUP_OVERLAP_DAYS = 5

# How long a successful check keeps a ticker off the provider. Both series
# move once a day, so four checks a day is already generous; the point is
# that a page hammered by crawlers cannot turn into one provider call per
# request.
TOPUP_INTERVAL_SECONDS = 6 * 60 * 60


def freshness_cache_key(namespace: str, ticker: str) -> str:
    return f"{namespace}:checked:{ticker.upper()}"


def is_fresh(namespace: str, ticker: str) -> bool:
    return bool(cache.get(freshness_cache_key(namespace, ticker)))


def mark_fresh(namespace: str, ticker: str) -> None:
    cache.set(freshness_cache_key(namespace, ticker), True, TOPUP_INTERVAL_SECONDS)


def topup_start_date(newest_stored: date) -> date:
    return newest_stored - timedelta(days=TOPUP_OVERLAP_DAYS)


def parse_provider_rows(rows: list[dict], value_keys: tuple[str, ...]) -> dict[date, float]:
    """Provider rows as {date: value}, dropping anything incomplete.

    `value_keys` are tried in order, which is how one parser reads an
    endpoint that renamed its column (`light` calls the close `price`,
    `full` called it `close`).
    """
    parsed: dict[date, float] = {}
    for row in rows or []:
        raw_date = row.get("date")
        value = next(
            (row[key] for key in value_keys if row.get(key) is not None), None
        )
        if not raw_date or value is None:
            continue
        try:
            parsed[date.fromisoformat(str(raw_date)[:10])] = float(value)
        except (TypeError, ValueError):
            continue
    return parsed


def to_chart_series(
    series: list[tuple[date, float]], value_key: str
) -> list[dict]:
    """The shape the views and `price_history` read: unix date, then value."""
    return [
        {
            "date": int(
                datetime(
                    value_date.year,
                    value_date.month,
                    value_date.day,
                    tzinfo=timezone.utc,
                ).timestamp()
            ),
            value_key: value,
        }
        for value_date, value in series
    ]
