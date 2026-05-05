"""Tests for the Learning Mode ratings block on the PE10/quote endpoint.

The endpoint must include a ``ratings`` block when indicators are
computable. Sector lookup feeds into per-sector threshold overrides
(currently only the default profile, but the wiring must be present).
"""
from unittest.mock import patch

import pytest
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
        "marketCap": 585000000000,
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
class TestQuoteEndpointRatings:
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_response_includes_ratings_block(
        self, _sync_e, _sync_cf, _sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 200
        data = response.json()
        assert "ratings" in data
        ratings = data["ratings"]
        assert "overall" in ratings
        assert "methodologyVersion" in ratings
        assert ratings["methodologyVersion"]

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_per_indicator_ratings_match_camelcase_keys(
        self, _sync_e, _sync_cf, _sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        ratings = response.json()["ratings"]
        # All indicator keys are present (value may be null when source
        # data is missing). Keys must be camelCase to match the rest of
        # the response shape.
        for key in (
            "pe10", "pfcf10", "peg", "pfcfPeg",
            "debtToEquity", "debtExLeaseToEquity", "liabilitiesToEquity",
            "currentRatio", "debtToAvgEarnings", "debtToAvgFCF",
        ):
            assert key in ratings

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_ratings_are_one_through_five_or_null(
        self, _sync_e, _sync_cf, _sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote, petr4_ticker,
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        ratings = response.json()["ratings"]
        for key, tier in ratings.items():
            if key in ("overall", "methodologyVersion"):
                continue
            assert tier is None or (isinstance(tier, int) and 1 <= tier <= 5)

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_works_when_ticker_row_missing(
        self, _sync_e, _sync_cf, _sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote,
    ):
        # No Ticker row (sector unknown). Ratings should still come back,
        # using default-sector thresholds.
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 200
        data = response.json()
        assert "ratings" in data
