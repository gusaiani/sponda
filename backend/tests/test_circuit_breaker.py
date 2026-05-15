"""Tests for the Redis-backed circuit breaker.

Wraps an outbound provider call. After N consecutive failures the
breaker opens and short-circuits subsequent calls for ``cool_down``
seconds, raising ``CircuitOpenError`` instead of executing the call.
A single successful call closes the breaker again.
"""
import time

import pytest
from django.core.cache import cache

from quotes.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class _BoomError(Exception):
    pass


class TestCircuitBreaker:
    def test_passes_through_on_success(self):
        breaker = CircuitBreaker(name="fmp", failure_threshold=3, cool_down_seconds=60)
        assert breaker.call(lambda: "ok") == "ok"

    def test_opens_after_threshold_failures(self):
        breaker = CircuitBreaker(name="fmp", failure_threshold=2, cool_down_seconds=60)

        def boom():
            raise _BoomError("nope")

        with pytest.raises(_BoomError):
            breaker.call(boom)
        with pytest.raises(_BoomError):
            breaker.call(boom)
        # Third call short-circuits.
        with pytest.raises(CircuitOpenError):
            breaker.call(boom)

    def test_does_not_invoke_function_when_open(self):
        breaker = CircuitBreaker(name="fmp", failure_threshold=1, cool_down_seconds=60)
        called = []

        with pytest.raises(_BoomError):
            breaker.call(lambda: (_raise(_BoomError("x"))))

        with pytest.raises(CircuitOpenError):
            breaker.call(lambda: called.append("nope") or "ok")

        assert called == []

    def test_success_resets_failure_count(self):
        breaker = CircuitBreaker(name="fmp", failure_threshold=3, cool_down_seconds=60)

        def boom():
            raise _BoomError("nope")

        with pytest.raises(_BoomError):
            breaker.call(boom)
        with pytest.raises(_BoomError):
            breaker.call(boom)
        # Two failures; one success resets.
        breaker.call(lambda: "ok")
        # Fresh failures should not immediately trip the breaker.
        with pytest.raises(_BoomError):
            breaker.call(boom)
        with pytest.raises(_BoomError):
            breaker.call(boom)

    def test_breakers_are_isolated_by_name(self):
        a = CircuitBreaker(name="fmp", failure_threshold=1, cool_down_seconds=60)
        b = CircuitBreaker(name="brapi", failure_threshold=1, cool_down_seconds=60)

        with pytest.raises(_BoomError):
            a.call(lambda: (_raise(_BoomError("x"))))
        # B is unaffected.
        assert b.call(lambda: "ok") == "ok"

    def test_breaker_recovers_after_cool_down(self, monkeypatch):
        breaker = CircuitBreaker(name="fmp", failure_threshold=1, cool_down_seconds=1)

        with pytest.raises(_BoomError):
            breaker.call(lambda: (_raise(_BoomError("x"))))

        with pytest.raises(CircuitOpenError):
            breaker.call(lambda: "ok")

        # Simulate cool_down elapsing by deleting the open marker.
        cache.delete(breaker.open_cache_key)
        # After cool-down, calls are allowed through again.
        assert breaker.call(lambda: "ok") == "ok"


def _raise(exc):
    raise exc
