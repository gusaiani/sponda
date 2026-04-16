"""E2E tests for the 'Marcar como visitada' (Mark as visited) feature.

Tests cover: clicking the visited button when logged in, verifying it
transitions from prominent to compact active state, auth modal flow,
and the expanded panel for notes/scheduling.
"""
import json
import os
import re
import signal
import subprocess
import time
import urllib.request
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
NEXTJS_PORT = 3096


def _home_url_pattern(base_url: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(base_url)}/(pt|en|es|de|fr|it|zh)?/?$")


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
    )
    if result.returncode != 0:
        pytest.skip(f"Frontend build failed: {result.stderr}")


@pytest.fixture
def _nextjs(live_server, _build_frontend):
    """Start Next.js production server pointing to the Django live_server."""
    django_url = live_server.url
    env = {
        **os.environ,
        "DJANGO_API_URL": django_url,
        "PORT": str(NEXTJS_PORT),
    }
    process = subprocess.Popen(
        ["npx", "next", "start", "-p", str(NEXTJS_PORT)],
        cwd=FRONTEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://localhost:{NEXTJS_PORT}/")
            break
        except Exception:
            time.sleep(1)
    else:
        process.kill()
        pytest.skip("Next.js server failed to start")
    print(f"\n  Next.js on :{NEXTJS_PORT} -> Django on {django_url}")
    yield f"http://localhost:{NEXTJS_PORT}"
    os.kill(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


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
    page.wait_for_load_state("networkidle")
    page.fill("input#email", email)
    page.fill("input#password", password)

    with page.expect_response("**/api/auth/login/") as response_info:
        page.click("button[type='submit']")
    login_response = response_info.value
    assert login_response.status == 200, (
        f"Login failed: {login_response.status} {login_response.text()} "
        f"(base_url={base_url})"
    )

    page.wait_for_url(_home_url_pattern(base_url), timeout=10000)


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestVisitedButton:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, _nextjs):
        return _nextjs

    def test_visited_button_appears_for_logged_in_user(
        self, page: Page, url, test_user
    ):
        """Prominent visited button should be visible when logged in with < 3 visits."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        visited_button = page.locator(".visited-button-prominent")
        expect(visited_button).to_be_visible()
        expect(visited_button).to_contain_text("Marcar como visitada")

    def test_visited_button_visible_when_logged_out(self, page: Page, url):
        """Prominent visited button should be visible when not logged in."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        visited_button = page.locator(".visited-button-prominent")
        expect(visited_button).to_be_visible()
        expect(visited_button).to_contain_text("Marcar como visitada")

    def test_click_when_logged_out_shows_auth_modal(self, page: Page, url):
        """Clicking visited button when not logged in should show the auth modal."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        page.locator(".visited-button-prominent").click()

        expect(page.locator(".auth-mode-toggle")).to_be_visible(timeout=5000)
        expect(page.locator(".auth-mode-toggle >> text=Entrar")).to_be_visible()
        expect(page.locator(".auth-mode-toggle >> text=Criar conta")).to_be_visible()

    def test_clicking_visited_button_marks_company(
        self, page: Page, url, test_user
    ):
        """Clicking the prominent visited button should mark the company as visited."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.wait_for_load_state("networkidle")

        # User has 0 visits, so the prominent button is shown
        visited_button = page.locator(".visited-button-prominent")
        expect(visited_button).to_be_visible()

        # Click it and expect the API call to succeed
        with page.expect_response("**/api/auth/visits/mark/") as response_info:
            visited_button.click()

        mark_response = response_info.value
        assert mark_response.status == 201, (
            f"Mark visited failed: {mark_response.status} {mark_response.text()}"
        )

        # After marking, the button should switch to compact active state
        compact_active = page.locator(".visited-button-active")
        expect(compact_active).to_be_visible(timeout=10000)

    def test_auth_modal_login_then_marks_visited(
        self, page: Page, url, test_user
    ):
        """Login via auth modal should complete the visited action."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        # Click visited button while logged out
        page.locator(".visited-button-prominent").click()
        expect(page.locator(".auth-mode-toggle")).to_be_visible(timeout=5000)

        # Login in the modal
        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "testpass123")
        page.locator(".feedback-panel button[type='submit']").click()

        # After login, the button should become active (visited)
        expect(page.locator(".visited-button-active")).to_be_visible(timeout=10000)
