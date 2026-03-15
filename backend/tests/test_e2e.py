"""End-to-end tests using Playwright against Django's live server."""
import os
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from playwright.sync_api import Page

from quotes.models import IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings

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
    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    for year in range(2016, 2026):
        for month, day in quarter_ends:
            QuarterlyEarnings.objects.create(
                ticker="VALE3",
                end_date=date(year, month, day),
                net_income=10_000_000_000,
            )
    for year in range(2016, 2026):
        IPCAIndex.objects.create(
            date=date(year, 12, 1),
            annual_rate=Decimal("4.5"),
        )
    quarter_ends_cf = [(3, 31), (6, 30), (9, 30), (12, 31)]
    for year in range(2016, 2026):
        for month, day in quarter_ends_cf:
            QuarterlyCashFlow.objects.create(
                ticker="VALE3",
                end_date=date(year, month, day),
                operating_cash_flow=20_000_000_000,
                investment_cash_flow=-8_000_000_000,
            )


@pytest.mark.django_db(transaction=True)
class TestE2EWithLiveServer:
    """E2E tests using pytest-django's live_server fixture + Playwright."""

    @pytest.fixture(autouse=True)
    def _setup(self, seed_data):
        pass

    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_cash_flows", side_effect=_mock_sync)
    @patch("quotes.views.sync_earnings", side_effect=_mock_sync)
    def test_search_returns_pe10(self, _mock1, _mock2, _mock3, page: Page, live_server):
        response = page.request.get(f"{live_server.url}/api/quote/VALE3/")
        data = response.json()
        assert data["ticker"] == "VALE3"
        assert data["pe10"] is not None
        assert data["pe10YearsOfData"] == 10

    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_cash_flows", side_effect=_mock_sync)
    @patch("quotes.views.sync_earnings", side_effect=_mock_sync)
    def test_search_returns_pfcf10(self, _mock1, _mock2, _mock3, page: Page, live_server):
        response = page.request.get(f"{live_server.url}/api/quote/VALE3/")
        data = response.json()
        assert data["ticker"] == "VALE3"
        assert data["pfcf10"] is not None
        assert data["pfcf10YearsOfData"] == 10
        assert data["pfcf10Label"] == "PFCF10"
        assert data["avgAdjustedFCF"] is not None

    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_cash_flows", side_effect=_mock_sync)
    @patch("quotes.views.sync_earnings", side_effect=_mock_sync)
    def test_both_metrics_returned_together(self, _mock1, _mock2, _mock3, page: Page, live_server):
        response = page.request.get(f"{live_server.url}/api/quote/VALE3/")
        data = response.json()
        assert data["pe10"] is not None
        assert data["pfcf10"] is not None
        assert "pe10CalculationDetails" in data
        assert "pfcf10CalculationDetails" in data

    def test_health_endpoint(self, page: Page, live_server):
        response = page.request.get(f"{live_server.url}/api/health/")
        assert response.status == 200
        assert response.json()["status"] == "ok"

