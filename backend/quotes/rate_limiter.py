"""A per-minute allowance for outbound provider calls, shared fleet-wide.

FMP answers anything past its per-minute allowance with a 429 whose body
reads "Limit Reach . Please upgrade your plan". Those rejections still
spend the account's data allowance, so discovering the ceiling by hitting
it is the most expensive way to find it: the weekly fundamentals command
ran at roughly 650 calls a minute against an allowance of 300 and lost
half of every run to rejections.

The counter lives in the shared cache rather than in process memory. The
web workers, the Celery workers and the systemd commands all call FMP, so
a per-process limiter would let the fleet multiply the allowance by the
number of processes. A fixed one-minute window is used rather than a
sliding one because it matches how the provider counts, and because it
costs a single atomic increment per call.

That increment goes straight to Redis. Django's cache API cannot express
"increment or create" in one command, and the two or three round trips it
takes instead were showing up in Sentry as an N+1 on every endpoint that
paced a provider call. See `_redis_client`.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator

from django.core.cache import cache

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


class RateLimitTimeout(Exception):
    """The allowance could not be had inside the caller's wait budget."""


class _WaitBudget:
    """What is left of one caller's allowance for waiting.

    Mutable and shared for the length of the block, because a single page
    view makes several provider calls. A budget handed out afresh to each
    call would let a request wait its ceiling over and over and still
    outlive the worker timeout it was meant to stay inside.
    """

    def __init__(self, seconds: float) -> None:
        self.remaining = seconds

    def spend(self, seconds: float) -> None:
        self.remaining -= seconds


# What is left of the current caller's waiting allowance. None, the
# default, means "as long as it takes", which is what a Celery task or a
# management command wants: nothing is timing them.
_wait_budget: ContextVar[_WaitBudget | None] = ContextVar(
    "provider_wait_budget", default=None
)


def wait_budget_seconds() -> float | None:
    """What is left of the caller's budget, or None if it may wait forever."""
    budget = _wait_budget.get()
    return None if budget is None else budget.remaining


@contextmanager
def wait_budget(seconds: float | None) -> Iterator[None]:
    """Cap how long provider pacing may block inside this block.

    A request served by gunicorn is on a clock: the worker is aborted if a
    request outlives the worker timeout, and the abort takes down every
    other request that worker was holding. See
    `config.middleware.provider_wait_budget`.
    """
    token = _wait_budget.set(None if seconds is None else _WaitBudget(seconds))
    try:
        yield
    finally:
        _wait_budget.reset(token)


# The window key outlives its window so a clock skew between processes
# cannot resurrect a counter that another process is still incrementing.
_COUNTER_TTL_SECONDS = WINDOW_SECONDS * 2


def _redis_client():
    """The Redis client behind the default cache, or None if there is none.

    Django's cache API has no atomic increment-or-create: `cache.incr`
    asks `EXISTS` before `INCRBY` and raises when the key is missing, and
    `cache.add` is a second `SET NX` on top. Counting one call that way
    costs two or three round trips, and Sentry reports the repeated
    command as an N+1 on whatever endpoint paid for it.

    LocMemCache, which development and the tests use, has no client to
    reach for. Those callers keep the cache API, where the extra round
    trips are in-process and cost nothing.
    """
    backend = getattr(cache, "_cache", None)
    get_client = getattr(backend, "get_client", None)
    if get_client is None:
        return None
    return get_client(None, write=True)


class RateLimiter:
    """Blocks the caller until its call fits inside the current allowance.

    `max_calls_per_minute` of 0 (or less) disables throttling entirely,
    which is how tests and local development opt out.
    """

    def __init__(
        self,
        name: str,
        max_calls_per_minute: int,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.max_calls_per_minute = max_calls_per_minute
        self._sleep = sleep
        self._clock = clock

    def window_cache_key(self, window_start: int) -> str:
        return f"rate_limiter:{self.name}:{window_start}"

    def acquire(self) -> None:
        """Return once the caller may issue its request, sleeping if needed.

        Raises `RateLimitTimeout` when the wait would outlast the caller's
        budget, if it set one. Refusing at once rather than sleeping for
        whatever is left of the budget is deliberate: the call is lost
        either way, and a shorter sleep only spends the worker's time
        before losing it.
        """
        if self.max_calls_per_minute <= 0:
            return

        budget = _wait_budget.get()

        while True:
            now = self._clock()
            window_start = int(now // WINDOW_SECONDS) * WINDOW_SECONDS
            calls_this_window = self._increment(self.window_cache_key(window_start))

            if calls_this_window <= self.max_calls_per_minute:
                return

            seconds_until_next_window = max(window_start + WINDOW_SECONDS - now, 0.0)

            # The budget covers the whole of the caller's waiting, across
            # every provider call it makes, not each sleep in isolation.
            if budget is not None and seconds_until_next_window > budget.remaining:
                raise RateLimitTimeout(
                    f"'{self.name}' needs {seconds_until_next_window:.1f}s, "
                    f"more than the {budget.remaining:.1f}s the caller has left"
                )

            logger.debug(
                "Rate limiter '%s' full (%s calls); waiting %.1fs",
                self.name,
                calls_this_window,
                seconds_until_next_window,
            )
            self._sleep(seconds_until_next_window)
            if budget is not None:
                budget.spend(seconds_until_next_window)

    def _increment(self, cache_key: str) -> int:
        """The number of calls taken in this window, counting this one.

        A cache that is down must not stop the application from talking to
        its providers, so an unusable counter degrades to "allowed".
        """
        try:
            client = _redis_client()
            if client is not None:
                return self._increment_in_redis(client, cache_key)
            return self._increment_through_the_cache_api(cache_key)
        except Exception:
            return self._unusable_counter()

    def _increment_in_redis(self, client, cache_key: str) -> int:
        """Count this call with a single command.

        `INCR` on a key Redis does not hold creates it at zero and returns
        1, so the counter needs no separate create and no existence check.
        Whoever opens the window is the one that gives the counter its
        lifetime.
        """
        redis_key = cache.make_key(cache_key)
        count = client.incr(redis_key)
        if count == 1:
            client.expire(redis_key, _COUNTER_TTL_SECONDS)
        return count

    def _increment_through_the_cache_api(self, cache_key: str) -> int:
        """The same count for a cache with no Redis behind it.

        Two round trips rather than one, which is the right trade for
        LocMemCache: it is in-process, so they cost nothing.
        """
        try:
            return cache.incr(cache_key)
        except ValueError:
            pass  # No counter for this window yet; this caller may be first.

        if cache.add(cache_key, 1, timeout=_COUNTER_TTL_SECONDS):
            return 1
        try:
            # Another process created the counter in between. Its call is
            # already counted, and this one still has to be.
            return cache.incr(cache_key)
        except ValueError:
            # The key expired again. Whatever the true count was, the
            # window is about to roll over anyway.
            return 1

    def _unusable_counter(self) -> int:
        """Log a counter we could not reach, and let the call through."""
        logger.warning(
            "Rate limiter '%s' could not read its counter; allowing the call",
            self.name,
            exc_info=True,
        )
        return 1
