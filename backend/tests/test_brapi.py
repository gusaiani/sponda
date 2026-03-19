"""Tests for BRAPI client with mocked API responses."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from quotes.brapi import (
    BRAPIError,
    fetch_historical_prices,
    fetch_income_statements,
    fetch_quote,
    sync_ipca,
    sync_earnings,
)
from quotes.models import IPCAIndex, QuarterlyEarnings


MOCK_QUOTE_RESPONSE = {
    "results": [
        {
            "symbol": "PETR4",
            "shortName": "PETR4",
            "longName": "Petroleo Brasileiro SA Pfd",
            "regularMarketPrice": 45.0,
            "marketCap": 602167750093,
            "earningsPerShare": 8.54,
        }
    ]
}

MOCK_INCOME_RESPONSE = {
    "results": [
        {
            "incomeStatementHistoryQuarterly": [
                {
                    "endDate": "2025-12-31",
                    "netIncome": 15653000000,
                    "basicEarningsPerCommonShare": None,
                },
                {
                    "endDate": "2025-09-30",
                    "netIncome": 32847000000,
                    "basicEarningsPerCommonShare": 2540,
                },
                {
                    "endDate": "2025-06-30",
                    "netIncome": 26774000000,
                    "basicEarningsPerCommonShare": 2070,
                },
                {
                    "endDate": "2025-03-31",
                    "netIncome": 35331000000,
                    "basicEarningsPerCommonShare": 2730,
                },
            ]
        }
    ]
}

MOCK_IPCA_RESPONSE = {
    "inflation": [
        {"date": "01/12/2025", "value": "4.26", "epochDate": 1764547200000},
        {"date": "01/11/2025", "value": "4.46", "epochDate": 1761955200000},
        {"date": "01/12/2024", "value": "4.83", "epochDate": 1733011200000},
    ]
}


class TestFetchQuote:
    @patch("quotes.brapi._get")
    def test_returns_first_result(self, mock_get):
        mock_get.return_value = MOCK_QUOTE_RESPONSE
        result = fetch_quote("PETR4")
        assert result["symbol"] == "PETR4"
        assert result["regularMarketPrice"] == 45.0

    @patch("quotes.brapi._get")
    def test_raises_on_empty_results(self, mock_get):
        mock_get.return_value = {"results": []}
        with pytest.raises(BRAPIError, match="No results"):
            fetch_quote("FAKE3")


MOCK_HISTORICAL_RESPONSE = {
    "results": [
        {
            "historicalDataPrice": [
                {"date": 1704067200, "adjustedClose": 30.0},
                {"date": 1706745600, "adjustedClose": 32.0},
            ]
        }
    ]
}


class TestFetchHistoricalPrices:
    @patch("quotes.brapi._get")
    def test_returns_historical_data(self, mock_get):
        mock_get.return_value = MOCK_HISTORICAL_RESPONSE
        result = fetch_historical_prices("PETR4")
        assert len(result) == 2
        assert result[0]["adjustedClose"] == 30.0
        mock_get.assert_called_once_with(
            "/quote/PETR4", params={"range": "max", "interval": "1mo"}
        )

    @patch("quotes.brapi._get")
    def test_raises_on_empty_results(self, mock_get):
        mock_get.return_value = {"results": []}
        with pytest.raises(BRAPIError, match="No results"):
            fetch_historical_prices("FAKE3")

    @patch("quotes.brapi._get")
    def test_returns_empty_list_when_no_historical_data(self, mock_get):
        mock_get.return_value = {"results": [{"historicalDataPrice": []}]}
        result = fetch_historical_prices("PETR4")
        assert result == []


class TestFetchIncomeStatements:
    @patch("quotes.brapi._get")
    def test_returns_quarterly_statements(self, mock_get):
        mock_get.return_value = MOCK_INCOME_RESPONSE
        result = fetch_income_statements("PETR4")
        assert len(result) == 4
        assert result[0]["endDate"] == "2025-12-31"
        assert result[0]["netIncome"] == 15653000000

    @patch("quotes.brapi._get")
    def test_returns_empty_list_when_no_statements(self, mock_get):
        mock_get.return_value = {"results": [{"incomeStatementHistoryQuarterly": []}]}
        result = fetch_income_statements("PETR4")
        assert result == []


class TestSyncQuarterlyEarnings:
    @patch("quotes.brapi.fetch_income_statements")
    def test_creates_earnings_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_RESPONSE["results"][0][
            "incomeStatementHistoryQuarterly"
        ]
        earnings = sync_earnings("PETR4")
        assert len(earnings) == 4
        assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == 4

    @patch("quotes.brapi.fetch_income_statements")
    def test_stores_net_income(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_RESPONSE["results"][0][
            "incomeStatementHistoryQuarterly"
        ]
        sync_earnings("PETR4")
        q4 = QuarterlyEarnings.objects.get(ticker="PETR4", end_date=date(2025, 12, 31))
        assert q4.net_income == 15653000000

    @patch("quotes.brapi.fetch_income_statements")
    def test_handles_null_eps(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_RESPONSE["results"][0][
            "incomeStatementHistoryQuarterly"
        ]
        sync_earnings("PETR4")
        q4 = QuarterlyEarnings.objects.get(ticker="PETR4", end_date=date(2025, 12, 31))
        assert q4.eps is None

    @patch("quotes.brapi.fetch_income_statements")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_RESPONSE["results"][0][
            "incomeStatementHistoryQuarterly"
        ]
        sync_earnings("PETR4")
        sync_earnings("PETR4")
        # Should not create duplicates
        assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == 4

    @patch("quotes.brapi.fetch_income_statements")
    def test_skips_entries_without_end_date(self, mock_fetch, db):
        mock_fetch.return_value = [{"endDate": "", "netIncome": 1000}]
        earnings = sync_earnings("PETR4")
        assert len(earnings) == 0


class TestSyncIPCA:
    @patch("quotes.brapi.fetch_ipca_data")
    def test_creates_ipca_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_IPCA_RESPONSE["inflation"]
        count = sync_ipca()
        assert count == 3
        assert IPCAIndex.objects.count() == 3

    @patch("quotes.brapi.fetch_ipca_data")
    def test_parses_brapi_date_format(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_IPCA_RESPONSE["inflation"]
        sync_ipca()
        entry = IPCAIndex.objects.get(date=date(2025, 12, 1))
        assert entry.annual_rate == Decimal("4.26")

    @patch("quotes.brapi.fetch_ipca_data")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_IPCA_RESPONSE["inflation"]
        sync_ipca()
        sync_ipca()
        assert IPCAIndex.objects.count() == 3

    @patch("quotes.brapi.fetch_ipca_data")
    def test_skips_entries_without_value(self, mock_fetch, db):
        mock_fetch.return_value = [{"date": "01/01/2025", "value": None}]
        count = sync_ipca()
        assert count == 0
