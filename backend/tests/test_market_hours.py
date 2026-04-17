"""Tests for exchange market-hours helpers."""
from datetime import datetime, timezone

from quotes.market_hours import any_exchange_open, is_b3_open, is_nyse_open

UTC = timezone.utc


def make_utc(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


class TestIsB3Open:
    def test_open_mid_session_weekday(self):
        # Monday 15:00 UTC = 12:00 BRT (within 10:00-17:30)
        assert is_b3_open(make_utc(2024, 4, 15, 15, 0)) is True

    def test_closed_before_open(self):
        # 12:59 UTC = 09:59 BRT (before 10:00)
        assert is_b3_open(make_utc(2024, 4, 15, 12, 59)) is False

    def test_open_exactly_at_open_time(self):
        # 13:00 UTC = 10:00 BRT (exactly at open)
        assert is_b3_open(make_utc(2024, 4, 15, 13, 0)) is True

    def test_closed_exactly_at_close_time(self):
        # 20:30 UTC = 17:30 BRT (exactly at close — market closed)
        assert is_b3_open(make_utc(2024, 4, 15, 20, 30)) is False

    def test_open_one_minute_before_close(self):
        # 20:29 UTC = 17:29 BRT
        assert is_b3_open(make_utc(2024, 4, 15, 20, 29)) is True

    def test_closed_after_close(self):
        # 21:00 UTC = 18:00 BRT (after 17:30)
        assert is_b3_open(make_utc(2024, 4, 15, 21, 0)) is False

    def test_closed_on_saturday(self):
        assert is_b3_open(make_utc(2024, 4, 13, 15, 0)) is False

    def test_closed_on_sunday(self):
        assert is_b3_open(make_utc(2024, 4, 14, 15, 0)) is False


class TestIsNYSEOpen:
    # Summer (EDT, UTC-4): NYSE opens 13:30 UTC, closes 20:00 UTC
    # Winter (EST, UTC-5): NYSE opens 14:30 UTC, closes 21:00 UTC

    def test_open_mid_session_summer(self):
        # April (EDT, UTC-4): 16:00 UTC = 12:00 ET
        assert is_nyse_open(make_utc(2024, 4, 15, 16, 0)) is True

    def test_open_exactly_at_summer_open(self):
        # April (EDT): 13:30 UTC = 09:30 ET
        assert is_nyse_open(make_utc(2024, 4, 15, 13, 30)) is True

    def test_closed_before_summer_open(self):
        # April (EDT): 13:29 UTC = 09:29 ET
        assert is_nyse_open(make_utc(2024, 4, 15, 13, 29)) is False

    def test_closed_exactly_at_summer_close(self):
        # April (EDT): 20:00 UTC = 16:00 ET (closed)
        assert is_nyse_open(make_utc(2024, 4, 15, 20, 0)) is False

    def test_open_one_minute_before_summer_close(self):
        # April (EDT): 19:59 UTC = 15:59 ET
        assert is_nyse_open(make_utc(2024, 4, 15, 19, 59)) is True

    def test_open_mid_session_winter(self):
        # January (EST, UTC-5): 17:00 UTC = 12:00 ET
        assert is_nyse_open(make_utc(2024, 1, 15, 17, 0)) is True

    def test_open_exactly_at_winter_open(self):
        # January (EST): 14:30 UTC = 09:30 ET
        assert is_nyse_open(make_utc(2024, 1, 15, 14, 30)) is True

    def test_closed_before_winter_open(self):
        # January (EST): 14:29 UTC = 09:29 ET
        assert is_nyse_open(make_utc(2024, 1, 15, 14, 29)) is False

    def test_closed_exactly_at_winter_close(self):
        # January (EST): 21:00 UTC = 16:00 ET (closed)
        assert is_nyse_open(make_utc(2024, 1, 15, 21, 0)) is False

    def test_closed_on_saturday(self):
        assert is_nyse_open(make_utc(2024, 4, 13, 16, 0)) is False

    def test_closed_on_sunday(self):
        assert is_nyse_open(make_utc(2024, 4, 14, 16, 0)) is False


class TestAnyExchangeOpen:
    def test_true_when_both_open(self):
        # April weekday 16:00 UTC: B3 open (BRT 13:00), NYSE open (ET 12:00 EDT)
        assert any_exchange_open(make_utc(2024, 4, 15, 16, 0)) is True

    def test_true_when_only_b3_open(self):
        # 13:10 UTC (April, EDT): B3 open (BRT 10:10), NYSE not yet (ET 09:10, opens 09:30)
        assert any_exchange_open(make_utc(2024, 4, 15, 13, 10)) is True

    def test_true_when_only_nyse_open(self):
        # January 15 is a Monday.
        # 20:45 UTC (EST): B3 closed (BRT 17:45, after close 17:30), NYSE open (ET 15:45)
        assert any_exchange_open(make_utc(2024, 1, 15, 20, 45)) is True

    def test_false_on_weekend(self):
        assert any_exchange_open(make_utc(2024, 4, 13, 16, 0)) is False

    def test_false_before_any_open(self):
        # 12:00 UTC: B3 opens 13:00, NYSE opens 13:30 (EDT)
        assert any_exchange_open(make_utc(2024, 4, 15, 12, 0)) is False

    def test_false_after_all_closed(self):
        # 21:30 UTC (April, EDT): B3 closed 20:30, NYSE closed 20:00
        assert any_exchange_open(make_utc(2024, 4, 15, 21, 30)) is False
