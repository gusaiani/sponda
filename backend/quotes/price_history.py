"""Reading a dated value out of a historical series, by date.

Both the Fundamentos table and the multiples chart value a year at the close
of that year. For a filer that does not close on 31 December, "that year"
ends on a day the series has no special knowledge of, so a series is indexed
by date and searched rather than bucketed by calendar year.

Two series are read this way: adjusted closes, and the market cap reported
on each trading day. The lookup is the same for both, so it is written once
over `(date, value)` pairs.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timezone

DatedValue = tuple[date, float]


def _series_by_date(points: list[dict], value_field: str) -> list[DatedValue]:
    """Dated values as (date, value), oldest first, dropping incomplete points.

    Sorted so `value_on_or_before` can binary-search it. Providers disagree
    on direction · FMP returns newest first, BRAPI oldest first · so the
    order is imposed here rather than assumed.
    """
    series: list[DatedValue] = []
    for point in points or []:
        timestamp = point.get("date")
        value = point.get(value_field)
        if timestamp is None or value is None:
            continue
        point_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        series.append((point_date, value))
    series.sort(key=lambda dated_value: dated_value[0])
    return series


def closes_by_date(historical_prices: list[dict]) -> list[DatedValue]:
    """Adjusted closes as (date, price), oldest first."""
    return _series_by_date(historical_prices, "adjustedClose")


def market_caps_by_date(historical_market_caps: list[dict]) -> list[DatedValue]:
    """Reported market caps as (date, market_cap), oldest first."""
    return _series_by_date(historical_market_caps, "marketCap")


def value_on_or_before(series: list[DatedValue], target: date) -> float | None:
    """The last value at or before `target`.

    A fiscal year is valued on the day it closed, which for an off-calendar
    filer is not 31 December. Salesforce's fiscal 2026 ended on 31 January
    2026, and pricing it at the previous December's close would carry a
    month of price movement into that year's multiples.

    None when the series starts after `target`, which is the honest answer:
    there is no value to price the year at.
    """
    if not series:
        return None
    index = bisect_right(series, target, key=lambda dated_value: dated_value[0])
    if index == 0:
        return None
    return series[index - 1][1]
