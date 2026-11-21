"""Per-endpoint accounting of what we spend at each data provider.

FMP bills on a rolling 30-day data volume and only warns once usage passes
90% of the plan. That warning names no endpoint, so without local numbers
the next step is reading nginx logs and guessing. Every outbound call
records its endpoint, its response size and whether it was rejected, which
turns "what is eating the quota" into a query.

Accounting is best-effort by design: a failure here must never take down a
data fetch that is otherwise working.

Inside a request the calls are summed in memory and written once, when the
request ends (``batched_provider_usage``, installed by
``ProviderUsageBatchMiddleware``). A cold company page makes one FMP call
per statement, and a write per call was the N+1 Sentry kept filing on the
quote endpoints. The write sits in a ``finally``, so it still happens when
the view raises and when gunicorn aborts a timed-out worker, which it does
by raising ``SystemExit`` inside it. Only a SIGKILL loses a request's
counts, a handful of calls in a ledger that exists to rank endpoints.

Outside a batch (Celery tasks, management commands, the batch endpoint's
worker threads, which do not inherit the request's context) every call is
written as it happens, as one insert-or-increment statement.
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from typing import Iterator

from django.db import connection
from django.utils import timezone

from .models import ProviderUsageDay

logger = logging.getLogger(__name__)

UsageKey = tuple[str, date, str]


class _PendingUsage:
    """Calls and bytes counted inside one batch, keyed by (provider, date, endpoint)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._totals: dict[UsageKey, list[int]] = defaultdict(lambda: [0, 0])

    def add(self, key: UsageKey, response_bytes: int) -> None:
        with self._lock:
            totals = self._totals[key]
            totals[0] += 1
            totals[1] += response_bytes

    def drain(self) -> dict[UsageKey, tuple[int, int]]:
        with self._lock:
            drained = {key: (calls, size) for key, (calls, size) in self._totals.items()}
            self._totals.clear()
        return drained


# The open batch for the current request, or None to write every call
# straight away.
_pending_usage: ContextVar[_PendingUsage | None] = ContextVar(
    "pending_provider_usage", default=None
)


def record_provider_call(provider: str, endpoint: str, response_bytes: int) -> None:
    """Count one call and `response_bytes` against today's row for this endpoint."""
    key = (provider, timezone.localdate(), endpoint)
    pending = _pending_usage.get()
    if pending is not None:
        pending.add(key, response_bytes)
        return
    _write_usage_safely({key: (1, response_bytes)})


@contextmanager
def batched_provider_usage() -> Iterator[None]:
    """Sum the calls made inside this block and write them once at the end.

    A block opened inside another one joins it, so the outer block writes
    everything.
    """
    if _pending_usage.get() is not None:
        yield
        return

    pending = _PendingUsage()
    token = _pending_usage.set(pending)
    try:
        yield
    finally:
        _pending_usage.reset(token)
        _write_usage_safely(pending.drain())


def _write_usage_safely(usage: dict[UsageKey, tuple[int, int]]) -> None:
    if not usage:
        return
    try:
        _write_usage(usage)
    except Exception:
        logger.warning(
            "Could not record provider usage for %s",
            sorted(endpoint for _, _, endpoint in usage),
            exc_info=True,
        )


def _write_usage(usage: dict[UsageKey, tuple[int, int]]) -> None:
    """Insert or increment every row in one statement.

    Django's ``bulk_create(update_conflicts=True)`` can only overwrite a
    column with the incoming value, and these columns are counters, so the
    upsert is written out. It also settles the race two processes used to
    have over creating the same row: the loser increments instead of
    raising an IntegrityError.
    """
    table = connection.ops.quote_name(ProviderUsageDay._meta.db_table)
    rows = sorted(usage.items())
    placeholders = ", ".join(["(%s, %s, %s, %s, %s)"] * len(rows))
    parameters = [
        value
        for (provider, usage_date, endpoint), (calls, size) in rows
        for value in (provider, usage_date, endpoint, calls, size)
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {table} "
            "(provider, date, endpoint, call_count, bytes_downloaded) "
            f"VALUES {placeholders} "
            "ON CONFLICT (provider, date, endpoint) DO UPDATE SET "
            f"call_count = {table}.call_count + EXCLUDED.call_count, "
            f"bytes_downloaded = {table}.bytes_downloaded + EXCLUDED.bytes_downloaded",
            parameters,
        )
