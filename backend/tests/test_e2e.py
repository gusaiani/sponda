"""End-to-end tests using Playwright against Django's live server."""
import os
from datetime import date
from unittest.mock import patch

import pytest
from playwright.sync_api import Page

from quotes.models import BalanceSheet
from tests.conftest import seed_e2e_baseline

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


def _mock_fetch_quote(ticker):
    return {
        "symbol": ticker,
        "longName": f"Test Company {ticker}",
        "shortName": ticker,
        "regularMarketPrice": 50.0,
        "marketCap": 500_000_000_000,
    }


def _mock_sync(ticker):
    return []


@pytest.fixture
def seed_data(db):
    """Seed the database with test data for e2e tests."""
    seed_e2e_baseline("VALE3")
    BalanceSheet.objects.update_or_create(
        ticker="VALE3",
        end_date=date(2025, 9, 30),
        defaults={
            "total_debt": 150_000_000_000,
            "total_liabilities": 300_000_000_000,
            "stockholders_equity": 250_000_000_000,
        },
    )


@pytest.mark.django_db(transaction=True)
class TestE2EWithLiveServer:
    """E2E tests using pytest-django's live_server fixture + Playwright."""

    @pytest.fixture(autouse=True)
    def _setup(self, seed_data):
        pass

    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_cash_flows", side_effect=_mock_sync)
    @patch("quotes.views.sync_balance_sheets", side_effect=_mock_sync)
    @patch("quotes.views.sync_earnings", side_effect=_mock_sync)
    def test_search_returns_pe10(self, _mock1, _mock2, _mock3, _mock4, page: Page, live_server):
        response = page.request.get(f"{live_server.url}/api/quote/VALE3/")
        data = response.json()
        assert data["ticker"] == "VALE3"
        assert data["pe10"] is not None
        assert data["pe10YearsOfData"] == 10

    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_cash_flows", side_effect=_mock_sync)
    @patch("quotes.views.sync_balance_sheets", side_effect=_mock_sync)
    @patch("quotes.views.sync_earnings", side_effect=_mock_sync)
    def test_search_returns_pfcf10(self, _mock1, _mock2, _mock3, _mock4, page: Page, live_server):
        response = page.request.get(f"{live_server.url}/api/quote/VALE3/")
        data = response.json()
        assert data["ticker"] == "VALE3"
        assert data["pfcf10"] is not None
        assert data["pfcf10YearsOfData"] == 10
        assert data["pfcf10Label"] == "PFCF10"
        assert data["avgAdjustedFCF"] is not None

    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_cash_flows", side_effect=_mock_sync)
    @patch("quotes.views.sync_balance_sheets", side_effect=_mock_sync)
    @patch("quotes.views.sync_earnings", side_effect=_mock_sync)
    def test_both_metrics_returned_together(self, _mock1, _mock2, _mock3, _mock4, page: Page, live_server):
        response = page.request.get(f"{live_server.url}/api/quote/VALE3/")
        data = response.json()
        assert data["pe10"] is not None
        assert data["pfcf10"] is not None
        assert "pe10CalculationDetails" in data
        assert "pfcf10CalculationDetails" in data
        assert data["debtToEquity"] is not None
        assert data["liabilitiesToEquity"] is not None

    def test_health_endpoint(self, page: Page, live_server):
        response = page.request.get(f"{live_server.url}/api/health/")
        assert response.status == 200
        assert response.json()["status"] == "ok"

