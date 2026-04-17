"""E2E test for the favorites feature using Playwright.

Reproduces the bug: clicking the star to favorite a company does nothing.
"""
import json
import os
import re
import signal
import subprocess
import time
import urllib.request
import pytest
import responses
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from tests.conftest import seed_e2e_baseline

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

User = get_user_model()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
NEXTJS_PORT = 3098

# Matches the post-auth landing URL. The login flow does
# `window.location.href = "/${locale}"`, so the browser lands on e.g.
# `http://localhost:3098/pt`. Accept any supported locale.
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
    seed_e2e_baseline("PETR4")


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

    # Capture the login API response
    with page.expect_response("**/api/auth/login/") as response_info:
        page.click("button[type='submit']")
    login_response = response_info.value
    assert login_response.status == 200, (
        f"Login failed: {login_response.status} {login_response.text()} "
        f"(base_url={base_url})"
    )

    # After successful login, the page does window.location.href = "/${locale}"
    page.wait_for_url(_home_url_pattern(base_url), timeout=10000)


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestFavorites:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, _nextjs):
        return _nextjs

    def test_favorite_star_appears_for_logged_in_user(
        self, page: Page, url, test_user
    ):
        """Prominent favorite button should be visible when logged in with < 3 favorites."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        # Navigate to a company page
        page.goto(f"{url}/PETR4")
        # Wait for the card to load
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        # Prominent button should be visible (user has 0 favorites)
        favorite_button = page.locator(".favorite-button-prominent")
        expect(favorite_button).to_be_visible()
        expect(favorite_button).to_contain_text("Adicionar a Favoritos")

    def test_favorite_star_visible_when_logged_out(self, page: Page, url):
        """Prominent favorite button should be visible when not logged in."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        favorite_button = page.locator(".favorite-button-prominent")
        expect(favorite_button).to_be_visible()
        expect(favorite_button).to_contain_text("Adicionar a Favoritos")

    def test_star_click_when_logged_out_shows_auth_modal(self, page: Page, url):
        """Clicking the prominent button when not logged in should show the auth modal."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        page.locator(".favorite-button-prominent").click()

        # Auth modal should appear with login/signup toggle
        expect(page.locator(".auth-mode-toggle")).to_be_visible(timeout=5000)
        expect(page.locator(".auth-mode-toggle >> text=Entrar")).to_be_visible()
        expect(page.locator(".auth-mode-toggle >> text=Criar conta")).to_be_visible()

    def test_auth_modal_login_then_favorites(self, page: Page, url, test_user):
        """Login via auth modal should complete the favorite action."""
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)

        # Click prominent button while logged out
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".auth-mode-toggle")).to_be_visible(timeout=5000)

        # Login in the modal
        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "testpass123")
        page.locator(".feedback-panel button[type='submit']").click()

        # After login, the star should become active (favorited)
        expect(page.locator(".favorite-button-active")).to_be_visible(timeout=10000)

    def test_clicking_star_favorites_company(self, page: Page, url, test_user):
        """Clicking the prominent button should favorite the company."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.wait_for_load_state("networkidle")

        # User has 0 favorites, so prominent button is shown
        favorite_button = page.locator(".favorite-button-prominent")
        expect(favorite_button).to_be_visible()

        favorite_button.click()

        # After favoriting, it switches to the compact active button
        compact_button = page.locator(".favorite-button-active")
        expect(compact_button).to_be_visible(timeout=10000)
        expect(compact_button).to_have_text("★")

    def test_favorited_company_appears_on_homepage(
        self, page: Page, url, test_user
    ):
        """After favoriting, the company should appear in favorites on home."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        # Favorite PETR4
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.wait_for_load_state("networkidle")
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".favorite-button-active")).to_be_visible(timeout=10000)
        page.wait_for_load_state("networkidle")

        # Go home
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # Should see favorited company as a card on the homepage grid
        expect(
            page.locator(".hcc-ticker >> text=PETR4")
        ).to_be_visible(timeout=10000)

    def test_unfavorite_removes_from_homepage(self, page: Page, url, test_user):
        """Clicking the star again should unfavorite and remove from home."""
        login_via_ui(page, url, "test@example.com", "testpass123")

        # Favorite
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.wait_for_load_state("networkidle")
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".favorite-button-active")).to_be_visible(timeout=10000)
        page.wait_for_load_state("networkidle")

        # Unfavorite — now the compact active button is visible
        page.locator(".favorite-button-active").click()

        # Should revert to prominent (since user now has 0 favorites again)
        expect(page.locator(".favorite-button-prominent")).to_be_visible(timeout=10000)
        page.wait_for_load_state("networkidle")

        # Go home — PETR4 card should still appear (default popular list includes it)
        page.goto(url)
        page.wait_for_load_state("networkidle")
        expect(page.locator(".homepage-grid")).to_be_visible(timeout=10000)
