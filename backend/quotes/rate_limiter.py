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
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from django.core.cache import cache

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60

# The window key outlives its window so a clock skew between processes
# cannot resurrect a counter that another process is still incrementing.
_COUNTER_TTL_SECONDS = WINDOW_SECONDS * 2


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
        """Return once the caller may issue its request, sleeping if needed."""
        if self.max_calls_per_minute <= 0:
            return

        while True:
            now = self._clock()
            window_start = int(now // WINDOW_SECONDS) * WINDOW_SECONDS
            calls_this_window = self._increment(self.window_cache_key(window_start))

            if calls_this_window <= self.max_calls_per_minute:
                return

            seconds_until_next_window = max(window_start + WINDOW_SECONDS - now, 0.0)
            logger.debug(
                "Rate limiter '%s' full (%s calls); waiting %.1fs",
                self.name,
                calls_this_window,
                seconds_until_next_window,
            )
            self._sleep(seconds_until_next_window)

    def _increment(self, cache_key: str) -> int:
        """The number of calls taken in this window, counting this one.

        A cache that is down must not stop the application from talking to
        its providers, so an unusable counter degrades to "allowed".
        """
        try:
            cache.add(cache_key, 0, timeout=_COUNTER_TTL_SECONDS)
            return cache.incr(cache_key)
        except ValueError:
            # The key expired between the add and the incr. Whatever the
            # true count was, the window is about to roll over anyway.
            return 1
        except Exception:
            logger.warning(
                "Rate limiter '%s' could not read its counter; allowing the call",
                self.name,
                exc_info=True,
            )
            return 1
