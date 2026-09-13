"""Deciding which companies could plausibly have a statement we do not hold.

The weekly refresh used to refetch income statement, cash flow statement
and balance sheet for every company in the universe: 54,000 calls and
7.3 GB to discover that almost nobody had filed anything that week. A
company reports four times a year, and FMP publishes a calendar of who
reported when, so the set of companies worth refetching is small and
knowable in advance.

Three reasons to refetch, and nothing else:

1. **They reported.** The company appears on the earnings calendar for the
   window since the last run.
2. **We hold nothing.** A company with no statements has everything to
   gain from a fetch and nothing to lose.
3. **The safety net.** The calendar does not cover every thinly traded
   foreign issuer. A company whose newest quarter has gone properly stale
   is retried on a slow cadence rather than never.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from django.db.models import Max
from django.utils import timezone

from .models import QuarterlyEarnings

# Past this, the newest quarter we hold is stale by any reporting calendar:
# two quarters plus filing lag. A company this far behind is either between
# reports in a way the calendar missed, or has stopped filing.
LONG_OVERDUE_DAYS = 180

# How long a long-overdue company waits between retries. Slow on purpose:
# these are mostly companies that will still be overdue next month.
RETRY_OVERDUE_AFTER_DAYS = 30

_BRAZILIAN_TICKER_PATTERN = re.compile(r"^[A-Z]+\d+$")


def _is_brazilian(symbol: str) -> bool:
    return bool(_BRAZILIAN_TICKER_PATTERN.match(symbol.upper()))


def symbols_needing_statement_refresh(
    symbols: list[str],
    recent_reporters: set[str],
    today: date | None = None,
) -> set[str]:
    """The subset of `symbols` whose statements are worth refetching now.

    `recent_reporters` is who FMP's earnings calendar says reported since
    the last run. Brazilian tickers are always included: their statements
    come from BRAPI and CVM rather than FMP, so they are absent from that
    calendar and cost nothing against this quota.
    """
    today = today or timezone.localdate()
    long_overdue_before = today - timedelta(days=LONG_OVERDUE_DAYS)
    retry_before = timezone.now() - timedelta(days=RETRY_OVERDUE_AFTER_DAYS)

    stored = {
        row["ticker"]: (row["newest_quarter_end"], row["last_fetched_at"])
        for row in QuarterlyEarnings.objects.filter(ticker__in=symbols)
        .values("ticker")
        .annotate(
            newest_quarter_end=Max("end_date"),
            last_fetched_at=Max("fetched_at"),
        )
    }

    needing: set[str] = set()
    for symbol in symbols:
        if _is_brazilian(symbol):
            needing.add(symbol)
            continue

        if symbol in recent_reporters:
            needing.add(symbol)
            continue

        newest_quarter_end, last_fetched_at = stored.get(symbol, (None, None))
        if newest_quarter_end is None:
            needing.add(symbol)
            continue

        is_long_overdue = newest_quarter_end < long_overdue_before
        waited_long_enough = last_fetched_at is None or last_fetched_at < retry_before
        if is_long_overdue and waited_long_enough:
            needing.add(symbol)

    return needing
