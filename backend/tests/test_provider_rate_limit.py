"""Tests for the shared outbound rate limiter that paces provider calls.

FMP rejects anything past its per-minute allowance with a 429 whose body
reads "Limit Reach . Please upgrade your plan". The weekly fundamentals
command used to issue roughly 650 calls a minute against an allowance of
300, so half of every run failed and the wasted calls still counted. The
limiter paces callers instead of discovering the ceiling by hitting it.
"""
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache

from quotes.rate_limiter import RateLimiter


class FakeClock:
    """A clock that only moves when the code under test sleeps."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class TestRateLimiterUnderTheLimit:
    def test_calls_within_the_allowance_never_sleep(self):
        clock = FakeClock()
        limiter = RateLimiter(
            "test-provider",
            max_calls_per_minute=3,
            sleep=clock.sleep,
            clock=clock.time,
        )

        for _ in range(3):
            limiter.acquire()

        assert clock.sleeps == []


class TestRateLimiterAtTheLimit:
    def test_the_call_past_the_allowance_waits_for_the_next_window(self):
        clock = FakeClock(start=10.0)
        limiter = RateLimiter(
            "test-provider",
            max_calls_per_minute=2,
            sleep=clock.sleep,
            clock=clock.time,
        )

        limiter.acquire()
        limiter.acquire()
        limiter.acquire()

        # 10s into the minute, so 50s remain before the window rolls over.
        assert clock.sleeps == [50.0]

    def test_the_allowance_refills_in_the_next_window(self):
        clock = FakeClock()
        limiter = RateLimiter(
            "test-provider",
            max_calls_per_minute=2,
            sleep=clock.sleep,
            clock=clock.time,
        )

        limiter.acquire()
        limiter.acquire()
        limiter.acquire()  # sleeps 60s into the next window
        clock.sleeps.clear()

        limiter.acquire()

        assert clock.sleeps == []


class TestRateLimiterIsSharedAcrossProcesses:
    """The web workers, the Celery workers and the systemd commands all call
    FMP. A limiter that only counted its own process would let the fleet
    multiply the allowance by the number of processes, so the counter lives
    in the shared cache and any instance with the same name sees it."""

    def test_a_second_instance_sees_the_first_instances_calls(self):
        clock = FakeClock()
        first = RateLimiter(
            "test-provider", max_calls_per_minute=2, sleep=clock.sleep, clock=clock.time
        )
        second = RateLimiter(
            "test-provider", max_calls_per_minute=2, sleep=clock.sleep, clock=clock.time
        )

        first.acquire()
        second.acquire()
        second.acquire()

        assert clock.sleeps == [60.0]

    def test_a_different_name_keeps_its_own_allowance(self):
        clock = FakeClock()
        fmp_limiter = RateLimiter(
            "fmp-test", max_calls_per_minute=1, sleep=clock.sleep, clock=clock.time
        )
        brapi_limiter = RateLimiter(
            "brapi-test", max_calls_per_minute=1, sleep=clock.sleep, clock=clock.time
        )

        fmp_limiter.acquire()
        brapi_limiter.acquire()

        assert clock.sleeps == []


class TestRateLimiterDisabled:
    def test_a_limit_of_zero_never_throttles(self):
        clock = FakeClock()
        limiter = RateLimiter(
            "test-provider",
            max_calls_per_minute=0,
            sleep=clock.sleep,
            clock=clock.time,
        )

        for _ in range(50):
            limiter.acquire()

        assert clock.sleeps == []


class TestFMPClientIsPaced:
    """Every FMP request goes through the limiter, not just the batch jobs."""

    @patch("quotes.fmp.requests.get")
    @patch("quotes.fmp._RATE_LIMITER")
    def test_get_acquires_before_requesting(self, mock_limiter, mock_requests_get):
        call_order = []
        mock_limiter.acquire.side_effect = lambda: call_order.append("acquire")

        response = Mock(status_code=200, content=b"[]")
        response.json.return_value = []
        mock_requests_get.side_effect = lambda *args, **kwargs: (
            call_order.append("request") or response
        )

        from quotes.fmp import _get

        _get("/stable/quote", params={"symbol": "AAPL"})

        assert call_order == ["acquire", "request"]


class TestRateLimiterCostsOneRoundTripPerCall:
    """Sentry flagged `/api/quote/{ticker}/` as an N+1 on a cache write.

    The offending span was `SET ':1:rate_limiter:fmp:<window>'`, repeated
    once per outbound call: `acquire` used to run `cache.add` before every
    `cache.incr`, and after the first call of a window that `add` is a
    guaranteed no-op. A cold company page makes several provider calls, so
    the request paid two Redis round trips per call to write a value that
    was already there.

    Incrementing first inverts it: the ordinary call is one round trip,
    and only the first caller of a window pays for creating the counter.
    """

    def test_a_call_in_an_established_window_does_not_rewrite_the_counter(self):
        clock = FakeClock()
        limiter = RateLimiter(
            "test-provider", max_calls_per_minute=100, sleep=clock.sleep, clock=clock.time
        )
        limiter.acquire()  # creates the counter for this window

        with patch("quotes.rate_limiter.cache.add") as mock_add:
            for _ in range(10):
                limiter.acquire()

        mock_add.assert_not_called()

    def test_the_first_call_of_a_window_still_creates_the_counter(self):
        clock = FakeClock()
        limiter = RateLimiter(
            "test-provider", max_calls_per_minute=2, sleep=clock.sleep, clock=clock.time
        )

        limiter.acquire()

        assert cache.get(limiter.window_cache_key(0)) == 1

    def test_two_processes_racing_to_create_the_counter_both_get_counted(self):
        """`add` losing the race must not lose the caller's call.

        Both instances find no counter and both try to create it. The one
        whose `add` is refused has to fall back to incrementing, or the
        window would undercount and the allowance would be overspent.
        """
        clock = FakeClock()
        first = RateLimiter(
            "test-provider", max_calls_per_minute=10, sleep=clock.sleep, clock=clock.time
        )
        second = RateLimiter(
            "test-provider", max_calls_per_minute=10, sleep=clock.sleep, clock=clock.time
        )
        real_add = cache.add
        added_by_the_loser = []

        def add_that_the_second_caller_loses(key, *args, **kwargs):
            if added_by_the_loser:
                return False
            added_by_the_loser.append(key)
            return real_add(key, *args, **kwargs)

        with patch("quotes.rate_limiter.cache.add", side_effect=add_that_the_second_caller_loses):
            first.acquire()
            second.acquire()

        assert cache.get(first.window_cache_key(0)) == 2

    def test_a_cache_that_is_down_still_allows_the_call(self):
        clock = FakeClock()
        limiter = RateLimiter(
            "test-provider", max_calls_per_minute=1, sleep=clock.sleep, clock=clock.time
        )

        with patch("quotes.rate_limiter.cache.incr", side_effect=ConnectionError("redis is down")), \
             patch("quotes.rate_limiter.cache.add", side_effect=ConnectionError("redis is down")):
            limiter.acquire()

        assert clock.sleeps == []
