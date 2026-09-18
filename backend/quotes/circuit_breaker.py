"""A small Redis-backed circuit breaker for outbound provider calls.

Why this exists: a slow or failing provider (FMP, BRAPI, FRED) can pin
gunicorn workers for the full ``requests`` timeout. With ~60 parallel
home-page calls, a single bad provider easily takes the site down.

Behaviour:

- Wraps a callable. If it raises, the breaker increments a counter
  scoped to the breaker name in the Django cache.
- After ``failure_threshold`` consecutive failures the breaker opens.
  Subsequent calls raise ``CircuitOpenError`` immediately for
  ``cool_down_seconds`` instead of executing the underlying function.
- A single success closes the breaker (resets the counter).

Two callers must use the same ``name`` to share a breaker. Names are
free-form, but in practice they match the provider key (``fmp``,
``brapi``, ``fred``).

The open marker lives in the shared cache so every process sees the
same breaker, but it is polled rather than read before every call: see
``OPEN_MARKER_POLL_SECONDS``.
"""
from __future__ import annotations

import time
import weakref
from typing import Callable, TypeVar

from django.core.cache import cache

T = TypeVar("T")

# How long a process may reuse its last reading of the shared open
# marker. Reading it before every call costs a cache round trip per
# provider call: a single cold company page makes four FMP calls, so
# four round trips and four identical spans on the trace.
#
# The staleness this buys back is bounded by the situation the breaker
# exists for. A healthy provider answers in tens of milliseconds, so a
# whole request rides one reading. A sick one takes seconds to fail, so
# the reading expires between calls and the marker is read again. The
# worst case is one extra in-flight call per process per interval.
#
# Threads inside a worker share the reading. Each field is a single
# attribute assignment, so the worst an interleaving costs is one
# extra read of the marker.
OPEN_MARKER_POLL_SECONDS = 1.0

# Every live breaker, so a reading can be dropped fleet-wide inside one
# process. A reading is process memory: it survives ``cache.clear()``,
# which the test suite relies on to isolate one test from the next.
_LIVE_BREAKERS: weakref.WeakSet = weakref.WeakSet()


def forget_open_readings() -> None:
    """Make every breaker in this process re-read its shared marker."""
    for breaker in _LIVE_BREAKERS:
        breaker.forget_open_reading()


class CircuitOpenError(Exception):
    """Raised when the breaker short-circuits a call."""


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int,
        cool_down_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cool_down_seconds = cool_down_seconds
        self._clock = clock
        self._last_open_reading: bool | None = None
        self._last_open_reading_at = 0.0
        _LIVE_BREAKERS.add(self)

    @property
    def failure_cache_key(self) -> str:
        return f"circuit_breaker:{self.name}:failures"

    @property
    def open_cache_key(self) -> str:
        return f"circuit_breaker:{self.name}:open"

    def is_open(self) -> bool:
        """Whether the breaker is refusing calls, reusing a recent reading."""
        now = self._clock()
        reading_age = now - self._last_open_reading_at
        if (
            self._last_open_reading is not None
            and reading_age < OPEN_MARKER_POLL_SECONDS
        ):
            return self._last_open_reading
        return self._remember_open_reading(bool(cache.get(self.open_cache_key)))

    def forget_open_reading(self) -> None:
        """Discard the last reading so the next call re-reads the marker."""
        self._last_open_reading = None

    def _remember_open_reading(self, is_open: bool) -> bool:
        self._last_open_reading = is_open
        self._last_open_reading_at = self._clock()
        return is_open

    def call(self, fn: Callable[[], T]) -> T:
        if self.is_open():
            raise CircuitOpenError(f"Circuit '{self.name}' is open")
        try:
            result = fn()
        except Exception:
            failures = (cache.get(self.failure_cache_key) or 0) + 1
            cache.set(
                self.failure_cache_key, failures, timeout=self.cool_down_seconds
            )
            if failures >= self.failure_threshold:
                cache.set(
                    self.open_cache_key, True, timeout=self.cool_down_seconds
                )
                # This process just opened the breaker, so it must not wait
                # for the next poll to start refusing calls.
                self._remember_open_reading(True)
            raise
        else:
            cache.delete(self.failure_cache_key)
            return result
