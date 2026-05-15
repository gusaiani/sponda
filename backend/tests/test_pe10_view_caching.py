"""Tests for PE10View HTTP cache headers.

PE10View must emit ``Cache-Control: public, max-age=...`` so the browser
can short-circuit repeat visits without re-hitting the API. Mirrors what
FundamentalsView already does.
"""
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client

from quotes.models import Ticker


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


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
        symbol="PETR4",
        name="Petrobras",
        sector="Oil",
        market_cap=585_000_000_000,
        country="BR",
    )


@pytest.mark.django_db
class TestPE10ViewCacheControl:
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_cold_response_sets_cache_control(
        self, _sync_e, _sync_cf, _sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 200
        cache_control = response["Cache-Control"]
        assert "public" in cache_control
        assert "max-age=" in cache_control

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_warm_response_keeps_cache_control(
        self, _sync_e, _sync_cf, _sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        # Prime cache.
        api_client.get("/api/quote/PETR4/")
        # Subsequent request hits the in-memory cache path; header still set.
        response = api_client.get("/api/quote/PETR4/")
        assert response["Cache-Control"].startswith("public")
