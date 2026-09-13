"""Tests for the stored daily close series.

Every company page used to refetch twenty-five years of daily prices from
FMP, 1.09 MB a time, because the only copy lived in a one-hour cache. The
series is now kept in Postgres and topped up with the handful of days that
are actually missing, which is about a kilobyte.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache

from quotes.fmp import FMPError
from quotes.models import DailyClosePrice
from quotes.price_store import HISTORY_START_DATE, get_daily_closes

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def fmp_row(day: date, price: float) -> dict:
    """One row shaped like FMP's `historical-price-eod/light` response."""
    return {"symbol": "AAPL", "date": day.isoformat(), "price": price}


def store_closes(ticker: str, closes: dict[date, float]) -> None:
    DailyClosePrice.objects.bulk_create(
        DailyClosePrice(ticker=ticker, date=day, close=Decimal(str(price)))
        for day, price in closes.items()
    )


class TestFirstFetch:
    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_fetches_the_whole_history_when_nothing_is_stored(self, mock_fetch):
        mock_fetch.return_value = [
            fmp_row(date(2020, 1, 3), 101.0),
            fmp_row(date(2020, 1, 2), 100.0),
        ]

        series = get_daily_closes("AAPL")

        mock_fetch.assert_called_once_with("AAPL", start_date=HISTORY_START_DATE)
        assert len(series) == 2
        assert DailyClosePrice.objects.count() == 2

    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_returns_the_shape_the_charts_read(self, mock_fetch):
        mock_fetch.return_value = [fmp_row(date(2020, 1, 2), 100.5)]

        series = get_daily_closes("AAPL")

        assert series == [
            {"date": 1577923200, "adjustedClose": 100.5},
        ]

    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_raises_when_the_provider_has_no_history_either(self, mock_fetch):
        mock_fetch.return_value = []

        with pytest.raises(FMPError, match="No historical price data"):
            get_daily_closes("NOPE")


class TestIncrementalTopUp:
    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_asks_only_for_the_days_it_is_missing(self, mock_fetch):
        last_stored = date.today() - timedelta(days=30)
        store_closes("AAPL", {last_stored: 100.0})
        mock_fetch.return_value = [fmp_row(last_stored, 100.0)]

        get_daily_closes("AAPL")

        _, keyword_arguments = mock_fetch.call_args
        assert keyword_arguments["start_date"] < last_stored
        assert keyword_arguments["start_date"] > HISTORY_START_DATE

    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_keeps_the_stored_history_and_adds_the_new_days(self, mock_fetch):
        old_day = date(2015, 6, 1)
        last_stored = date.today() - timedelta(days=3)
        new_day = date.today() - timedelta(days=1)
        store_closes("AAPL", {old_day: 50.0, last_stored: 100.0})
        mock_fetch.return_value = [
            fmp_row(new_day, 110.0),
            fmp_row(last_stored, 100.0),
        ]

        series = get_daily_closes("AAPL")

        assert len(series) == 3
        assert DailyClosePrice.objects.count() == 3
        assert series[0]["adjustedClose"] == 50.0
        assert series[-1]["adjustedClose"] == 110.0

    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_a_second_read_inside_the_window_does_not_call_the_provider(
        self, mock_fetch
    ):
        mock_fetch.return_value = [fmp_row(date.today() - timedelta(days=1), 100.0)]

        get_daily_closes("AAPL")
        get_daily_closes("AAPL")

        mock_fetch.assert_called_once()

    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_a_provider_failure_still_serves_what_is_stored(self, mock_fetch):
        store_closes("AAPL", {date(2020, 1, 2): 100.0})
        mock_fetch.side_effect = FMPError("FMP returned 429")

        series = get_daily_closes("AAPL")

        assert series == [{"date": 1577923200, "adjustedClose": 100.0}]


class TestSplitReadjustment:
    """FMP's series is split-adjusted, so a split rewrites every past close.

    The overlap the top-up refetches is what catches that: when the days we
    already hold come back at a different price, the stored series belongs
    to the pre-split scale and has to be replaced wholesale.
    """

    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_refetches_everything_when_the_overlap_disagrees(self, mock_fetch):
        last_stored = date.today() - timedelta(days=2)
        store_closes("AAPL", {date(2015, 6, 1): 400.0, last_stored: 400.0})
        mock_fetch.side_effect = [
            [fmp_row(last_stored, 100.0)],  # a 4-for-1 split, overlap disagrees
            [fmp_row(date(2015, 6, 1), 100.0), fmp_row(last_stored, 100.0)],
        ]

        series = get_daily_closes("AAPL")

        assert mock_fetch.call_count == 2
        assert mock_fetch.call_args_list[1].kwargs["start_date"] == HISTORY_START_DATE
        assert [point["adjustedClose"] for point in series] == [100.0, 100.0]
        assert DailyClosePrice.objects.count() == 2

    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_a_rounding_difference_is_not_a_split(self, mock_fetch):
        last_stored = date.today() - timedelta(days=2)
        store_closes("AAPL", {last_stored: 100.0})
        mock_fetch.return_value = [fmp_row(last_stored, 100.0001)]

        get_daily_closes("AAPL")

        assert mock_fetch.call_count == 1


class TestPruning:
    @patch("quotes.price_store.fmp.fetch_historical_prices")
    def test_each_ticker_keeps_its_own_series(self, mock_fetch):
        mock_fetch.return_value = [fmp_row(date(2020, 1, 2), 100.0)]
        get_daily_closes("AAPL")
        mock_fetch.return_value = [fmp_row(date(2020, 1, 2), 50.0)]
        get_daily_closes("MSFT")

        assert DailyClosePrice.objects.filter(ticker="AAPL").count() == 1
        assert DailyClosePrice.objects.filter(ticker="MSFT").count() == 1
