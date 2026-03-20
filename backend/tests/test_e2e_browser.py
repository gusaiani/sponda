"""Browser-driven end-to-end tests using Playwright.

These tests build the frontend, start a Django live server that serves
the SPA, and use a real Chromium browser to interact with the UI.
BRAPI HTTP calls are intercepted with the `responses` library (thread-safe).
"""
import json
import os
import subprocess
from datetime import date
from decimal import Decimal

import pytest
import responses
from playwright.sync_api import Page, expect

from quotes.models import IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

BRAPI_QUOTE_URL = "https://brapi.dev/api/quote/"


def _brapi_quote_callback(request):
    """Return a fake BRAPI quote response for any ticker."""
    # Extract ticker from URL path: /api/quote/VALE3 -> VALE3
    ticker = request.url.split("/quote/")[1].rstrip("/").split("?")[0]
    body = {
        "results": [
            {
                "symbol": ticker,
                "longName": f"Test Company {ticker}",
                "shortName": ticker,
                "regularMarketPrice": 50.0,
                "marketCap": 500_000_000_000,
                "incomeStatementHistoryQuarterly": [],
            }
        ]
    }
    return (200, {}, json.dumps(body))


@pytest.fixture(scope="session")
def _build_frontend():
    """Build the frontend once per test session."""
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"Frontend build failed: {result.stderr}")


@pytest.fixture
def seed_data(db):
    """Seed the database with test data."""
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


@pytest.fixture
def mock_brapi():
    """Mock all BRAPI HTTP requests (thread-safe, works with live_server)."""
    import re

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_callback(
            responses.GET,
            re.compile(r"https://brapi\.dev/api/quote/\w+"),
            callback=_brapi_quote_callback,
        )
        yield rsps


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestBrowserSearch:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, live_server):
        return live_server.url

    def test_homepage_loads(self, page: Page, url):
        page.goto(url)
        expect(page.locator("text=SPONDA").first).to_be_visible()
        expect(page.locator("text=investidores em valor").first).to_be_visible()

    def test_search_bar_is_visible(self, page: Page, url):
        page.goto(url)
        search_input = page.locator("input[placeholder*='Ticker']")
        expect(search_input).to_be_visible()

    def test_search_shows_pe10_result(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").fill("VALE3")
        page.locator("button[type='submit']").click()

        # Wait for the PE10 card to appear with ticker
        expect(page.locator(".pe10-ticker", has_text="VALE3")).to_be_visible(timeout=10000)

        # Should show the company name
        expect(page.locator(".pe10-name", has_text="Test Company VALE3")).to_be_visible()

        # Should show P/L10 label
        expect(page.locator(".pe10-label", has_text="P/L10")).to_be_visible()

    def test_search_shows_price(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").fill("VALE3")
        page.locator("button[type='submit']").click()

        # Should show current price
        expect(page.locator("text=R$ 50,00")).to_be_visible(timeout=10000)

    def test_search_shows_pfcf10_label(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").fill("VALE3")
        page.locator("button[type='submit']").click()

        # Should show P/FCL10 label alongside P/L10
        expect(page.locator(".pe10-label", has_text="P/FCL10")).to_be_visible(timeout=10000)

    def test_search_shows_both_metrics(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").fill("VALE3")
        page.locator("button[type='submit']").click()

        # Both metric labels should be visible
        expect(page.locator(".pe10-label", has_text="P/L10")).to_be_visible(timeout=10000)
        expect(page.locator(".pe10-label", has_text="P/FCL10")).to_be_visible()

    def test_entenda_melhor_opens_modal(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").fill("VALE3")
        page.locator("button[type='submit']").click()

        # Wait for card, then click first "Entenda melhor"
        expect(page.locator(".pe10-ticker", has_text="VALE3")).to_be_visible(timeout=10000)
        page.locator(".info-btn").first.click()

        # Modal should appear with explainer content
        expect(page.locator(".modal-overlay")).to_be_visible()
        expect(page.locator(".modal-content")).to_be_visible()

    def test_modal_closes_on_x_button(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").fill("VALE3")
        page.locator("button[type='submit']").click()

        expect(page.locator(".pe10-ticker", has_text="VALE3")).to_be_visible(timeout=10000)
        page.locator(".info-btn").first.click()
        expect(page.locator(".modal-overlay")).to_be_visible()

        # Close via the X button
        page.locator(".modal-close").click()
        expect(page.locator(".modal-overlay")).not_to_be_visible()

    def test_search_shows_years_of_data(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").fill("VALE3")
        page.locator("button[type='submit']").click()

        # Should show 10 years of data
        expect(page.locator(".pe10-detail-value", has_text="10")).to_be_visible(timeout=10000)


