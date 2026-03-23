"""E2E test for the favorites feature using Playwright.

Reproduces the bug: clicking the star to favorite a company does nothing.
"""
import json
import os
import re
import subprocess
from datetime import date
from decimal import Decimal

import pytest
import responses
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from quotes.models import IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

User = get_user_model()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")


def _brapi_quote_callback(request):
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
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        env={**os.environ, "GOOGLE_CLIENT_ID": "test"},
    )
    if result.returncode != 0:
        pytest.skip(f"Frontend build failed: {result.stderr}")


@pytest.fixture
def seed_data(db):
    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    for year in range(2016, 2026):
        for month, day in quarter_ends:
            QuarterlyEarnings.objects.create(
                ticker="PETR4",
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
                ticker="PETR4",
                end_date=date(year, month, day),
                operating_cash_flow=20_000_000_000,
                investment_cash_flow=-8_000_000_000,
            )


@pytest.fixture
def mock_brapi():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_callback(
            responses.GET,
            re.compile(r"https://brapi\.dev/api/quote/\w+"),
            callback=_brapi_quote_callback,
        )
        yield rsps


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        password="testpass123",
    )


def login_via_ui(page: Page, base_url: str, email: str, password: str):
    """Log in via the unified login page."""
    page.goto(f"{base_url}/login")
    page.fill("input#email", email)
    page.fill("input#password", password)
    page.click("button[type='submit']")
    # Wait for redirect to home
    page.wait_for_url(base_url + "/", timeout=10000)


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestFavorites:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, live_server):
        return live_server.url

    def test_favorite_star_appears_for_logged_in_user(
        self, page: Page, url, test_user
    ):
        """Star should be visible on the company card when logged in."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        # Navigate to a company page
        page.goto(f"{url}/PETR4")
        # Wait for the card to load
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        # Star button should be visible
        favorite_button = page.locator(".favorite-button")
        expect(favorite_button).to_be_visible()

    def test_favorite_star_visible_when_logged_out(self, page: Page, url):
        """Star should be visible even when not logged in."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        favorite_button = page.locator(".favorite-button")
        expect(favorite_button).to_be_visible()

    def test_star_click_when_logged_out_shows_auth_modal(self, page: Page, url):
        """Clicking the star when not logged in should show the auth modal."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        page.locator(".favorite-button").click()

        # Auth modal should appear with login/signup toggle
        expect(page.locator(".auth-mode-toggle")).to_be_visible(timeout=5000)
        expect(page.locator(".auth-mode-toggle >> text=Entrar")).to_be_visible()
        expect(page.locator(".auth-mode-toggle >> text=Criar conta")).to_be_visible()

    def test_auth_modal_login_then_favorites(self, page: Page, url, test_user):
        """Login via auth modal should complete the favorite action."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        # Click star while logged out
        page.locator(".favorite-button").click()
        expect(page.locator(".auth-mode-toggle")).to_be_visible(timeout=5000)

        # Login in the modal
        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "testpass123")
        page.locator(".feedback-panel button[type='submit']").click()

        # After login, the star should become active (favorited)
        expect(page.locator(".favorite-button-active")).to_be_visible(timeout=10000)

    def test_clicking_star_favorites_company(self, page: Page, url, test_user):
        """Clicking the star should toggle it to active (golden)."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.wait_for_load_state("networkidle")

        favorite_button = page.locator(".favorite-button")
        expect(favorite_button).to_be_visible()
        expect(favorite_button).to_have_text("☆")

        favorite_button.click()

        expect(favorite_button).to_have_text("★", timeout=10000)
        expect(favorite_button).to_have_class(re.compile("favorite-button-active"))

    def test_favorited_company_appears_on_homepage(
        self, page: Page, url, test_user
    ):
        """After favoriting, the company should appear in favorites on home."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        # Favorite PETR4
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.locator(".favorite-button").click()
        expect(page.locator(".favorite-button-active")).to_be_visible(timeout=5000)

        # Go home
        page.goto(url)

        # Should see favorites section
        expect(
            page.locator("text=Favoritas")
        ).to_be_visible(timeout=5000)

    def test_unfavorite_removes_from_homepage(self, page: Page, url, test_user):
        """Clicking the star again should unfavorite and remove from home."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        # Favorite
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.locator(".favorite-button").click()
        expect(page.locator(".favorite-button-active")).to_be_visible(timeout=5000)

        # Unfavorite
        page.locator(".favorite-button").click()
        expect(page.locator(".favorite-button")).not_to_have_class(
            re.compile("favorite-button-active"), timeout=5000
        )

        # Go home — should NOT see favorites section
        page.goto(url)
        expect(page.locator("text=Favoritas")).not_to_be_visible(timeout=3000)
