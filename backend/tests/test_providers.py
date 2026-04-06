"""Tests for the provider routing layer."""
import re
from unittest.mock import patch, MagicMock

import pytest

from quotes.providers import (
    ProviderError,
    is_brazilian_ticker,
    fetch_quote,
    fetch_dividends,
    fetch_historical_prices,
    sync_earnings,
    sync_cash_flows,
    sync_balance_sheets,
)


class TestIsBrazilianTicker:
    """Brazilian tickers end with a digit: PETR4, VALE3, BBDC4, ITUB3."""

    def test_standard_brazilian_tickers(self):
        assert is_brazilian_ticker("PETR4") is True
        assert is_brazilian_ticker("VALE3") is True
        assert is_brazilian_ticker("BBDC4") is True
        assert is_brazilian_ticker("ITUB3") is True
        assert is_brazilian_ticker("WEGE3") is True

    def test_us_tickers(self):
        assert is_brazilian_ticker("AAPL") is False
        assert is_brazilian_ticker("MSFT") is False
        assert is_brazilian_ticker("GOOGL") is False
        assert is_brazilian_ticker("TSLA") is False
        assert is_brazilian_ticker("BRK.B") is False
        assert is_brazilian_ticker("META") is False

    def test_case_insensitive(self):
        assert is_brazilian_ticker("petr4") is True
        assert is_brazilian_ticker("aapl") is False

    def test_single_letter_class(self):
        """Some BR units/receipts: BRAP11, SANB11."""
        assert is_brazilian_ticker("BRAP11") is True
        assert is_brazilian_ticker("SANB11") is True


class TestFetchQuoteRouting:
    @patch("quotes.providers.brapi")
    def test_routes_brazilian_ticker_to_brapi(self, mock_brapi):
        mock_brapi.fetch_quote.return_value = {"symbol": "PETR4", "regularMarketPrice": 45.0}
        result = fetch_quote("PETR4")
        mock_brapi.fetch_quote.assert_called_once_with("PETR4")
        assert result["symbol"] == "PETR4"

    @patch("quotes.providers.fmp")
    def test_routes_us_ticker_to_fmp_and_normalizes(self, mock_fmp):
        mock_fmp.fetch_quote.return_value = {"symbol": "AAPL", "name": "Apple Inc.", "price": 178.0, "marketCap": 2800000000000}
        result = fetch_quote("AAPL")
        mock_fmp.fetch_quote.assert_called_once_with("AAPL")
        assert result["symbol"] == "AAPL"
        assert result["regularMarketPrice"] == 178.0
        assert result["longName"] == "Apple Inc."

    @patch("quotes.providers.brapi")
    def test_wraps_brapi_error_as_provider_error(self, mock_brapi):
        from quotes.brapi import BRAPIError
        mock_brapi.fetch_quote.side_effect = BRAPIError("No results")
        mock_brapi.BRAPIError = BRAPIError
        with pytest.raises(ProviderError, match="No results"):
            fetch_quote("PETR4")

    @patch("quotes.providers.fmp")
    def test_wraps_fmp_error_as_provider_error(self, mock_fmp):
        from quotes.fmp import FMPError
        mock_fmp.fetch_quote.side_effect = FMPError("No results")
        mock_fmp.FMPError = FMPError
        with pytest.raises(ProviderError, match="No results"):
            fetch_quote("AAPL")


class TestSyncRouting:
    @patch("quotes.providers.brapi")
    def test_sync_earnings_routes_to_brapi(self, mock_brapi):
        mock_brapi.sync_earnings.return_value = []
        sync_earnings("VALE3")
        mock_brapi.sync_earnings.assert_called_once_with("VALE3")

    @patch("quotes.providers.fmp")
    def test_sync_earnings_routes_to_fmp(self, mock_fmp):
        mock_fmp.sync_earnings.return_value = []
        sync_earnings("MSFT")
        mock_fmp.sync_earnings.assert_called_once_with("MSFT")

    @patch("quotes.providers.brapi")
    def test_sync_cash_flows_routes_to_brapi(self, mock_brapi):
        mock_brapi.sync_cash_flows.return_value = []
        sync_cash_flows("PETR4")
        mock_brapi.sync_cash_flows.assert_called_once_with("PETR4")

    @patch("quotes.providers.fmp")
    def test_sync_cash_flows_routes_to_fmp(self, mock_fmp):
        mock_fmp.sync_cash_flows.return_value = []
        sync_cash_flows("GOOGL")
        mock_fmp.sync_cash_flows.assert_called_once_with("GOOGL")

    @patch("quotes.providers.brapi")
    def test_sync_balance_sheets_routes_to_brapi(self, mock_brapi):
        mock_brapi.sync_balance_sheets.return_value = []
        sync_balance_sheets("BBDC4")
        mock_brapi.sync_balance_sheets.assert_called_once_with("BBDC4")

    @patch("quotes.providers.fmp")
    def test_sync_balance_sheets_routes_to_fmp(self, mock_fmp):
        mock_fmp.sync_balance_sheets.return_value = []
        sync_balance_sheets("TSLA")
        mock_fmp.sync_balance_sheets.assert_called_once_with("TSLA")


class TestFetchDividendsRouting:
    @patch("quotes.providers.brapi")
    def test_routes_brazilian_ticker_to_brapi(self, mock_brapi):
        mock_brapi.fetch_dividends.return_value = {"cashDividends": []}
        fetch_dividends("ITUB3")
        mock_brapi.fetch_dividends.assert_called_once_with("ITUB3")

    @patch("quotes.providers.fmp")
    def test_routes_us_ticker_to_fmp_and_normalizes(self, mock_fmp):
        mock_fmp.fetch_dividends.return_value = [
            {"date": "2025-02-07", "dividend": 0.25, "paymentDate": "2025-02-13"},
        ]
        result = fetch_dividends("AAPL")
        mock_fmp.fetch_dividends.assert_called_once_with("AAPL")
        assert "cashDividends" in result
        assert "stockDividends" in result
        assert len(result["cashDividends"]) == 1
        assert result["cashDividends"][0]["value"] == 0.25
        assert result["cashDividends"][0]["paymentDate"] == "2025-02-13"


class TestFetchHistoricalPricesRouting:
    @patch("quotes.providers.brapi")
    def test_routes_brazilian_ticker_to_brapi(self, mock_brapi):
        mock_brapi.fetch_historical_prices.return_value = []
        fetch_historical_prices("WEGE3")
        mock_brapi.fetch_historical_prices.assert_called_once_with("WEGE3")

    @patch("quotes.providers.fmp")
    def test_routes_us_ticker_to_fmp_and_normalizes(self, mock_fmp):
        mock_fmp.fetch_historical_prices.return_value = [
            {"date": "2025-01-02", "close": 178.5},
        ]
        result = fetch_historical_prices("META")
        mock_fmp.fetch_historical_prices.assert_called_once_with("META")
        assert len(result) == 1
        assert result[0]["adjustedClose"] == 178.5
        assert isinstance(result[0]["date"], int)  # unix timestamp


class TestProviderLayerCaching:
    """Provider functions cache results in Redis to avoid redundant external API calls."""

    @patch("quotes.providers.brapi")
    def test_fetch_quote_caches_result(self, mock_brapi):
        mock_brapi.fetch_quote.return_value = {"symbol": "VALE3", "regularMarketPrice": 60.0}
        result_1 = fetch_quote("VALE3")
        result_2 = fetch_quote("VALE3")
        assert result_1 == result_2
        mock_brapi.fetch_quote.assert_called_once()

    @patch("quotes.providers.brapi")
    def test_fetch_historical_prices_caches_result(self, mock_brapi):
        mock_brapi.fetch_historical_prices.return_value = [{"date": 1000, "adjustedClose": 10.0}]
        result_1 = fetch_historical_prices("PETR4")
        result_2 = fetch_historical_prices("PETR4")
        assert result_1 == result_2
        mock_brapi.fetch_historical_prices.assert_called_once()

    @patch("quotes.providers.brapi")
    def test_fetch_dividends_caches_result(self, mock_brapi):
        mock_brapi.fetch_dividends.return_value = {"cashDividends": [], "stockDividends": []}
        result_1 = fetch_dividends("ITUB3")
        result_2 = fetch_dividends("ITUB3")
        assert result_1 == result_2
        mock_brapi.fetch_dividends.assert_called_once()

    @patch("quotes.providers.brapi")
    def test_cache_is_per_ticker(self, mock_brapi):
        mock_brapi.fetch_quote.side_effect = [
            {"symbol": "VALE3", "regularMarketPrice": 60.0},
            {"symbol": "PETR4", "regularMarketPrice": 45.0},
        ]
        fetch_quote("VALE3")
        fetch_quote("PETR4")
        assert mock_brapi.fetch_quote.call_count == 2

    @patch("quotes.providers.brapi")
    def test_errors_are_not_cached(self, mock_brapi):
        from quotes.brapi import BRAPIError
        mock_brapi.BRAPIError = BRAPIError
        mock_brapi.fetch_quote.side_effect = BRAPIError("Timeout")
        with pytest.raises(ProviderError):
            fetch_quote("VALE3")
        # After fixing the error, it should retry
        mock_brapi.fetch_quote.side_effect = None
        mock_brapi.fetch_quote.return_value = {"symbol": "VALE3", "regularMarketPrice": 60.0}
        result = fetch_quote("VALE3")
        assert result["symbol"] == "VALE3"
        assert mock_brapi.fetch_quote.call_count == 2
