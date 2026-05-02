"""Tests for the FRED client and per-country CPI sync."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from quotes.fred import (
    CURRENCY_TO_SERIES_ID,
    FREDError,
    fetch_cpi_observations,
    sync_country_cpi,
)
from quotes.models import CountryCPIIndex


# FRED returns a JSON object with `observations`. Values are strings
# (FRED's convention) and a missing reading is "."
MOCK_DKK_OBSERVATIONS = {
    "observations": [
        {"date": "2024-01-01", "value": "100.0"},
        {"date": "2024-12-01", "value": "102.0"},
        {"date": "2025-01-01", "value": "103.0"},
        {"date": "2025-12-01", "value": "105.06"},
    ],
}


class TestCurrencyToSeriesIdMapping:
    def test_covers_at_least_the_majors(self):
        for ccy in ("DKK", "JPY", "EUR", "GBP", "CNY", "TWD", "CHF", "CAD"):
            assert ccy in CURRENCY_TO_SERIES_ID, f"missing FRED series for {ccy}"
            assert isinstance(CURRENCY_TO_SERIES_ID[ccy], str)
            assert len(CURRENCY_TO_SERIES_ID[ccy]) > 0


class TestFetchCpiObservations:
    @patch("quotes.fred._get")
    def test_passes_series_id_and_returns_observations(self, mock_get):
        mock_get.return_value = MOCK_DKK_OBSERVATIONS
        result = fetch_cpi_observations("DKK")
        assert mock_get.call_args.kwargs["params"]["series_id"] == CURRENCY_TO_SERIES_ID["DKK"]
        assert mock_get.call_args.kwargs["params"]["file_type"] == "json"
        assert result == MOCK_DKK_OBSERVATIONS["observations"]

    @patch("quotes.fred._get")
    def test_returns_empty_when_no_observations(self, mock_get):
        mock_get.return_value = {"observations": []}
        assert fetch_cpi_observations("DKK") == []

    def test_raises_for_unmapped_currency(self):
        with pytest.raises(FREDError, match="No FRED series id"):
            fetch_cpi_observations("ZZZ")


class TestSyncCountryCpi:
    @patch("quotes.fred.fetch_cpi_observations")
    def test_writes_yoy_rates_per_month(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_DKK_OBSERVATIONS["observations"]
        sync_country_cpi(["DKK"])
        # Jan-2025 vs Jan-2024: (103/100 - 1) * 100 = 3.00%
        # Dec-2025 vs Dec-2024: (105.06/102 - 1) * 100 ≈ 3.00%
        rows = list(CountryCPIIndex.objects.filter(currency="DKK").order_by("date"))
        assert len(rows) == 2
        assert rows[0].date == date(2025, 1, 1)
        assert rows[0].annual_rate == Decimal("3.0000")
        assert rows[1].date == date(2025, 12, 1)
        assert rows[1].annual_rate == Decimal("3.0000")

    @patch("quotes.fred.fetch_cpi_observations")
    def test_skips_dot_value(self, mock_fetch, db):
        """FRED uses '.' to mark a missing observation."""
        mock_fetch.return_value = [
            {"date": "2024-12-01", "value": "100.0"},
            {"date": "2025-12-01", "value": "."},
        ]
        sync_country_cpi(["DKK"])
        assert CountryCPIIndex.objects.filter(currency="DKK").count() == 0

    @patch("quotes.fred.fetch_cpi_observations")
    def test_is_idempotent(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_DKK_OBSERVATIONS["observations"]
        sync_country_cpi(["DKK"])
        sync_country_cpi(["DKK"])
        assert CountryCPIIndex.objects.filter(currency="DKK").count() == 2

    @patch("quotes.fred.fetch_cpi_observations")
    def test_runs_for_each_requested_currency(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_DKK_OBSERVATIONS["observations"]
        sync_country_cpi(["DKK", "EUR"])
        assert CountryCPIIndex.objects.filter(currency="DKK").exists()
        assert CountryCPIIndex.objects.filter(currency="EUR").exists()
