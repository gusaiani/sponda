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
"""
from __future__ import annotations

from typing import Callable, TypeVar

from django.core.cache import cache

T = TypeVar("T")


class CircuitOpenError(Exception):
    """Raised when the breaker short-circuits a call."""


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int,
        cool_down_seconds: int,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cool_down_seconds = cool_down_seconds

    @property
    def failure_cache_key(self) -> str:
        return f"circuit_breaker:{self.name}:failures"

    @property
    def open_cache_key(self) -> str:
        return f"circuit_breaker:{self.name}:open"

    def call(self, fn: Callable[[], T]) -> T:
        if cache.get(self.open_cache_key):
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
            raise
        else:
            cache.delete(self.failure_cache_key)
            return result
