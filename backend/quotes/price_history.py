"""Reading a share price out of a historical series, by date.

Both the Fundamentos table and the multiples chart value a year at the close
of that year. For a filer that does not close on 31 December, "that year"
ends on a day the price series has no special knowledge of, so the series is
indexed by date and searched rather than bucketed by calendar year.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timezone

Close = tuple[date, float]


def closes_by_date(historical_prices: list[dict]) -> list[Close]:
    """Adjusted closes as (date, price), oldest first.

    Sorted so `close_on_or_before` can binary-search it. Providers disagree
    on direction · FMP returns newest first, BRAPI oldest first · so the
    order is imposed here rather than assumed.
    """
    closes: list[Close] = []
    for point in historical_prices or []:
        timestamp = point.get("date")
        adjusted_close = point.get("adjustedClose")
        if timestamp is None or adjusted_close is None:
            continue
        point_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        closes.append((point_date, adjusted_close))
    closes.sort(key=lambda close: close[0])
    return closes


def close_on_or_before(closes: list[Close], target: date) -> float | None:
    """The last adjusted close at or before `target`.

    A fiscal year is valued on the day it closed, which for an off-calendar
    filer is not 31 December. Salesforce's fiscal 2026 ended on 31 January
    2026, and pricing it at the previous December's close would carry a
    month of price movement into that year's multiples.

    None when the series starts after `target`, which is the honest answer:
    there is no price to value the year at.
    """
    if not closes:
        return None
    index = bisect_right(closes, target, key=lambda close: close[0])
    if index == 0:
        return None
    return closes[index - 1][1]
