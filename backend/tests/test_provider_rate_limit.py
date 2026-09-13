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
