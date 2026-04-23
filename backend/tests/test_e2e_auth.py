"""E2E tests for authentication flows: login page, signup, auth modal (from
favorite and save list), error handling, and post-auth action completion."""
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

from accounts.models import FavoriteCompany
from quotes.models import Ticker
from tests.conftest import seed_e2e_baseline

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

User = get_user_model()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
NEXTJS_PORT = 3097

# Matches the post-auth landing URL. The login/signup flows do
# `window.location.href = "/${locale}"`, so the browser lands on e.g.
# `http://localhost:3097/pt`. Accept any supported locale (or a bare `/`
# if locale middleware ever stops prefixing).
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
    for _ in range(30):
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


# ── Helpers ──


def fill_login_form(page: Page, email: str, password: str, selector_prefix: str = ""):
    """Fill login form fields. selector_prefix differentiates page vs modal."""
    email_selector = f"input#{selector_prefix}email" if not selector_prefix else f"input#{selector_prefix}-email"
    password_selector = f"input#{selector_prefix}password" if not selector_prefix else f"input#{selector_prefix}-password"
    page.fill(email_selector, email)
    page.fill(password_selector, password)


def submit_modal_form(page: Page):
    """Click the submit button inside the auth modal."""
    page.locator(".feedback-panel button[type='submit']").click()


def submit_page_form(page: Page):
    """Click the submit button on the login page."""
    page.locator(".auth-card button[type='submit']").click()


# ── Login Page Tests ──


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestLoginPage:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, _nextjs):
        return _nextjs

    def test_login_page_loads(self, page: Page, url):
        page.goto(f"{url}/login")
        expect(page.locator(".auth-mode-toggle")).to_be_visible(timeout=5000)
        expect(page.locator("input#email")).to_be_visible()
        expect(page.locator("input#password")).to_be_visible()

    def test_login_success_redirects_to_home(self, page: Page, url, test_user):
        page.goto(f"{url}/login")
        fill_login_form(page, "test@example.com", "testpass123")
        submit_page_form(page)
        page.wait_for_url(_home_url_pattern(url), timeout=10000)

    def test_login_wrong_password_shows_error(self, page: Page, url, test_user):
        page.goto(f"{url}/login")
        fill_login_form(page, "test@example.com", "wrongpassword")
        submit_page_form(page)
        expect(page.locator(".auth-error")).to_be_visible(timeout=5000)
        expect(page.locator(".auth-error")).to_contain_text("incorretos")

    def test_login_nonexistent_email_shows_error(self, page: Page, url):
        page.goto(f"{url}/login")
        fill_login_form(page, "nobody@example.com", "testpass123")
        submit_page_form(page)
        expect(page.locator(".auth-error")).to_be_visible(timeout=5000)
        expect(page.locator(".auth-error")).to_contain_text("incorretos")

    def test_close_button_navigates_to_home(self, page: Page, url):
        page.goto(f"{url}/login")
        expect(page.locator(".auth-header-close")).to_be_visible(timeout=5000)
        page.locator(".auth-header-close").click()
        page.wait_for_url(_home_url_pattern(url), timeout=5000)


# ── Signup Page Tests ──


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestSignupPage:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, _nextjs):
        return _nextjs

    def test_switch_to_signup_mode(self, page: Page, url):
        page.goto(f"{url}/login")
        page.locator(".auth-mode-toggle >> text=Criar conta").click()
        # Confirm password field should appear
        expect(page.locator("input#confirm-password")).to_be_visible(timeout=3000)

    def test_signup_success_redirects_home_logged_in(self, page: Page, url):
        page.goto(f"{url}/login")
        page.locator(".auth-mode-toggle >> text=Criar conta").click()

        page.fill("input#email", "newuser@example.com")
        page.fill("input#password", "securepass123")
        page.fill("input#confirm-password", "securepass123")
        submit_page_form(page)

        # Should show email verification prompt
        expect(page.locator(".auth-signup-success")).to_be_visible(timeout=10000)
        expect(page.locator("text=Confirme seu email")).to_be_visible()

        # Click continue to go to homepage
        page.locator("text=Ir para a página inicial").click()
        page.wait_for_url(_home_url_pattern(url), timeout=10000)

        # Should be logged in (sees "Minha conta", not "Entrar")
        expect(page.locator("text=Minha conta")).to_be_visible(timeout=5000)
        expect(page.locator("text=Entrar")).not_to_be_visible()

        # User should exist in DB
        assert User.objects.filter(email="newuser@example.com").exists()

    def test_signup_password_mismatch_shows_error(self, page: Page, url):
        page.goto(f"{url}/login")
        page.locator(".auth-mode-toggle >> text=Criar conta").click()

        page.fill("input#email", "newuser@example.com")
        page.fill("input#password", "securepass123")
        page.fill("input#confirm-password", "differentpass")
        submit_page_form(page)

        expect(page.locator(".auth-error")).to_be_visible(timeout=5000)
        expect(page.locator(".auth-error")).to_contain_text("coincidem")

    def test_signup_duplicate_email_shows_error(self, page: Page, url, test_user):
        page.goto(f"{url}/login")
        page.locator(".auth-mode-toggle >> text=Criar conta").click()

        page.fill("input#email", "test@example.com")
        page.fill("input#password", "securepass123")
        page.fill("input#confirm-password", "securepass123")
        submit_page_form(page)

        expect(page.locator(".auth-error")).to_be_visible(timeout=5000)

    def test_signup_allow_contact_checked_by_default(self, page: Page, url):
        page.goto(f"{url}/login")
        page.locator(".auth-mode-toggle >> text=Criar conta").click()
        checkbox = page.locator(".auth-checkbox")
        expect(checkbox).to_be_checked()

    def test_signup_saves_allow_contact(self, page: Page, url):
        page.goto(f"{url}/login")
        page.locator(".auth-mode-toggle >> text=Criar conta").click()

        page.fill("input#email", "contact@example.com")
        page.fill("input#password", "securepass123")
        page.fill("input#confirm-password", "securepass123")
        # Checkbox is checked by default — leave it
        submit_page_form(page)

        # Should show email verification prompt
        expect(page.locator(".auth-signup-success")).to_be_visible(timeout=10000)

        # Click continue to go to homepage
        page.locator("text=Ir para a página inicial").click()
        page.wait_for_url(_home_url_pattern(url), timeout=10000)

        user = User.objects.get(email="contact@example.com")
        assert user.allow_contact is True


# ── Auth Modal via Favorite ──


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestAuthModalFromFavorite:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, _nextjs):
        return _nextjs

    def test_modal_appears_on_star_click(self, page: Page, url):
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".feedback-panel .auth-mode-toggle")).to_be_visible(timeout=5000)

    def test_modal_login_wrong_password_shows_error(self, page: Page, url, test_user):
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".feedback-panel")).to_be_visible(timeout=5000)

        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "wrongpassword")
        submit_modal_form(page)

        expect(page.locator(".feedback-panel .auth-error")).to_be_visible(timeout=5000)
        expect(page.locator(".feedback-panel .auth-error")).to_contain_text("incorretos")

    def test_modal_login_then_favorites(self, page: Page, url, test_user):
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".feedback-panel")).to_be_visible(timeout=5000)

        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "testpass123")
        submit_modal_form(page)

        # Modal should close and star should be active
        expect(page.locator(".feedback-panel")).not_to_be_visible(timeout=10000)
        expect(page.locator(".favorite-button-active")).to_be_visible(timeout=10000)

    def test_modal_signup_then_favorites(self, page: Page, url):
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".feedback-panel")).to_be_visible(timeout=5000)

        # Switch to signup
        page.locator(".feedback-panel .auth-mode-toggle >> text=Criar conta").click()
        expect(page.locator("input#modal-confirm-password")).to_be_visible(timeout=3000)

        page.fill("input#modal-email", "newvia-star@example.com")
        page.fill("input#modal-password", "securepass123")
        page.fill("input#modal-confirm-password", "securepass123")
        submit_modal_form(page)

        # Modal should close and star should be active
        expect(page.locator(".feedback-panel")).not_to_be_visible(timeout=10000)
        expect(page.locator(".favorite-button-active")).to_be_visible(timeout=10000)

        assert User.objects.filter(email="newvia-star@example.com").exists()

    def test_modal_close_on_overlay_click(self, page: Page, url):
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".feedback-panel")).to_be_visible(timeout=5000)

        # Click the overlay (outside the panel)
        page.locator(".feedback-overlay").click(position={"x": 10, "y": 10})
        expect(page.locator(".feedback-panel")).not_to_be_visible(timeout=3000)

    def test_modal_close_on_x_button(self, page: Page, url):
        page.goto(f"{url}/PETR4")
        expect(page.locator(".company-header-name")).to_be_visible(timeout=10000)
        page.locator(".favorite-button-prominent").click()
        expect(page.locator(".feedback-panel")).to_be_visible(timeout=5000)

        page.locator(".feedback-close").click()
        expect(page.locator(".feedback-panel")).not_to_be_visible(timeout=3000)


# ── Auth Modal via Save List ──


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestAuthModalFromSaveList:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        pass

    @pytest.fixture
    def url(self, _nextjs):
        return _nextjs

    def test_save_list_button_visible_when_logged_out(self, page: Page, url):
        page.goto(f"{url}/PETR4/comparar")
        expect(page.locator(".compare-save-floating")).to_be_visible(timeout=10000)

    def test_save_list_click_when_logged_out_shows_auth_modal(self, page: Page, url):
        page.goto(f"{url}/PETR4/comparar")
        expect(page.locator(".compare-save-floating")).to_be_visible(timeout=10000)
        page.locator(".compare-save-floating").click()

        expect(page.locator(".feedback-panel .auth-mode-toggle")).to_be_visible(timeout=5000)

    def test_save_list_login_then_save_form_opens(self, page: Page, url, test_user):
        page.goto(f"{url}/PETR4/comparar")
        expect(page.locator(".compare-save-floating")).to_be_visible(timeout=10000)
        page.locator(".compare-save-floating").click()

        # Auth modal appears
        expect(page.locator(".feedback-panel")).to_be_visible(timeout=5000)

        # Login
        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "testpass123")
        submit_modal_form(page)

        # Auth modal closes, save form modal should open
        expect(page.locator(".compare-save-modal")).to_be_visible(timeout=10000)
        expect(page.locator(".compare-save-modal input[placeholder='Nome da lista']")).to_be_visible()

    def test_save_list_signup_then_save_form_opens(self, page: Page, url):
        page.goto(f"{url}/PETR4/comparar")
        expect(page.locator(".compare-save-floating")).to_be_visible(timeout=10000)
        page.locator(".compare-save-floating").click()

        expect(page.locator(".feedback-panel")).to_be_visible(timeout=5000)

        # Switch to signup
        page.locator(".feedback-panel .auth-mode-toggle >> text=Criar conta").click()
        page.fill("input#modal-email", "newvia-list@example.com")
        page.fill("input#modal-password", "securepass123")
        page.fill("input#modal-confirm-password", "securepass123")
        submit_modal_form(page)

        # Save form should open
        expect(page.locator(".compare-save-modal")).to_be_visible(timeout=10000)
        assert User.objects.filter(email="newvia-list@example.com").exists()

    def test_save_list_modal_login_error_then_retry(self, page: Page, url, test_user):
        page.goto(f"{url}/PETR4/comparar")
        expect(page.locator(".compare-save-floating")).to_be_visible(timeout=10000)
        page.locator(".compare-save-floating").click()

        expect(page.locator(".feedback-panel")).to_be_visible(timeout=5000)

        # Wrong password
        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "wrongpassword")
        submit_modal_form(page)

        expect(page.locator(".feedback-panel .auth-error")).to_be_visible(timeout=5000)

        # Correct password
        page.fill("input#modal-password", "testpass123")
        submit_modal_form(page)

        # Save form should open
        expect(page.locator(".compare-save-modal")).to_be_visible(timeout=10000)


# ── Homepage Add Favorite Card ──


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_build_frontend")
class TestHomepageAddFavoriteCard:
    @pytest.fixture(autouse=True)
    def _setup(self, seed_data, mock_brapi):
        # Seed ticker so the search dropdown can find PETR4
        Ticker.objects.create(
            symbol="PETR4", name="Petroleo Brasileiro", display_name="Petrobras",
            sector="Energy Minerals", type="stock", logo="https://icons.brapi.dev/icons/PETR4.svg",
        )

    @pytest.fixture
    def url(self, _nextjs):
        return _nextjs

    def test_placeholder_visible_when_logged_out(self, page: Page, url):
        page.goto(url)
        expect(page.locator(".hcc-add-favorite-card")).to_be_visible(timeout=15000)
        expect(page.locator(".hcc-add-favorite-input")).to_be_visible()

    def test_auth_modal_opens_on_select(self, page: Page, url):
        """Selecting a company in the placeholder should open auth modal."""
        page.goto(url)
        expect(page.locator(".hcc-add-favorite-card")).to_be_visible(timeout=15000)

        page.locator(".hcc-add-favorite-input").fill("PETR")
        expect(page.locator(".search-dropdown-item")).to_be_visible(timeout=10000)
        page.locator(".search-dropdown-item").first.click()

        # Auth modal should appear
        expect(page.locator(".feedback-panel .auth-mode-toggle")).to_be_visible(timeout=10000)

    def test_signup_via_placeholder_adds_favorite(self, page: Page, url):
        """Full flow: select company -> signup -> company auto-added as favorite."""
        page.goto(url)
        expect(page.locator(".hcc-add-favorite-card")).to_be_visible(timeout=15000)

        # Select PETR4 from the placeholder search
        page.locator(".hcc-add-favorite-input").fill("PETR")
        expect(page.locator(".search-dropdown-item")).to_be_visible(timeout=10000)
        page.locator(".search-dropdown-item").first.click()

        # Auth modal opens - switch to signup
        expect(page.locator(".feedback-panel .auth-mode-toggle")).to_be_visible(timeout=10000)
        page.locator(".feedback-panel .auth-mode-toggle >> text=Criar conta").click()

        # Fill signup form
        page.locator(".feedback-panel input#modal-email").fill("homepage-fav@test.com")
        page.locator(".feedback-panel input#modal-password").fill("securepass123")
        page.locator(".feedback-panel input#modal-confirm-password").fill("securepass123")
        submit_modal_form(page)

        # Wait for modal to close and page to update
        expect(page.locator(".feedback-panel")).not_to_be_visible(timeout=15000)

        # User should be logged in
        expect(page.locator("text=Minha conta")).to_be_visible(timeout=15000)

        # PETR4 should now be in their favorites (visible as a card on homepage)
        expect(page.locator(".hcc-ticker >> text=PETR4")).to_be_visible(timeout=15000)

    def test_login_via_placeholder_adds_new_favorite(self, page: Page, url, test_user):
        """Existing user logs in via placeholder. The selected company is added
        to their favorites in the database."""
        # Seed a second ticker for the new favorite
        Ticker.objects.get_or_create(
            symbol="VALE3", defaults=dict(
                name="Vale", display_name="Vale",
                sector="Non-Energy Minerals", type="stock",
                logo="https://icons.brapi.dev/icons/VALE3.svg",
            ),
        )
        # Give the existing user a pre-existing favorite (PETR4)
        FavoriteCompany.objects.create(user=test_user, ticker="PETR4")

        # Go to homepage (logged out)
        page.goto(url)
        expect(page.locator(".hcc-add-favorite-card")).to_be_visible(timeout=15000)

        # Select VALE3 (a new favorite) from the placeholder
        page.locator(".hcc-add-favorite-input").fill("VALE")
        expect(page.locator(".search-dropdown-item")).to_be_visible(timeout=10000)
        page.locator(".search-dropdown-item").first.click()

        # Auth modal opens - login with existing account
        expect(page.locator(".feedback-panel .auth-mode-toggle")).to_be_visible(timeout=10000)
        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "testpass123")
        submit_modal_form(page)

        # Modal closes, user is logged in
        expect(page.locator(".feedback-panel")).not_to_be_visible(timeout=15000)
        expect(page.locator("text=Minha conta")).to_be_visible(timeout=15000)

        # Wait for the favorite to be added to the database
        page.wait_for_timeout(3000)

        # Both favorites should exist in DB
        assert FavoriteCompany.objects.filter(user=test_user, ticker="PETR4").exists()
        assert FavoriteCompany.objects.filter(user=test_user, ticker="VALE3").exists()

    def test_login_via_placeholder_does_not_duplicate_existing_favorite(self, page: Page, url, test_user):
        """If the selected company is already a favorite, don't duplicate it."""
        # User already has PETR4 as favorite
        FavoriteCompany.objects.create(user=test_user, ticker="PETR4")

        page.goto(url)
        expect(page.locator(".hcc-add-favorite-card")).to_be_visible(timeout=15000)

        # Select PETR4 (already a favorite)
        page.locator(".hcc-add-favorite-input").fill("PETR")
        expect(page.locator(".search-dropdown-item")).to_be_visible(timeout=10000)
        page.locator(".search-dropdown-item").first.click()

        # Login
        expect(page.locator(".feedback-panel .auth-mode-toggle")).to_be_visible(timeout=10000)
        page.fill("input#modal-email", "test@example.com")
        page.fill("input#modal-password", "testpass123")
        submit_modal_form(page)

        expect(page.locator(".feedback-panel")).not_to_be_visible(timeout=15000)
        expect(page.locator("text=Minha conta")).to_be_visible(timeout=15000)

        # Wait for any pending favorite operations
        page.wait_for_timeout(3000)

        # Should still have exactly 1 favorite (not duplicated)
        assert FavoriteCompany.objects.filter(user=test_user, ticker="PETR4").count() == 1
