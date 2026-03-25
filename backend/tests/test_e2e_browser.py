"""Browser-driven end-to-end tests using Playwright.

These tests build the Next.js frontend, start a Django live server for the API,
start Next.js pointing to the Django server, and use Chromium to interact with the UI.
BRAPI HTTP calls are intercepted with the `responses` library (thread-safe).
"""
import json
import os
import signal
import subprocess
import time
import urllib.request
from datetime import date
from decimal import Decimal

import pytest
import responses
from playwright.sync_api import Page, expect

from quotes.models import IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
NEXTJS_PORT = 3099


def _brapi_quote_callback(request):
    """Return a fake BRAPI quote response for any ticker."""
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
    """Build the Next.js frontend once per test session."""
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
    for year in range(2016, 2026):
        for month, day in quarter_ends:
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


@pytest.fixture
def _nextjs(live_server, _build_frontend):
    """Start Next.js production server pointing to the Django live_server."""
    env = {
        **os.environ,
        "DJANGO_API_URL": live_server.url,
        "PORT": str(NEXTJS_PORT),
    }
    process = subprocess.Popen(
        ["npx", "next", "start", "-p", str(NEXTJS_PORT)],
        cwd=FRONTEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for Next.js to be ready
    for attempt in range(30):
        try:
            urllib.request.urlopen(f"http://localhost:{NEXTJS_PORT}/")
            break
        except Exception:
            time.sleep(1)
    else:
        process.kill()
        pytest.skip("Next.js server failed to start")

    yield f"http://localhost:{NEXTJS_PORT}"

    os.kill(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestBrowserSearch:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, _nextjs):
        return _nextjs

    def test_homepage_loads(self, page: Page, url):
        page.goto(url)
        expect(page.locator("text=SPONDA").first).to_be_visible()
        expect(page.locator("text=investidores em valor").first).to_be_visible()

    def test_search_bar_is_visible(self, page: Page, url):
        page.goto(url)
        search_input = page.locator("input[placeholder*='Ticker']").first
        expect(search_input).to_be_visible()

    def test_search_shows_pe10_result(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").first.fill("VALE3")
        page.locator("button[type='submit']").first.click()

        # Wait for the company header to appear with ticker
        expect(page.locator(".company-header-ticker", has_text="VALE3")).to_be_visible(timeout=10000)

        # Should show the company name
        header = page.locator(".company-header-name")
        expect(header).to_be_visible()
        expect(header).to_contain_text("VALE3")

        # Should show P/L10 label
        expect(page.locator(".pe10-label", has_text="P/L10")).to_be_visible()

    def test_search_shows_price(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").first.fill("VALE3")
        page.locator("button[type='submit']").first.click()

        # Should show a current price (R$ followed by a number)
        expect(page.locator("text=/R\\$\\s*[\\d.,]+/").first).to_be_visible(timeout=10000)

    def test_search_shows_pfcf10_label(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").first.fill("VALE3")
        page.locator("button[type='submit']").first.click()

        # Should show P/FCL10 label alongside P/L10
        expect(page.locator(".pe10-label", has_text="P/FCL10")).to_be_visible(timeout=10000)

    def test_search_shows_both_metrics(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").first.fill("VALE3")
        page.locator("button[type='submit']").first.click()

        # Both metric labels should be visible
        expect(page.locator(".pe10-label", has_text="P/L10")).to_be_visible(timeout=10000)
        expect(page.locator(".pe10-label", has_text="P/FCL10")).to_be_visible()

    def test_entenda_melhor_opens_modal(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").first.fill("VALE3")
        page.locator("button[type='submit']").first.click()

        # Wait for card, then click first "Entenda melhor"
        expect(page.locator(".company-header-ticker", has_text="VALE3")).to_be_visible(timeout=10000)
        page.locator(".info-btn").first.click()

        # Modal should appear with explainer content
        expect(page.locator(".modal-overlay")).to_be_visible()
        expect(page.locator(".modal-content")).to_be_visible()

    def test_modal_closes_on_x_button(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").first.fill("VALE3")
        page.locator("button[type='submit']").first.click()

        expect(page.locator(".company-header-ticker", has_text="VALE3")).to_be_visible(timeout=10000)
        page.locator(".info-btn").first.click()
        expect(page.locator(".modal-overlay")).to_be_visible()

        # Close via the X button
        page.locator(".modal-close").click()
        expect(page.locator(".modal-overlay")).not_to_be_visible()

    def test_search_shows_years_of_data(self, page: Page, url):
        page.goto(url)
        page.locator("input[placeholder*='Ticker']").first.fill("VALE3")
        page.locator("button[type='submit']").first.click()

        # Should show 10 years of data
        expect(page.locator(".pe10-detail-value", has_text="10")).to_be_visible(timeout=10000)
