"""Tests for the Redis-backed circuit breaker.

Wraps an outbound provider call. After N consecutive failures the
breaker opens and short-circuits subsequent calls for ``cool_down``
seconds, raising ``CircuitOpenError`` instead of executing the call.
A single successful call closes the breaker again.

The shared open marker is polled, not read before every call: see
``TestOpenMarkerPolling``.
"""

import pytest
from django.core.cache import cache

from quotes import circuit_breaker as circuit_breaker_module
from quotes.circuit_breaker import (
    OPEN_MARKER_POLL_SECONDS,
    CircuitBreaker,
    CircuitOpenError,
    forget_local_breaker_state,
)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class _BoomError(Exception):
    pass


class _FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds

    def advance(self, seconds: float) -> None:
        self.seconds += seconds


class _CacheSpy:
    """Counts reads of one key, delegating every operation to the cache."""

    def __init__(self, watched_key: str) -> None:
        self.watched_key = watched_key
        self.read_count = 0

    def get(self, key, *args, **kwargs):
        if key == self.watched_key:
            self.read_count += 1
        return cache.get(key, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(cache, name)


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

    def test_breaker_recovers_after_cool_down(self):
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=1, cool_down_seconds=1, clock=clock
        )

        with pytest.raises(_BoomError):
            breaker.call(lambda: (_raise(_BoomError("x"))))

        with pytest.raises(CircuitOpenError):
            breaker.call(lambda: "ok")

        # Simulate cool_down elapsing by deleting the open marker.
        cache.delete(breaker.open_cache_key)
        clock.advance(OPEN_MARKER_POLL_SECONDS)
        # After cool-down, calls are allowed through again.
        assert breaker.call(lambda: "ok") == "ok"

    def test_honours_a_marker_another_process_left_behind(self):
        cache.set("circuit_breaker:fmp:open", True, timeout=60)
        breaker = CircuitBreaker(name="fmp", failure_threshold=3, cool_down_seconds=60)

        with pytest.raises(CircuitOpenError):
            breaker.call(lambda: "ok")


class TestOpenMarkerPolling:
    """The shared marker is read at most once per poll interval.

    Reading it before every provider call costs a cache round trip per
    call, which shows up as a repeated span on every trace. The reading
    is reused between polls instead. Staleness is bounded by the very
    situation the breaker exists for: a call against a sick provider
    takes longer than the poll interval, so the next check re-reads the
    marker anyway.
    """

    def test_quick_calls_share_one_reading(self, monkeypatch):
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=3, cool_down_seconds=60, clock=clock
        )
        spy = _CacheSpy(breaker.open_cache_key)
        monkeypatch.setattr(circuit_breaker_module, "cache", spy)

        for _ in range(4):
            assert breaker.call(lambda: "ok") == "ok"

        assert spy.read_count == 1

    def test_marker_is_read_again_after_the_poll_interval(self, monkeypatch):
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=3, cool_down_seconds=60, clock=clock
        )
        spy = _CacheSpy(breaker.open_cache_key)
        monkeypatch.setattr(circuit_breaker_module, "cache", spy)

        breaker.call(lambda: "ok")
        clock.advance(OPEN_MARKER_POLL_SECONDS)
        breaker.call(lambda: "ok")

        assert spy.read_count == 2

    def test_picks_up_another_process_opening_the_breaker(self):
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=3, cool_down_seconds=60, clock=clock
        )
        breaker.call(lambda: "ok")

        # Another process trips the breaker mid-request.
        cache.set(breaker.open_cache_key, True, timeout=60)
        clock.advance(OPEN_MARKER_POLL_SECONDS)

        with pytest.raises(CircuitOpenError):
            breaker.call(lambda: "ok")

    def test_opening_locally_short_circuits_the_very_next_call(self):
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=1, cool_down_seconds=60, clock=clock
        )

        with pytest.raises(_BoomError):
            breaker.call(lambda: (_raise(_BoomError("x"))))

        # No time has passed, so only the local reading can know.
        with pytest.raises(CircuitOpenError):
            breaker.call(lambda: "ok")

    def test_readings_do_not_leak_once_they_are_dropped(self):
        """A reading outlives ``cache.clear()``, so tests drop it by hand."""
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=1, cool_down_seconds=60, clock=clock
        )

        with pytest.raises(_BoomError):
            breaker.call(lambda: (_raise(_BoomError("x"))))

        cache.clear()
        forget_local_breaker_state()

        assert breaker.call(lambda: "ok") == "ok"

    def test_a_slow_call_always_costs_a_fresh_reading(self, monkeypatch):
        """The dangerous case never rides a stale reading."""
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=3, cool_down_seconds=60, clock=clock
        )
        spy = _CacheSpy(breaker.open_cache_key)
        monkeypatch.setattr(circuit_breaker_module, "cache", spy)

        def slow_call():
            clock.advance(OPEN_MARKER_POLL_SECONDS * 2)
            return "ok"

        breaker.call(slow_call)
        breaker.call(slow_call)

        assert spy.read_count == 2


def _raise(exc):
    raise exc


class _DeleteSpy:
    """Counts deletes of one key, delegating every operation to the cache."""

    def __init__(self, watched_key: str) -> None:
        self.watched_key = watched_key
        self.delete_count = 0

    def delete(self, key, *args, **kwargs):
        if key == self.watched_key:
            self.delete_count += 1
        return cache.delete(key, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(cache, name)


class TestFailureCounterReset:
    """A success clears the shared failure counter, but not on every call.

    Clearing it after every successful call cost one `DEL` per provider
    call, and a cold company page makes several: Sentry's trace showed
    three identical `DEL circuit_breaker:fmp:failures` in one request. A
    success now clears the counter when this process has seen a failure
    since its last clear, or when the last clear is older than the poll
    interval, so a failure another process counted is still forgiven
    within a second.
    """

    def test_quick_successes_clear_the_counter_once(self, monkeypatch):
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=3, cool_down_seconds=60, clock=clock
        )
        spy = _DeleteSpy(breaker.failure_cache_key)
        monkeypatch.setattr(circuit_breaker_module, "cache", spy)

        for _ in range(4):
            breaker.call(lambda: "ok")

        assert spy.delete_count == 1

    def test_a_local_failure_is_always_cleared_by_the_next_success(self):
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=3, cool_down_seconds=60, clock=clock
        )
        breaker.call(lambda: "ok")

        with pytest.raises(_BoomError):
            breaker.call(lambda: _raise(_BoomError("x")))
        breaker.call(lambda: "ok")

        assert cache.get(breaker.failure_cache_key) is None

    def test_another_process_failures_are_cleared_after_the_interval(self):
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=3, cool_down_seconds=60, clock=clock
        )
        breaker.call(lambda: "ok")

        cache.set(breaker.failure_cache_key, 2, timeout=60)
        clock.advance(OPEN_MARKER_POLL_SECONDS)
        breaker.call(lambda: "ok")

        assert cache.get(breaker.failure_cache_key) is None

    def test_dropped_state_clears_the_counter_on_the_next_success(self):
        """`forget_local_breaker_state` must not let one test's clear skip the next."""
        clock = _FakeClock()
        breaker = CircuitBreaker(
            name="fmp", failure_threshold=3, cool_down_seconds=60, clock=clock
        )
        breaker.call(lambda: "ok")

        cache.set(breaker.failure_cache_key, 2, timeout=60)
        forget_local_breaker_state()
        breaker.call(lambda: "ok")

        assert cache.get(breaker.failure_cache_key) is None
