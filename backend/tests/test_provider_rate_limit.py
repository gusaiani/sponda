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

from quotes.rate_limiter import CALLS_RESERVED_PER_ROUND_TRIP, RateLimiter


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

        assert cache.get(limiter.window_cache_key(0)) == CALLS_RESERVED_PER_ROUND_TRIP

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

        assert cache.get(first.window_cache_key(0)) == 2 * CALLS_RESERVED_PER_ROUND_TRIP

    def test_a_cache_that_is_down_still_allows_the_call(self):
        clock = FakeClock()
        limiter = RateLimiter(
            "test-provider", max_calls_per_minute=1, sleep=clock.sleep, clock=clock.time
        )

        with patch("quotes.rate_limiter.cache.incr", side_effect=ConnectionError("redis is down")), \
             patch("quotes.rate_limiter.cache.add", side_effect=ConnectionError("redis is down")):
            limiter.acquire()

        assert clock.sleeps == []


class FakeRedisClient:
    """Enough of redis-py to see which commands the limiter actually sends."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expiries: dict[str, int] = {}
        self.commands: list[tuple[str, str]] = []

    def incr(self, key, amount=1):
        self.commands.append(("incr", key, amount))
        self.values[key] = self.values.get(key, 0) + amount
        return self.values[key]

    def expire(self, key, seconds):
        self.commands.append(("expire", key))
        self.expiries[key] = seconds
        return True


class FakeRedisCache:
    """A cache shaped like Django's RedisCache, over a FakeRedisClient."""

    def __init__(self, client: FakeRedisClient) -> None:
        self.client = client

        class Backend:
            def get_client(_self, key=None, write=False):
                return client

        self._cache = Backend()

    def make_key(self, key, version=None):
        return f":1:{key}"


class TestTheCounterIsOneRoundTripOnRedis:
    """Django's `cache.incr` is `EXISTS` then `INCRBY`, and `cache.add` is a
    `SET NX`. Going through the cache API therefore costs two round trips
    per call at best, and Sentry filed the surviving `EXISTS` as its own
    N+1 on /api/quote/{ticker}/ once the `SET` was gone.

    Redis `INCR` creates a missing key at zero and returns 1, so the
    existence check buys nothing. The limiter uses it directly and sets
    the expiry only for whoever opened the window."""

    def test_an_ordinary_call_sends_one_command(self):
        client = FakeRedisClient()
        limiter = RateLimiter("test-provider", max_calls_per_minute=100)

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            limiter._increment("rate_limiter:test-provider:0", 1)  # opens the window
            client.commands.clear()

            for _ in range(10):
                limiter._increment("rate_limiter:test-provider:0", 1)

        assert client.commands == [("incr", ":1:rate_limiter:test-provider:0", 1)] * 10

    def test_the_call_that_opens_the_window_also_sets_the_expiry(self):
        client = FakeRedisClient()
        limiter = RateLimiter("test-provider", max_calls_per_minute=100)

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            count = limiter._increment("rate_limiter:test-provider:0", 1)

        assert count == 1
        assert client.commands == [
            ("incr", ":1:rate_limiter:test-provider:0", 1),
            ("expire", ":1:rate_limiter:test-provider:0"),
        ]

    def test_the_expiry_outlives_the_window(self):
        client = FakeRedisClient()
        limiter = RateLimiter("test-provider", max_calls_per_minute=100)

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            limiter._increment("rate_limiter:test-provider:0", 1)

        assert client.expiries[":1:rate_limiter:test-provider:0"] > 60

    def test_it_never_checks_existence(self):
        """The whole point: no EXISTS span for Sentry to report."""
        client = FakeRedisClient()
        limiter = RateLimiter("test-provider", max_calls_per_minute=100)

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            counts = [
                limiter._increment("rate_limiter:test-provider:0", 1)
                for _ in range(5)
            ]

        assert counts == [1, 2, 3, 4, 5]
        assert not any(command[0] == "exists" for command in client.commands)

    def test_a_redis_that_is_down_still_allows_the_call(self):
        client = FakeRedisClient()
        clock = FakeClock()
        limiter = RateLimiter(
            "test-provider", max_calls_per_minute=1, sleep=clock.sleep, clock=clock.time
        )

        def refuse(*_args, **_kwargs):
            raise ConnectionError("redis is down")

        client.incr = refuse

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            limiter.acquire()
            limiter.acquire()

        assert clock.sleeps == []


class TestTheCacheApiIsStillUsedWithoutRedis:
    """LocMemCache in tests and development has no client to reach for."""

    def test_a_cache_with_no_redis_client_still_counts(self):
        limiter = RateLimiter("test-provider", max_calls_per_minute=100)

        first = limiter._increment("rate_limiter:test-provider:0", 1)
        second = limiter._increment("rate_limiter:test-provider:0", 3)

        assert (first, second) == (1, 4)


class TestOneRoundTripCoversAPageOfCalls:
    """Sentry filed the surviving `INCRBY ':1:rate_limiter:fmp:<window>'` as
    an N+1 on /api/quote/{ticker}/ under `ensure_fresh_data`, the same
    heading as every earlier shape of this counter. Counting one call in
    one command was still one command per call, and a cold company page
    makes four of them.

    So a process reserves a page's worth of calls in one `INCRBY` and
    hands them out locally until they run out or the window rolls over.
    The reservation is what the fleet-wide counter sees; whether the
    calls are then made is this process's business. Slots reserved and
    never used are the price, and it is bounded by one reservation per
    process per window."""

    WINDOW_KEY = ":1:rate_limiter:test-provider:0"

    def paced_limiter(self, clock: FakeClock, allowance: int = 100) -> RateLimiter:
        return RateLimiter(
            "test-provider",
            max_calls_per_minute=allowance,
            sleep=clock.sleep,
            clock=clock.time,
        )

    def test_a_reservation_is_the_size_of_a_cold_company_page(self):
        """Three statement syncs plus the quote itself."""
        assert CALLS_RESERVED_PER_ROUND_TRIP == 4

    def test_a_pages_worth_of_calls_costs_one_round_trip(self):
        client = FakeRedisClient()
        limiter = self.paced_limiter(FakeClock())

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            for _ in range(CALLS_RESERVED_PER_ROUND_TRIP):
                limiter.acquire()

        assert client.commands == [
            ("incr", self.WINDOW_KEY, CALLS_RESERVED_PER_ROUND_TRIP),
            ("expire", self.WINDOW_KEY),
        ]

    def test_the_call_after_the_reservation_takes_another(self):
        client = FakeRedisClient()
        limiter = self.paced_limiter(FakeClock())

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            for _ in range(CALLS_RESERVED_PER_ROUND_TRIP + 1):
                limiter.acquire()

        increments = [command for command in client.commands if command[0] == "incr"]
        assert increments == [("incr", self.WINDOW_KEY, CALLS_RESERVED_PER_ROUND_TRIP)] * 2

    def test_a_reservation_does_not_outlive_its_window(self):
        client = FakeRedisClient()
        clock = FakeClock()
        limiter = self.paced_limiter(clock)

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            limiter.acquire()  # reserves the rest of this window's page
            clock.now = 61.0
            limiter.acquire()

        increments = [command for command in client.commands if command[0] == "incr"]
        assert increments == [
            ("incr", ":1:rate_limiter:test-provider:0", CALLS_RESERVED_PER_ROUND_TRIP),
            ("incr", ":1:rate_limiter:test-provider:60", CALLS_RESERVED_PER_ROUND_TRIP),
        ]

    def test_reserved_slots_past_the_allowance_are_not_handed_out(self):
        """An allowance of 5 with reservations of 4: the second reservation
        straddles the ceiling, so only one of its four slots is real."""
        clock = FakeClock()
        limiter = self.paced_limiter(clock, allowance=5)

        for _ in range(5):
            limiter.acquire()
        assert clock.sleeps == []

        limiter.acquire()

        assert clock.sleeps == [60.0]

    def test_another_process_cannot_use_what_this_one_reserved(self):
        clock = FakeClock()
        first = self.paced_limiter(clock, allowance=CALLS_RESERVED_PER_ROUND_TRIP)
        second = self.paced_limiter(clock, allowance=CALLS_RESERVED_PER_ROUND_TRIP)

        first.acquire()  # holds the whole allowance for this window
        second.acquire()

        assert clock.sleeps == [60.0]

    def test_a_reservation_the_counter_refused_still_lets_one_call_through(self):
        """When Redis is down the limiter allows the call rather than block
        the provider. It must not also hand out a phantom reservation that
        keeps allowing calls once Redis is back."""
        client = FakeRedisClient()
        limiter = self.paced_limiter(FakeClock(), allowance=1)

        def refuse(*_args, **_kwargs):
            raise ConnectionError("redis is down")

        with patch("quotes.rate_limiter.cache", FakeRedisCache(client)):
            client.incr = refuse
            limiter.acquire()
            del client.incr  # Redis is back
            limiter.acquire()

        assert [command for command in client.commands if command[0] == "incr"] == [
            ("incr", self.WINDOW_KEY, CALLS_RESERVED_PER_ROUND_TRIP)
        ]
