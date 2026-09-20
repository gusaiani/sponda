"""A web worker must not be killed waiting for the FMP allowance to refill.

Sentry recorded `SystemExit: 1` on `/api/quote/{ticker}/`, raised from
gunicorn's `handle_abort` while `RateLimiter.acquire` was 36 seconds into
a sleep. The FMP window held 251 calls against an allowance of 250, so
the limiter did what it is built to do and waited for the window to roll
over. Gunicorn's default timeout is 30 seconds, so the worker was aborted
mid-request instead.

Waiting without limit is right for a Celery task or a management command,
which nothing is timing. It is wrong inside a request: five workers all
sleeping on a saturated minute is the whole web tier, and a killed worker
drops every other request it was holding, not just this one.

So a request carries a budget, and a wait it cannot afford becomes an
ordinary provider error that the view already knows how to degrade.
"""
from unittest.mock import patch

import pytest
import requests
from django.core.cache import cache

from quotes.circuit_breaker import CircuitBreaker
from quotes.rate_limiter import (
    RateLimiter,
    RateLimitTimeout,
    wait_budget,
    wait_budget_seconds,
)


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


def saturated_limiter(clock: FakeClock, allowance: int = 1) -> RateLimiter:
    """A limiter whose allowance is already spent for this window."""
    limiter = RateLimiter(
        "test-provider",
        max_calls_per_minute=allowance,
        sleep=clock.sleep,
        clock=clock.time,
    )
    for _ in range(allowance):
        limiter.acquire()
    clock.sleeps.clear()
    return limiter


class TestWithoutABudget:
    """Celery tasks and management commands still wait as long as it takes."""

    def test_a_caller_with_no_budget_waits_for_the_window(self):
        clock = FakeClock()
        limiter = saturated_limiter(clock)

        limiter.acquire()

        assert clock.sleeps == [60.0]

    def test_no_budget_is_the_default(self):
        assert wait_budget_seconds() is None


class TestWithinTheBudget:
    def test_a_wait_the_request_can_afford_still_happens(self):
        clock = FakeClock(start=55.0)  # 5s left in this window
        limiter = saturated_limiter(clock)

        with wait_budget(10.0):
            limiter.acquire()

        assert clock.sleeps == [5.0]


class TestBeyondTheBudget:
    def test_a_wait_the_request_cannot_afford_is_refused(self):
        clock = FakeClock()
        limiter = saturated_limiter(clock)

        with wait_budget(10.0), pytest.raises(RateLimitTimeout):
            limiter.acquire()

    def test_the_refusal_is_immediate_rather_than_a_shorter_sleep(self):
        """Sleeping for the budget and then failing helps nobody: the
        request is lost either way, and the worker spent the time."""
        clock = FakeClock()
        limiter = saturated_limiter(clock)

        with wait_budget(10.0), pytest.raises(RateLimitTimeout):
            limiter.acquire()

        assert clock.sleeps == []

    def test_the_budget_covers_the_whole_request_not_each_call(self):
        """One cold company page makes several provider calls. A budget
        handed out afresh to each of them would let the request wait its
        ceiling over and over and still outlive the worker timeout."""
        clock = FakeClock()
        limiter = saturated_limiter(clock, allowance=1)

        with wait_budget(90.0), pytest.raises(RateLimitTimeout):
            # The first call waits 60s for the next window. The allowance
            # of 1 is spent again immediately, so the second call needs
            # another 60s, and only 30s of the budget is left.
            for _ in range(3):
                limiter.acquire()

        assert clock.sleeps == [60.0]

    def test_what_is_left_of_the_budget_is_visible(self):
        clock = FakeClock()
        limiter = saturated_limiter(clock)

        with wait_budget(90.0):
            limiter.acquire()

            assert wait_budget_seconds() == 30.0


class TestTheBudgetIsScopedToItsBlock:
    def test_it_is_cleared_afterwards(self):
        with wait_budget(10.0):
            assert wait_budget_seconds() == 10.0

        assert wait_budget_seconds() is None

    def test_it_is_cleared_even_when_the_body_raises(self):
        with pytest.raises(ValueError), wait_budget(10.0):
            raise ValueError("boom")

        assert wait_budget_seconds() is None


class TestTheRequestPathSetsTheBudget:
    def test_the_middleware_gives_the_request_a_budget(self, settings):
        from config.middleware.provider_wait_budget import (
            ProviderWaitBudgetMiddleware,
        )

        settings.PROVIDER_WAIT_BUDGET_SECONDS = 7.5
        seen = {}

        def view(request):
            seen["budget"] = wait_budget_seconds()
            return "response"

        response = ProviderWaitBudgetMiddleware(view)(object())

        assert response == "response"
        assert seen["budget"] == 7.5
        assert wait_budget_seconds() is None

    def test_the_middleware_is_installed(self, settings):
        assert (
            "config.middleware.provider_wait_budget.ProviderWaitBudgetMiddleware"
            in settings.MIDDLEWARE
        )


class TestPacingIsNotAProviderFailure:
    """The breaker exists to notice FMP failing. A call this process chose
    not to make says nothing about FMP's health, and counting it would let
    a busy minute open the breaker for everybody."""

    def test_the_breaker_does_not_count_a_pacing_timeout(self):
        breaker = CircuitBreaker(
            name="test-breaker", failure_threshold=2, cool_down_seconds=60
        )

        def refuse():
            raise RateLimitTimeout("no budget left")

        for _ in range(5):
            with pytest.raises(RateLimitTimeout):
                breaker.call(refuse, not_a_provider_failure=(RateLimitTimeout,))

        assert not breaker.is_open()

    def test_the_breaker_still_counts_a_real_failure(self):
        breaker = CircuitBreaker(
            name="test-breaker", failure_threshold=2, cool_down_seconds=60
        )

        def fail():
            raise requests.RequestException("FMP is down")

        for _ in range(2):
            with pytest.raises(requests.RequestException):
                breaker.call(fail, not_a_provider_failure=(RateLimitTimeout,))

        assert breaker.is_open()


class TestTheFMPClientDegradesGracefully:
    def test_a_pacing_timeout_becomes_an_ordinary_provider_error(self):
        from quotes.fmp import FMPError, _get

        with patch(
            "quotes.fmp._RATE_LIMITER.acquire",
            side_effect=RateLimitTimeout("no budget left"),
        ), pytest.raises(FMPError, match="pacing"):
            _get("/stable/quote", params={"symbol": "AAPL"})
