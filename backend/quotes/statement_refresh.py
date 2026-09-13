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

The safety net needs a memory of its own. 1,848 of the 18,158 companies
in the universe have no statements at all · FMP simply has nothing to
give · and asking again every week costs 0.74 GB to re-confirm absence.
Each attempt is stamped on `Ticker.statements_last_attempted_at`, so the
retry can be spaced a month out, jittered per company so that everything
resynced on one Sunday does not come due together on a later one.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from hashlib import sha256

from django.db.models import Max
from django.utils import timezone

from .models import QuarterlyEarnings, Ticker

# Past this, the newest quarter we hold is stale by any reporting calendar:
# two quarters plus filing lag. A company this far behind is either between
# reports in a way the calendar missed, or has stopped filing.
LONG_OVERDUE_DAYS = 180

# How long a company with nothing new waits between retries. Slow on
# purpose: these are mostly companies that will still have nothing new
# next month.
RETRY_OVERDUE_AFTER_DAYS = 30

# Spread of the retry window. Without it, every company resynced on one
# Sunday comes due again on the same later Sunday, and the weekly saving
# reappears as a monthly spike.
MAX_RETRY_JITTER_DAYS = 14

_BRAZILIAN_TICKER_PATTERN = re.compile(r"^[A-Z]+\d+$")


def _is_brazilian(symbol: str) -> bool:
    return bool(_BRAZILIAN_TICKER_PATTERN.match(symbol.upper()))


def retry_window_days(symbol: str) -> int:
    """This company's retry window, stable across runs and spread across
    the herd. Derived from the symbol rather than randomised so that a
    company's turn does not move every time the job runs."""
    digest = sha256(symbol.upper().encode()).digest()
    return RETRY_OVERDUE_AFTER_DAYS + digest[0] % (MAX_RETRY_JITTER_DAYS + 1)


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
    now = timezone.now()
    long_overdue_before = today - timedelta(days=LONG_OVERDUE_DAYS)

    stored = {
        row["ticker"]: (row["newest_quarter_end"], row["last_fetched_at"])
        for row in QuarterlyEarnings.objects.filter(ticker__in=symbols)
        .values("ticker")
        .annotate(
            newest_quarter_end=Max("end_date"),
            last_fetched_at=Max("fetched_at"),
        )
    }
    last_attempted = dict(
        Ticker.objects.filter(symbol__in=symbols).values_list(
            "symbol", "statements_last_attempted_at"
        )
    )

    needing: set[str] = set()
    for symbol in symbols:
        if _is_brazilian(symbol) or symbol in recent_reporters:
            needing.add(symbol)
            continue

        newest_quarter_end, last_fetched_at = stored.get(symbol, (None, None))
        has_nothing_stored = newest_quarter_end is None
        is_long_overdue = (
            newest_quarter_end is not None and newest_quarter_end < long_overdue_before
        )
        if not (has_nothing_stored or is_long_overdue):
            continue

        # Both groups are asking the provider for something it has not
        # given us before, so both wait out the same backoff. The last
        # attempt is whichever is more recent: the stamp the weekly job
        # leaves, or the write a successful sync left on the statements.
        attempted_at = max(
            filter(None, (last_attempted.get(symbol), last_fetched_at)),
            default=None,
        )
        retry_before = now - timedelta(days=retry_window_days(symbol))
        if attempted_at is None or attempted_at < retry_before:
            needing.add(symbol)

    return needing
