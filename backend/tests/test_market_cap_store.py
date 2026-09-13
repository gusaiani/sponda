"""Tests for the stored daily market cap series.

The multiples chart values each past year at the market cap FMP observed
on the day that year closed. That series was refetched per company per
day, 0.44 MB a time, roughly 2.5 GB a month. It is stored now and topped
up with the days it is missing, exactly like the closing prices.

Unlike prices, this series is not adjusted after the fact. A split leaves
a company's market cap unchanged, so a day that comes back with a
different number is a provider revision to take, not evidence that the
whole history is on the wrong scale.
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache

from quotes.fmp import FMPError
from quotes.market_cap_store import get_daily_market_caps
from quotes.models import DailyMarketCap
from quotes.series_store import HISTORY_START_DATE

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def fmp_row(day: date, market_cap: int) -> dict:
    """One row shaped like FMP's `historical-market-capitalization` response."""
    return {"symbol": "AAPL", "date": day.isoformat(), "marketCap": market_cap}


def store_market_caps(ticker: str, caps: dict[date, int]) -> None:
    DailyMarketCap.objects.bulk_create(
        DailyMarketCap(ticker=ticker, date=day, market_cap=cap)
        for day, cap in caps.items()
    )


class TestFirstFetch:
    @patch("quotes.market_cap_store.fmp.fetch_historical_market_caps")
    def test_fetches_the_whole_history_when_nothing_is_stored(self, mock_fetch):
        mock_fetch.return_value = [
            fmp_row(date(2020, 1, 3), 1_300_000_000_000),
            fmp_row(date(2020, 1, 2), 1_290_000_000_000),
        ]

        series = get_daily_market_caps("AAPL")

        mock_fetch.assert_called_once_with("AAPL", start_date=HISTORY_START_DATE)
        assert len(series) == 2
        assert DailyMarketCap.objects.count() == 2

    @patch("quotes.market_cap_store.fmp.fetch_historical_market_caps")
    def test_returns_the_shape_the_chart_reads(self, mock_fetch):
        mock_fetch.return_value = [fmp_row(date(2020, 1, 2), 1_290_000_000_000)]

        series = get_daily_market_caps("AAPL")

        assert series == [{"date": 1577923200, "marketCap": 1_290_000_000_000.0}]

    @patch("quotes.market_cap_store.fmp.fetch_historical_market_caps")
    def test_raises_when_the_provider_does_not_cover_the_symbol(self, mock_fetch):
        """An empty answer with nothing stored is how FMP says it has no
        coverage. Raising keeps the ProviderError mapping the multiples view
        already treats as "chart without this enrichment"."""
        mock_fetch.return_value = []

        with pytest.raises(FMPError, match="No historical market cap"):
            get_daily_market_caps("NOPE")


class TestIncrementalTopUp:
    @patch("quotes.market_cap_store.fmp.fetch_historical_market_caps")
    def test_asks_only_for_the_days_it_is_missing(self, mock_fetch):
        last_stored = date.today() - timedelta(days=30)
        store_market_caps("AAPL", {last_stored: 1_000_000})
        mock_fetch.return_value = [fmp_row(last_stored, 1_000_000)]

        get_daily_market_caps("AAPL")

        start_date = mock_fetch.call_args.kwargs["start_date"]
        assert start_date < last_stored
        assert start_date > HISTORY_START_DATE

    @patch("quotes.market_cap_store.fmp.fetch_historical_market_caps")
    def test_keeps_the_stored_history_and_adds_the_new_days(self, mock_fetch):
        old_day = date(2015, 6, 1)
        last_stored = date.today() - timedelta(days=3)
        new_day = date.today() - timedelta(days=1)
        store_market_caps("AAPL", {old_day: 500_000, last_stored: 1_000_000})
        mock_fetch.return_value = [
            fmp_row(new_day, 1_100_000),
            fmp_row(last_stored, 1_000_000),
        ]

        series = get_daily_market_caps("AAPL")

        assert len(series) == 3
        assert series[0]["marketCap"] == 500_000
        assert series[-1]["marketCap"] == 1_100_000

    @patch("quotes.market_cap_store.fmp.fetch_historical_market_caps")
    def test_a_second_read_inside_the_window_does_not_call_the_provider(
        self, mock_fetch
    ):
        mock_fetch.return_value = [fmp_row(date.today() - timedelta(days=1), 1_000_000)]

        get_daily_market_caps("AAPL")
        get_daily_market_caps("AAPL")

        mock_fetch.assert_called_once()

    @patch("quotes.market_cap_store.fmp.fetch_historical_market_caps")
    def test_a_provider_failure_still_serves_what_is_stored(self, mock_fetch):
        store_market_caps("AAPL", {date(2020, 1, 2): 1_290_000_000_000})
        mock_fetch.side_effect = FMPError("FMP returned 429")

        series = get_daily_market_caps("AAPL")

        assert series == [{"date": 1577923200, "marketCap": 1_290_000_000_000.0}]

    @patch("quotes.market_cap_store.fmp.fetch_historical_market_caps")
    def test_a_revised_day_is_taken_without_refetching_the_history(self, mock_fetch):
        """A market cap is not adjusted backwards the way a split-adjusted
        price is, so a changed overlap day is a revision to store, not a
        signal that the stored history is on the wrong scale."""
        last_stored = date.today() - timedelta(days=2)
        store_market_caps("AAPL", {date(2015, 6, 1): 500_000, last_stored: 1_000_000})
        mock_fetch.return_value = [fmp_row(last_stored, 1_050_000)]

        series = get_daily_market_caps("AAPL")

        assert mock_fetch.call_count == 1
        assert [point["marketCap"] for point in series] == [500_000, 1_050_000]
