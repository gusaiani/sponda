"""Tests for POST /api/quotes/batch/.

The batch endpoint is the home page's wedge: instead of fanning out
~60 HTTP requests (PE10 + Fundamentals × ~30 tickers) the client makes
one request and gets a per-ticker dict back. Server-side we fan out to
the existing PE10 logic in a thread pool because most of the wall-clock
is in DB + provider I/O.
"""
import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client

from quotes.models import Ticker


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def mock_brapi_quote():
    return {
        "symbol": "PETR4",
        "longName": "Petroleo Brasileiro SA Pfd",
        "regularMarketPrice": 45.0,
        "marketCap": 585_000_000_000,
    }


@pytest.fixture
def petr4_ticker(db):
    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", sector="Oil",
        market_cap=585_000_000_000, country="BR",
    )


# transaction=True so DB writes performed by the BatchQuotesView's
# ThreadPoolExecutor (which uses a separate Django connection per thread)
# are torn down between tests rather than leaking into the next module.
@pytest.mark.django_db(transaction=True)
class TestQuotesBatchEndpoint:
    def test_rejects_get_method(self, api_client):
        response = api_client.get("/api/quotes/batch/")
        assert response.status_code == 405

    def test_rejects_missing_tickers_field(self, api_client):
        response = api_client.post(
            "/api/quotes/batch/", data={}, content_type="application/json",
        )
        assert response.status_code == 400

    def test_rejects_non_list_tickers(self, api_client):
        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": "PETR4"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_rejects_empty_tickers_list(self, api_client):
        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": []}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_rejects_oversized_batch(self, api_client):
        # Cap is intentional: prevents a malicious client from spawning
        # hundreds of provider calls in one request.
        too_many = [f"T{i:03d}" for i in range(101)]
        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": too_many}),
            content_type="application/json",
        )
        assert response.status_code == 400

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_per_ticker_quote_payload(
        self, _se, _scf, _sbs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": ["PETR4"]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "PETR4" in data["results"]
        entry = data["results"]["PETR4"]
        assert "quote" in entry
        assert entry["quote"]["ticker"] == "PETR4"
        assert "ratings" in entry["quote"]

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_sets_cache_control_on_response(
        self, _se, _scf, _sbs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": ["PETR4"]}),
            content_type="application/json",
        )
        assert "Cache-Control" in response.headers
        assert response.headers["Cache-Control"].startswith("public")

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_partial_failure_returns_error_per_ticker(
        self, _se, _scf, _sbs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        # Provider returns the good ticker but fails on the bad one.
        from quotes.providers import ProviderError

        def side_effect(ticker):
            if ticker == "PETR4":
                return mock_brapi_quote
            raise ProviderError(f"No results for {ticker}")

        mock_quote.side_effect = side_effect
        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": ["PETR4", "BOGUS9"]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert results["PETR4"]["quote"]["ticker"] == "PETR4"
        assert results["BOGUS9"].get("error")

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_dedupes_repeated_tickers(
        self, _se, _scf, _sbs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": ["PETR4", "PETR4", "petr4"]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert list(results.keys()) == ["PETR4"]

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_warm_cache_path_skips_provider(
        self, _se, _scf, _sbs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        # Prime by hitting the per-ticker endpoint first.
        api_client.get("/api/quote/PETR4/")
        mock_quote.reset_mock()
        # Batch request should reuse the cache populated by the GET.
        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": ["PETR4"]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        # No further provider call: cache served the row.
        mock_quote.assert_not_called()
