"""Tests for accounts: auth, favorites, saved lists, feedback, admin dashboard."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from accounts.models import CompanyVisit, EmailVerificationToken, FavoriteCompany, PageView, PasswordResetToken, SavedList, SavedScreenerFilter, UserOperation
from quotes.models import LookupLog

User = get_user_model()


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        password="securepass123",
    )


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.login(username="test@example.com", password="securepass123")
    return api_client


# ── Signup ──


class TestSignup:
    def test_signup_creates_user(self, api_client, db):
        response = api_client.post(
            "/api/auth/signup/",
            {"email": "new@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["email"] == "new@example.com"
        assert User.objects.filter(email="new@example.com").exists()

    def test_signup_sends_welcome_email(self, api_client, db):
        from django.core import mail

        api_client.post(
            "/api/auth/signup/",
            {"email": "welcome@example.com", "password": "testpass123", "language": "pt"},
            content_type="application/json",
        )
        assert len(mail.outbox) == 2  # welcome + verification
        welcome_email = mail.outbox[0]
        assert welcome_email.to == ["welcome@example.com"]
        assert "boas-vindas" in welcome_email.subject
        assert "Sponda" in welcome_email.subject
        assert "Favoritar empresas" in welcome_email.body
        assert "Salvar listas" in welcome_email.body

    def test_signup_welcome_email_has_html(self, api_client, db):
        from django.core import mail

        api_client.post(
            "/api/auth/signup/",
            {"email": "html@example.com", "password": "testpass123", "language": "pt"},
            content_type="application/json",
        )
        welcome_email = mail.outbox[0]
        # Should have HTML alternative
        assert len(welcome_email.alternatives) == 1
        html_content = welcome_email.alternatives[0][0]
        assert "Explorar agora" in html_content
        assert "SPONDA" in html_content
        assert "#1b347e" in html_content

    def test_signup_logs_in_user(self, api_client, db):
        api_client.post(
            "/api/auth/signup/",
            {"email": "new@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        # User should be authenticated now
        response = api_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert response.json()["email"] == "new@example.com"

    def test_signup_with_allow_contact(self, api_client, db):
        api_client.post(
            "/api/auth/signup/",
            {"email": "new@example.com", "password": "testpass123", "allow_contact": True},
            content_type="application/json",
        )
        user = User.objects.get(email="new@example.com")
        assert user.allow_contact is True

    def test_signup_without_allow_contact_defaults_false(self, api_client, db):
        api_client.post(
            "/api/auth/signup/",
            {"email": "new@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        user = User.objects.get(email="new@example.com")
        assert user.allow_contact is False

    def test_signup_duplicate_email_fails(self, api_client, user):
        response = api_client.post(
            "/api/auth/signup/",
            {"email": "test@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.json()
        error_message = data["email"][0]
        assert error_message == "Já existe uma conta com este email."

    def test_signup_short_password_fails(self, api_client, db):
        response = api_client.post(
            "/api/auth/signup/",
            {"email": "new@example.com", "password": "short"},
            content_type="application/json",
        )
        assert response.status_code == 400


class TestSignupLanguage:
    def test_language_defaults_to_en_without_header_or_body(self, api_client, db):
        api_client.post(
            "/api/auth/signup/",
            {"email": "default@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        user = User.objects.get(email="default@example.com")
        assert user.language == "en"

    def test_language_from_body_stored_on_user(self, api_client, db):
        api_client.post(
            "/api/auth/signup/",
            {"email": "fr@example.com", "password": "testpass123", "language": "fr"},
            content_type="application/json",
        )
        user = User.objects.get(email="fr@example.com")
        assert user.language == "fr"

    def test_language_from_accept_language_header(self, api_client, db):
        api_client.post(
            "/api/auth/signup/",
            {"email": "header@example.com", "password": "testpass123"},
            content_type="application/json",
            HTTP_ACCEPT_LANGUAGE="fr-CA,fr;q=0.9,en;q=0.8",
        )
        user = User.objects.get(email="header@example.com")
        assert user.language == "fr"

    def test_unsupported_language_falls_back_to_en(self, api_client, db):
        api_client.post(
            "/api/auth/signup/",
            {"email": "unsupp@example.com", "password": "testpass123", "language": "xx"},
            content_type="application/json",
        )
        user = User.objects.get(email="unsupp@example.com")
        assert user.language == "en"

    def test_body_language_beats_accept_language_header(self, api_client, db):
        api_client.post(
            "/api/auth/signup/",
            {"email": "both@example.com", "password": "testpass123", "language": "de"},
            content_type="application/json",
            HTTP_ACCEPT_LANGUAGE="fr-CA,fr;q=0.9",
        )
        user = User.objects.get(email="both@example.com")
        assert user.language == "de"


class TestWelcomeEmailLocalization:
    @pytest.mark.parametrize(
        "lang,tagline,welcome_heading,cta",
        [
            ("pt", "Para investidores em valor", "Te damos as boas-vindas", "Explorar agora"),
            ("en", "For value investors", "Welcome", "Explore now"),
            ("es", "Para inversores de valor", "Te damos la bienvenida", "Explorar ahora"),
            ("fr", "Pour les investisseurs value", "Bienvenue", "Explorer"),
            ("de", "Für Value-Investoren", "Willkommen", "Jetzt erkunden"),
            ("it", "Per investitori value", "Benvenuto", "Esplora ora"),
            ("zh", "为价值投资者而设", "欢迎", "立即探索"),
        ],
    )
    def test_welcome_email_rendered_in_user_language(
        self, api_client, db, lang, tagline, welcome_heading, cta,
    ):
        from django.core import mail

        api_client.post(
            "/api/auth/signup/",
            {"email": f"{lang}@example.com", "password": "testpass123", "language": lang},
            content_type="application/json",
        )
        welcome_email = mail.outbox[0]
        html_content = welcome_email.alternatives[0][0]
        assert tagline in html_content
        assert welcome_heading in html_content
        assert cta in html_content
        # Legacy Portuguese tagline must not leak into other locales
        if lang != "pt":
            assert "Indicadores de empresas brasileiras" not in html_content

    def test_welcome_email_does_not_use_legacy_tagline(self, api_client, db):
        from django.core import mail

        api_client.post(
            "/api/auth/signup/",
            {"email": "tag@example.com", "password": "testpass123", "language": "pt"},
            content_type="application/json",
        )
        welcome_html = mail.outbox[0].alternatives[0][0]
        assert "Indicadores de empresas brasileiras para investidores em valor" not in welcome_html


class TestVerificationEmailLocalization:
    @pytest.mark.parametrize(
        "lang,heading,button",
        [
            ("pt", "Confirme seu email", "Verificar email"),
            ("en", "Confirm your email", "Verify email"),
            ("es", "Confirma tu email", "Verificar email"),
            ("fr", "Confirmez votre e-mail", "Vérifier l'e-mail"),
            ("de", "Bestätige deine E-Mail", "E-Mail bestätigen"),
            ("it", "Conferma la tua email", "Verifica email"),
            ("zh", "确认您的邮箱", "验证邮箱"),
        ],
    )
    def test_verification_email_rendered_in_user_language(
        self, api_client, db, lang, heading, button,
    ):
        from django.core import mail

        api_client.post(
            "/api/auth/signup/",
            {"email": f"v{lang}@example.com", "password": "testpass123", "language": lang},
            content_type="application/json",
        )
        verification_email = mail.outbox[1]
        html_content = verification_email.alternatives[0][0]
        assert heading in html_content
        assert button in html_content
        if lang != "pt":
            assert "Indicadores de empresas brasileiras" not in html_content


# ── Login ──


class TestLogin:
    def test_login_success(self, api_client, user):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "test@example.com", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    def test_login_wrong_password(self, api_client, user):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "test@example.com", "password": "wrongpassword"},
            content_type="application/json",
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Email ou senha incorretos"

    def test_login_nonexistent_user_returns_portuguese_error(self, api_client, db):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "nobody@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Email ou senha incorretos"

    def test_login_nonexistent_user(self, api_client, db):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "nobody@example.com", "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 401


# ── Logout ──


class TestLogout:
    def test_logout(self, authenticated_client):
        response = authenticated_client.post("/api/auth/logout/")
        assert response.status_code == 200

        # Should no longer be authenticated
        response = authenticated_client.get("/api/auth/me/")
        assert response.status_code == 401


# ── Me ──


class TestMe:
    def test_me_authenticated(self, authenticated_client, user):
        response = authenticated_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    def test_me_unauthenticated(self, api_client, db):
        response = api_client.get("/api/auth/me/")
        assert response.status_code == 401

    def test_me_returns_language(self, api_client, user):
        user.language = "it"
        user.save(update_fields=["language"])
        api_client.login(username="test@example.com", password="securepass123")
        response = api_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert response.json()["language"] == "it"

    def test_me_sets_language_cookie(self, api_client, user):
        user.language = "de"
        user.save(update_fields=["language"])
        api_client.login(username="test@example.com", password="securepass123")
        response = api_client.get("/api/auth/me/")
        assert response.cookies["sponda-lang"].value == "de"


class TestLanguagePersistence:
    COOKIE_NAME = "sponda-lang"

    def test_login_sets_language_cookie_from_user(self, api_client, user):
        user.language = "fr"
        user.save(update_fields=["language"])
        response = api_client.post(
            "/api/auth/login/",
            {"email": "test@example.com", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.cookies[self.COOKIE_NAME].value == "fr"

    def test_signup_sets_language_cookie(self, api_client, db):
        response = api_client.post(
            "/api/auth/signup/",
            {"email": "ck@example.com", "password": "testpass123", "language": "de"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.cookies[self.COOKIE_NAME].value == "de"

    def test_update_language_persists(self, authenticated_client, user):
        response = authenticated_client.patch(
            "/api/auth/language/",
            {"language": "zh"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["language"] == "zh"
        user.refresh_from_db()
        assert user.language == "zh"

    def test_update_language_sets_cookie(self, authenticated_client, user):
        response = authenticated_client.patch(
            "/api/auth/language/",
            {"language": "es"},
            content_type="application/json",
        )
        assert response.cookies[self.COOKIE_NAME].value == "es"

    def test_update_language_rejects_unsupported(self, authenticated_client, user):
        response = authenticated_client.patch(
            "/api/auth/language/",
            {"language": "xx"},
            content_type="application/json",
        )
        assert response.status_code == 400
        user.refresh_from_db()
        assert user.language != "xx"

    def test_update_language_requires_auth(self, api_client, db):
        response = api_client.patch(
            "/api/auth/language/",
            {"language": "fr"},
            content_type="application/json",
        )
        assert response.status_code == 403


# ── Change Password ──


class TestChangePassword:
    def test_change_password_success(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/auth/change-password/",
            {"current_password": "securepass123", "new_password": "newpassword456"},
            content_type="application/json",
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password("newpassword456")

    def test_change_password_wrong_current(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/change-password/",
            {"current_password": "wrongpassword", "new_password": "newpassword456"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_change_password_unauthenticated(self, api_client, db):
        response = api_client.post(
            "/api/auth/change-password/",
            {"current_password": "test", "new_password": "newpassword456"},
            content_type="application/json",
        )
        assert response.status_code == 403


# ── Delete Account ──


class TestDeleteAccount:
    def test_delete_account_success(self, authenticated_client, user):
        response = authenticated_client.delete(
            "/api/auth/delete-account/",
            {"email_confirmation": "test@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 204
        assert not User.objects.filter(pk=user.pk).exists()

    def test_delete_account_wrong_email_confirmation(self, authenticated_client, user):
        response = authenticated_client.delete(
            "/api/auth/delete-account/",
            {"email_confirmation": "wrong@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert User.objects.filter(pk=user.pk).exists()

    def test_delete_account_email_confirmation_case_insensitive(self, authenticated_client, user):
        response = authenticated_client.delete(
            "/api/auth/delete-account/",
            {"email_confirmation": "TEST@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 204
        assert not User.objects.filter(pk=user.pk).exists()

    def test_delete_account_missing_confirmation(self, authenticated_client, user):
        response = authenticated_client.delete(
            "/api/auth/delete-account/",
            {},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert User.objects.filter(pk=user.pk).exists()

    def test_delete_account_cascades_related_data(self, authenticated_client, user):
        FavoriteCompany.objects.create(user=user, ticker="PETR4")
        SavedList.objects.create(
            user=user,
            name="My List",
            tickers=["PETR4"],
            share_token=SavedList.generate_share_token(),
        )

        response = authenticated_client.delete(
            "/api/auth/delete-account/",
            {"email_confirmation": "test@example.com"},
            content_type="application/json",
        )

        assert response.status_code == 204
        assert not FavoriteCompany.objects.filter(user_id=user.pk).exists()
        assert not SavedList.objects.filter(user_id=user.pk).exists()

    def test_delete_account_invalidates_session(self, authenticated_client, user):
        authenticated_client.delete(
            "/api/auth/delete-account/",
            {"email_confirmation": "test@example.com"},
            content_type="application/json",
        )

        # Session should be terminated — /me must now return 401
        me_response = authenticated_client.get("/api/auth/me/")
        assert me_response.status_code == 401

    def test_delete_account_unauthenticated(self, api_client, db):
        response = api_client.delete(
            "/api/auth/delete-account/",
            {"email_confirmation": "test@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 403


# ── Change Email ──


class TestChangeEmail:
    def test_change_email_success(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/auth/change-email/",
            {"new_email": "new@example.com", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.email == "new@example.com"
        assert user.username == "new@example.com"
        assert user.email_verified is False

    def test_change_email_wrong_password(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/auth/change-email/",
            {"new_email": "new@example.com", "password": "wrongpassword"},
            content_type="application/json",
        )
        assert response.status_code == 400
        user.refresh_from_db()
        assert user.email == "test@example.com"

    def test_change_email_duplicate_fails(self, authenticated_client, user, db):
        User.objects.create_user(
            username="taken@example.com",
            email="taken@example.com",
            password="pass123456",
        )
        response = authenticated_client.post(
            "/api/auth/change-email/",
            {"new_email": "taken@example.com", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 400
        user.refresh_from_db()
        assert user.email == "test@example.com"

    def test_change_email_same_email_fails(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/auth/change-email/",
            {"new_email": "test@example.com", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_change_email_invalid_email_format(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/auth/change-email/",
            {"new_email": "not-an-email", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_change_email_marks_email_unverified(self, authenticated_client, user):
        user.email_verified = True
        user.save(update_fields=["email_verified"])

        authenticated_client.post(
            "/api/auth/change-email/",
            {"new_email": "new@example.com", "password": "securepass123"},
            content_type="application/json",
        )

        user.refresh_from_db()
        assert user.email_verified is False

    def test_change_email_sends_verification_email_to_new_address(self, authenticated_client, user):
        from django.core import mail

        mail.outbox = []
        authenticated_client.post(
            "/api/auth/change-email/",
            {"new_email": "new@example.com", "password": "securepass123"},
            content_type="application/json",
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["new@example.com"]
        assert EmailVerificationToken.objects.filter(user=user, used=False).exists()

    def test_change_email_invalidates_prior_unused_tokens(self, authenticated_client, user):
        stale_token = EmailVerificationToken.create_for_user(user)

        authenticated_client.post(
            "/api/auth/change-email/",
            {"new_email": "new@example.com", "password": "securepass123"},
            content_type="application/json",
        )

        stale_token.refresh_from_db()
        assert stale_token.used is True

    def test_change_email_unauthenticated(self, api_client, db):
        response = api_client.post(
            "/api/auth/change-email/",
            {"new_email": "new@example.com", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 403


# ── User Preferences ──


class TestUpdatePreferences:
    def test_update_allow_contact_true(self, authenticated_client, user):
        assert user.allow_contact is False
        response = authenticated_client.patch(
            "/api/auth/preferences/",
            {"allow_contact": True},
            content_type="application/json",
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.allow_contact is True

    def test_update_allow_contact_false(self, authenticated_client, user):
        user.allow_contact = True
        user.save(update_fields=["allow_contact"])

        response = authenticated_client.patch(
            "/api/auth/preferences/",
            {"allow_contact": False},
            content_type="application/json",
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.allow_contact is False

    def test_update_preferences_returns_current_state(self, authenticated_client, user):
        response = authenticated_client.patch(
            "/api/auth/preferences/",
            {"allow_contact": True},
            content_type="application/json",
        )
        assert response.json()["allow_contact"] is True

    def test_update_preferences_unauthenticated(self, api_client, db):
        response = api_client.patch(
            "/api/auth/preferences/",
            {"allow_contact": True},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_me_endpoint_exposes_allow_contact(self, authenticated_client, user):
        user.allow_contact = True
        user.save(update_fields=["allow_contact"])

        response = authenticated_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert response.json()["allow_contact"] is True


# ── Forgot Password ──


class TestForgotPassword:
    def test_forgot_password_existing_user_creates_token(self, api_client, user):
        response = api_client.post(
            "/api/auth/forgot-password/",
            {"email": "test@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert PasswordResetToken.objects.filter(user=user).exists()

    def test_forgot_password_nonexistent_user_still_returns_ok(self, api_client, db):
        response = api_client.post(
            "/api/auth/forgot-password/",
            {"email": "nobody@example.com"},
            content_type="application/json",
        )
        # Should not leak whether email exists
        assert response.status_code == 200


# ── Reset Password ──


class TestResetPassword:
    def test_reset_password_success(self, api_client, user):
        token_obj = PasswordResetToken.create_for_user(user)
        response = api_client.post(
            "/api/auth/reset-password/",
            {"token": token_obj.token, "password": "brandnewpass789"},
            content_type="application/json",
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password("brandnewpass789")

    def test_reset_password_marks_token_used(self, api_client, user):
        token_obj = PasswordResetToken.create_for_user(user)
        api_client.post(
            "/api/auth/reset-password/",
            {"token": token_obj.token, "password": "brandnewpass789"},
            content_type="application/json",
        )
        token_obj.refresh_from_db()
        assert token_obj.used is True

    def test_reset_password_used_token_fails(self, api_client, user):
        token_obj = PasswordResetToken.create_for_user(user)
        token_obj.used = True
        token_obj.save()

        response = api_client.post(
            "/api/auth/reset-password/",
            {"token": token_obj.token, "password": "brandnewpass789"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_reset_password_invalid_token(self, api_client, db):
        response = api_client.post(
            "/api/auth/reset-password/",
            {"token": "invalid-token-xyz", "password": "brandnewpass789"},
            content_type="application/json",
        )
        assert response.status_code == 400


# ── Favorites ──


class TestFavorites:
    def test_list_favorites_empty(self, authenticated_client):
        response = authenticated_client.get("/api/auth/favorites/")
        assert response.status_code == 200
        assert response.json() == []

    def test_add_favorite(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["ticker"] == "PETR4"

    def test_add_favorite_normalizes_to_uppercase(self, authenticated_client):
        authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "petr4"},
            content_type="application/json",
        )
        response = authenticated_client.get("/api/auth/favorites/")
        assert response.json()[0]["ticker"] == "PETR4"

    def test_add_duplicate_favorite_returns_conflict(self, authenticated_client):
        authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        assert response.status_code == 409

    def test_remove_favorite(self, authenticated_client, user):
        FavoriteCompany.objects.create(user=user, ticker="VALE3")
        response = authenticated_client.delete("/api/auth/favorites/VALE3/")
        assert response.status_code == 204
        assert not FavoriteCompany.objects.filter(user=user, ticker="VALE3").exists()

    def test_remove_nonexistent_favorite(self, authenticated_client):
        response = authenticated_client.delete("/api/auth/favorites/XXXX0/")
        assert response.status_code == 404

    def test_favorites_require_auth(self, api_client, db):
        response = api_client.get("/api/auth/favorites/")
        assert response.status_code == 403

    def test_list_favorites_returns_all(self, authenticated_client, user):
        FavoriteCompany.objects.create(user=user, ticker="PETR4")
        FavoriteCompany.objects.create(user=user, ticker="VALE3")
        response = authenticated_client.get("/api/auth/favorites/")
        tickers = [entry["ticker"] for entry in response.json()]
        assert "PETR4" in tickers
        assert "VALE3" in tickers

    def test_favorite_limit_enforced_for_unverified_user(self, authenticated_client, user):
        assert user.email_verified is False
        for i in range(20):
            FavoriteCompany.objects.create(user=user, ticker=f"TST{i}")
        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "ONEMORE"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "Limite" in response.json()["error"]

    def test_verified_user_bypasses_favorite_limit(self, authenticated_client, user):
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        for i in range(20):
            FavoriteCompany.objects.create(user=user, ticker=f"TST{i}")
        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "EXTRA1"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert FavoriteCompany.objects.filter(user=user).count() == 21

    def test_favorite_at_limit_can_still_remove(self, authenticated_client, user):
        for i in range(20):
            FavoriteCompany.objects.create(user=user, ticker=f"TST{i}")
        response = authenticated_client.delete("/api/auth/favorites/TST0/")
        assert response.status_code == 204


# ── Saved Lists ──


class TestSavedLists:
    def test_list_empty(self, authenticated_client):
        response = authenticated_client.get("/api/auth/lists/")
        assert response.status_code == 200
        assert response.json() == []

    def test_save_list(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/lists/",
            {"name": "My list", "tickers": ["PETR4", "VALE3"], "years": 5},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My list"
        assert data["tickers"] == ["PETR4", "VALE3"]
        assert data["years"] == 5
        assert "share_token" in data

    def test_delete_list(self, authenticated_client, user):
        saved_list = SavedList.objects.create(
            user=user,
            name="Test",
            tickers=["PETR4"],
            share_token=SavedList.generate_share_token(),
        )
        response = authenticated_client.delete(f"/api/auth/lists/{saved_list.pk}/")
        assert response.status_code == 204

    def test_shared_list_public_access(self, api_client, user):
        saved_list = SavedList.objects.create(
            user=user,
            name="Shared test",
            tickers=["PETR4", "VALE3", "ITUB4"],
            years=7,
            share_token="test-share-token-123",
        )
        response = api_client.get(f"/api/auth/lists/shared/{saved_list.share_token}/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Shared test"
        assert data["tickers"] == ["PETR4", "VALE3", "ITUB4"]
        assert data["years"] == 7
        assert data["shared_by"] == "test@example.com"

    def test_shared_list_invalid_token(self, api_client, db):
        response = api_client.get("/api/auth/lists/shared/nonexistent/")
        assert response.status_code == 404

    def test_lists_require_auth(self, api_client, db):
        response = api_client.get("/api/auth/lists/")
        assert response.status_code == 403

    def test_update_list_tickers(self, authenticated_client, user):
        saved_list = SavedList.objects.create(
            user=user,
            name="Original",
            tickers=["PETR4", "VALE3"],
            years=10,
            share_token=SavedList.generate_share_token(),
        )
        response = authenticated_client.put(
            f"/api/auth/lists/{saved_list.pk}/",
            {"tickers": ["PETR4", "VALE3", "ITUB4"]},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tickers"] == ["PETR4", "VALE3", "ITUB4"]
        assert data["name"] == "Original"

    def test_update_list_years(self, authenticated_client, user):
        saved_list = SavedList.objects.create(
            user=user,
            name="Original",
            tickers=["PETR4"],
            years=10,
            share_token=SavedList.generate_share_token(),
        )
        response = authenticated_client.put(
            f"/api/auth/lists/{saved_list.pk}/",
            {"years": 5},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["years"] == 5

    def test_update_list_name(self, authenticated_client, user):
        saved_list = SavedList.objects.create(
            user=user,
            name="Original",
            tickers=["PETR4"],
            share_token=SavedList.generate_share_token(),
        )
        response = authenticated_client.put(
            f"/api/auth/lists/{saved_list.pk}/",
            {"name": "Renamed"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"

    def test_update_nonexistent_list_returns_404(self, authenticated_client):
        response = authenticated_client.put(
            "/api/auth/lists/99999/",
            {"name": "Ghost"},
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_update_list_requires_auth(self, api_client, db):
        response = api_client.put(
            "/api/auth/lists/1/",
            {"name": "Hack"},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_cannot_update_other_users_list(self, api_client, user):
        other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="otherpass123",
        )
        saved_list = SavedList.objects.create(
            user=other_user,
            name="Their list",
            tickers=["PETR4"],
            share_token=SavedList.generate_share_token(),
        )
        # Login as test user
        api_client.login(username="test@example.com", password="securepass123")
        response = api_client.put(
            f"/api/auth/lists/{saved_list.pk}/",
            {"name": "Stolen"},
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_delete_nonexistent_list_returns_404(self, authenticated_client):
        response = authenticated_client.delete("/api/auth/lists/99999/")
        assert response.status_code == 404

    def test_save_list_assigns_display_order(self, authenticated_client):
        authenticated_client.post(
            "/api/auth/lists/",
            {"name": "First", "tickers": ["PETR4"], "years": 10},
            content_type="application/json",
        )
        authenticated_client.post(
            "/api/auth/lists/",
            {"name": "Second", "tickers": ["VALE3"], "years": 5},
            content_type="application/json",
        )
        response = authenticated_client.get("/api/auth/lists/")
        lists = response.json()
        assert len(lists) == 2
        # Both should have display_order field
        for saved_list in lists:
            assert "display_order" in saved_list

    def test_reorder_lists(self, authenticated_client, user):
        list_a = SavedList.objects.create(
            user=user, name="A", tickers=["PETR4"],
            display_order=0, share_token=SavedList.generate_share_token(),
        )
        list_b = SavedList.objects.create(
            user=user, name="B", tickers=["VALE3"],
            display_order=1, share_token=SavedList.generate_share_token(),
        )
        list_c = SavedList.objects.create(
            user=user, name="C", tickers=["ITUB4"],
            display_order=2, share_token=SavedList.generate_share_token(),
        )

        # Reorder: C, A, B
        response = authenticated_client.post(
            "/api/auth/lists/reorder/",
            {"ordered_ids": [list_c.id, list_a.id, list_b.id]},
            content_type="application/json",
        )
        assert response.status_code == 200

        # Verify order
        list_a.refresh_from_db()
        list_b.refresh_from_db()
        list_c.refresh_from_db()
        assert list_c.display_order == 0
        assert list_a.display_order == 1
        assert list_b.display_order == 2

    def test_reorder_requires_auth(self, api_client, db):
        response = api_client.post(
            "/api/auth/lists/reorder/",
            {"ordered_ids": [1, 2]},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_reorder_ignores_other_users_lists(self, authenticated_client, user):
        other_user = User.objects.create_user(
            username="other2@example.com",
            email="other2@example.com",
            password="otherpass",
        )
        other_list = SavedList.objects.create(
            user=other_user, name="Other", tickers=["PETR4"],
            display_order=0, share_token=SavedList.generate_share_token(),
        )
        my_list = SavedList.objects.create(
            user=user, name="Mine", tickers=["VALE3"],
            display_order=0, share_token=SavedList.generate_share_token(),
        )

        # Try to reorder including the other user's list
        response = authenticated_client.post(
            "/api/auth/lists/reorder/",
            {"ordered_ids": [other_list.id, my_list.id]},
            content_type="application/json",
        )
        assert response.status_code == 200

        # Other user's list should be unchanged
        other_list.refresh_from_db()
        assert other_list.display_order == 0

        # My list should be updated
        my_list.refresh_from_db()
        assert my_list.display_order == 1

    def test_list_preserves_share_token_on_update(self, authenticated_client, user):
        saved_list = SavedList.objects.create(
            user=user,
            name="Original",
            tickers=["PETR4"],
            share_token="original-token-abc",
        )
        response = authenticated_client.put(
            f"/api/auth/lists/{saved_list.pk}/",
            {"tickers": ["VALE3"]},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["share_token"] == "original-token-abc"

    def test_rename_preserves_tickers_and_years(self, authenticated_client, user):
        saved_list = SavedList.objects.create(
            user=user,
            name="Before rename",
            tickers=["PETR4", "VALE3"],
            years=7,
            share_token=SavedList.generate_share_token(),
        )
        response = authenticated_client.put(
            f"/api/auth/lists/{saved_list.pk}/",
            {"name": "After rename"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "After rename"
        assert data["tickers"] == ["PETR4", "VALE3"]
        assert data["years"] == 7

    def test_duplicate_creates_separate_list(self, authenticated_client, user):
        original = SavedList.objects.create(
            user=user,
            name="Original",
            tickers=["PETR4", "VALE3"],
            years=10,
            share_token=SavedList.generate_share_token(),
        )
        # Duplicate by creating a new list with same tickers
        response = authenticated_client.post(
            "/api/auth/lists/",
            {"name": "Original (cópia)", "tickers": ["PETR4", "VALE3"], "years": 10},
            content_type="application/json",
        )
        assert response.status_code == 201
        duplicate = response.json()
        assert duplicate["name"] == "Original (cópia)"
        assert duplicate["id"] != original.id
        assert duplicate["share_token"] != original.share_token

        # Both should exist
        response = authenticated_client.get("/api/auth/lists/")
        assert len(response.json()) == 2

    def test_delete_after_rename(self, authenticated_client, user):
        saved_list = SavedList.objects.create(
            user=user,
            name="Will be renamed then deleted",
            tickers=["PETR4"],
            share_token=SavedList.generate_share_token(),
        )
        # Rename
        authenticated_client.put(
            f"/api/auth/lists/{saved_list.pk}/",
            {"name": "Renamed"},
            content_type="application/json",
        )
        # Delete
        response = authenticated_client.delete(f"/api/auth/lists/{saved_list.pk}/")
        assert response.status_code == 204
        assert not SavedList.objects.filter(pk=saved_list.pk).exists()

    def test_cannot_delete_other_users_list(self, api_client, user):
        other_user = User.objects.create_user(
            username="other3@example.com",
            email="other3@example.com",
            password="otherpass",
        )
        other_list = SavedList.objects.create(
            user=other_user,
            name="Not yours",
            tickers=["PETR4"],
            share_token=SavedList.generate_share_token(),
        )
        api_client.login(username="test@example.com", password="securepass123")
        response = api_client.delete(f"/api/auth/lists/{other_list.pk}/")
        assert response.status_code == 404
        assert SavedList.objects.filter(pk=other_list.pk).exists()

    def test_response_includes_display_order(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/lists/",
            {"name": "With order", "tickers": ["PETR4"], "years": 10},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert "display_order" in response.json()

    def test_lists_returned_in_display_order(self, authenticated_client, user):
        SavedList.objects.create(
            user=user, name="Third", tickers=["ITUB4"],
            display_order=2, share_token=SavedList.generate_share_token(),
        )
        SavedList.objects.create(
            user=user, name="First", tickers=["PETR4"],
            display_order=0, share_token=SavedList.generate_share_token(),
        )
        SavedList.objects.create(
            user=user, name="Second", tickers=["VALE3"],
            display_order=1, share_token=SavedList.generate_share_token(),
        )
        response = authenticated_client.get("/api/auth/lists/")
        names = [entry["name"] for entry in response.json()]
        assert names == ["First", "Second", "Third"]


# ── Saved screener filters ──


class TestSavedScreenerFilters:
    def test_list_empty(self, authenticated_client):
        response = authenticated_client.get("/api/auth/screener-filters/")
        assert response.status_code == 200
        assert response.json() == []

    def test_save_filter(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/screener-filters/",
            {
                "name": "Low PE",
                "bounds": {"pe10": {"min": "0", "max": "15"}},
                "sort": "-market_cap",
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Low PE"
        assert data["bounds"] == {"pe10": {"min": "0", "max": "15"}}
        assert data["sort"] == "-market_cap"
        assert "id" in data

    def test_save_filter_defaults_sort(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/screener-filters/",
            {"name": "Minimal", "bounds": {}},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["sort"] == "-market_cap"

    def test_list_filters_returns_user_filters(self, authenticated_client, user):
        SavedScreenerFilter.objects.create(
            user=user,
            name="Alpha",
            bounds={"pe10": {"max": "20"}},
            sort="market_cap",
        )
        SavedScreenerFilter.objects.create(
            user=user,
            name="Beta",
            bounds={"peg": {"max": "1"}},
            sort="-pe10",
        )
        response = authenticated_client.get("/api/auth/screener-filters/")
        assert response.status_code == 200
        names = {entry["name"] for entry in response.json()}
        assert names == {"Alpha", "Beta"}

    def test_update_filter_name(self, authenticated_client, user):
        saved = SavedScreenerFilter.objects.create(
            user=user, name="Original", bounds={}, sort="-market_cap",
        )
        response = authenticated_client.put(
            f"/api/auth/screener-filters/{saved.pk}/",
            {"name": "Renamed"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"

    def test_update_filter_bounds_and_sort(self, authenticated_client, user):
        saved = SavedScreenerFilter.objects.create(
            user=user, name="X", bounds={}, sort="-market_cap",
        )
        response = authenticated_client.put(
            f"/api/auth/screener-filters/{saved.pk}/",
            {"bounds": {"pe10": {"max": "10"}}, "sort": "-pe10"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bounds"] == {"pe10": {"max": "10"}}
        assert data["sort"] == "-pe10"

    def test_delete_filter(self, authenticated_client, user):
        saved = SavedScreenerFilter.objects.create(
            user=user, name="Temp", bounds={}, sort="-market_cap",
        )
        response = authenticated_client.delete(
            f"/api/auth/screener-filters/{saved.pk}/",
        )
        assert response.status_code == 204
        assert not SavedScreenerFilter.objects.filter(pk=saved.pk).exists()

    def test_filters_require_auth(self, api_client, db):
        response = api_client.get("/api/auth/screener-filters/")
        assert response.status_code == 403

    def test_cannot_update_other_users_filter(self, api_client, user):
        other = User.objects.create_user(
            username="otherf@example.com",
            email="otherf@example.com",
            password="otherpass",
        )
        saved = SavedScreenerFilter.objects.create(
            user=other, name="Theirs", bounds={}, sort="-market_cap",
        )
        api_client.login(username="test@example.com", password="securepass123")
        response = api_client.put(
            f"/api/auth/screener-filters/{saved.pk}/",
            {"name": "Hijack"},
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_cannot_delete_other_users_filter(self, api_client, user):
        other = User.objects.create_user(
            username="otherfd@example.com",
            email="otherfd@example.com",
            password="otherpass",
        )
        saved = SavedScreenerFilter.objects.create(
            user=other, name="Theirs", bounds={}, sort="-market_cap",
        )
        api_client.login(username="test@example.com", password="securepass123")
        response = api_client.delete(f"/api/auth/screener-filters/{saved.pk}/")
        assert response.status_code == 404
        assert SavedScreenerFilter.objects.filter(pk=saved.pk).exists()

    def test_rejects_invalid_sort_field(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/screener-filters/",
            {"name": "Bad", "bounds": {}, "sort": "wat_is_this"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_rejects_unknown_indicator_in_bounds(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/screener-filters/",
            {"name": "Bad", "bounds": {"not_a_field": {"min": "1"}}, "sort": "-market_cap"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_rejects_market_cap_in_bounds(self, authenticated_client):
        """market_cap is sortable (default ranking) but not filterable."""
        response = authenticated_client.post(
            "/api/auth/screener-filters/",
            {"name": "Bad", "bounds": {"market_cap": {"min": "1"}}, "sort": "-market_cap"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_update_nonexistent_returns_404(self, authenticated_client):
        response = authenticated_client.put(
            "/api/auth/screener-filters/99999/",
            {"name": "Ghost"},
            content_type="application/json",
        )
        assert response.status_code == 404


# ── Me endpoint ──


class TestMeEndpoint:
    def test_me_returns_date_joined(self, authenticated_client, user):
        response = authenticated_client.get("/api/auth/me/")
        assert response.status_code == 200
        data = response.json()
        assert "date_joined" in data
        assert data["email"] == "test@example.com"

    def test_me_returns_is_superuser_false(self, authenticated_client):
        response = authenticated_client.get("/api/auth/me/")
        assert response.json()["is_superuser"] is False

    def test_me_sets_csrf_cookie(self, authenticated_client):
        response = authenticated_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert "csrftoken" in response.cookies


# ── Feedback ──


class TestFeedback:
    def test_send_feedback_success(self, api_client, db):
        response = api_client.post(
            "/api/auth/feedback/",
            {"email": "user@example.com", "message": "Great tool!", "human_check": 7},
            content_type="application/json",
        )
        assert response.status_code == 201

    def test_send_feedback_wrong_human_check(self, api_client, db):
        response = api_client.post(
            "/api/auth/feedback/",
            {"email": "user@example.com", "message": "Spam", "human_check": 99},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_send_feedback_missing_fields(self, api_client, db):
        response = api_client.post(
            "/api/auth/feedback/",
            {"email": "user@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 400


# ── Password Reset Token Model ──


class TestPasswordResetTokenModel:
    def test_create_for_user(self, user):
        token_obj = PasswordResetToken.create_for_user(user)
        assert token_obj.token
        assert len(token_obj.token) > 20
        assert token_obj.user == user
        assert token_obj.is_valid

    def test_used_token_is_not_valid(self, user):
        token_obj = PasswordResetToken.create_for_user(user)
        token_obj.used = True
        token_obj.save()
        assert not token_obj.is_valid


# ── Saved List Model ──


class TestSavedListModel:
    def test_generate_share_token(self):
        token = SavedList.generate_share_token()
        assert len(token) > 10
        # Each call should generate a unique token
        assert token != SavedList.generate_share_token()


# ── Page View Model ──


class TestPageViewModel:
    def test_hash_ip_is_deterministic(self):
        hash_one = PageView.hash_ip("192.168.1.1")
        hash_two = PageView.hash_ip("192.168.1.1")
        assert hash_one == hash_two

    def test_hash_ip_differs_for_different_ips(self):
        hash_one = PageView.hash_ip("192.168.1.1")
        hash_two = PageView.hash_ip("192.168.1.2")
        assert hash_one != hash_two

    def test_hash_ip_returns_64_char_hex(self):
        ip_hash = PageView.hash_ip("10.0.0.1")
        assert len(ip_hash) == 64
        assert all(character in "0123456789abcdef" for character in ip_hash)

    def test_create_page_view(self, user):
        view = PageView.objects.create(
            path="/PETR4",
            ip_hash=PageView.hash_ip("127.0.0.1"),
            user=user,
        )
        assert view.pk is not None
        assert view.path == "/PETR4"


# ── Page View Tracking Endpoint ──


class TestTrackPageView:
    def test_track_page_view(self, api_client, db):
        response = api_client.post(
            "/api/auth/track/",
            {"path": "/PETR4"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert PageView.objects.filter(path="/PETR4").count() == 1

    def test_track_page_view_with_authenticated_user(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/auth/track/",
            {"path": "/VALE3"},
            content_type="application/json",
        )
        assert response.status_code == 201
        page_view = PageView.objects.get(path="/VALE3")
        assert page_view.user == user

    def test_track_page_view_without_path_fails(self, api_client, db):
        response = api_client.post(
            "/api/auth/track/",
            {},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_track_page_view_hashes_ip(self, api_client, db):
        api_client.post(
            "/api/auth/track/",
            {"path": "/"},
            content_type="application/json",
        )
        page_view = PageView.objects.get(path="/")
        assert len(page_view.ip_hash) == 64
        assert page_view.ip_hash != "127.0.0.1"

    def test_multiple_views_same_path(self, api_client, db):
        api_client.post("/api/auth/track/", {"path": "/"}, content_type="application/json")
        api_client.post("/api/auth/track/", {"path": "/"}, content_type="application/json")
        assert PageView.objects.filter(path="/").count() == 2


# ── Admin Dashboard ──


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="admin@example.com",
        email="admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def superuser_client(api_client, superuser):
    api_client.login(username="admin@example.com", password="adminpass123")
    return api_client


class TestAdminDashboard:
    def test_superuser_can_access_dashboard(self, superuser_client):
        response = superuser_client.get("/api/auth/admin/dashboard/")
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "page_views" in data
        assert "top_pages" in data
        assert "top_tickers" in data
        assert "signup_stats" in data
        assert "favorites_count" in data
        assert "saved_lists_count" in data

    def test_regular_user_cannot_access_dashboard(self, authenticated_client):
        response = authenticated_client.get("/api/auth/admin/dashboard/")
        assert response.status_code == 403

    def test_anonymous_user_cannot_access_dashboard(self, api_client, db):
        response = api_client.get("/api/auth/admin/dashboard/")
        assert response.status_code == 403

    def test_dashboard_returns_user_list(self, superuser_client, user):
        response = superuser_client.get("/api/auth/admin/dashboard/")
        data = response.json()
        emails = [user_entry["email"] for user_entry in data["users"]]
        assert "test@example.com" in emails
        assert "admin@example.com" in emails

    def test_dashboard_returns_page_view_stats(self, superuser_client):
        # Create some page views
        PageView.objects.create(path="/", ip_hash=PageView.hash_ip("1.1.1.1"))
        PageView.objects.create(path="/PETR4", ip_hash=PageView.hash_ip("1.1.1.1"))
        PageView.objects.create(path="/VALE3", ip_hash=PageView.hash_ip("2.2.2.2"))

        response = superuser_client.get("/api/auth/admin/dashboard/")
        data = response.json()

        day_stats = data["page_views"]["day"]
        assert day_stats["total_views"] >= 3
        assert day_stats["unique_visitors"] >= 2

    def test_dashboard_returns_signup_stats(self, superuser_client, user):
        response = superuser_client.get("/api/auth/admin/dashboard/")
        data = response.json()
        assert data["signup_stats"]["total"] >= 2  # superuser + regular user

    def test_dashboard_user_entries_have_visits_count(self, superuser_client, user):
        CompanyVisit.objects.create(user=user, ticker="PETR4")
        CompanyVisit.objects.create(user=user, ticker="VALE3")

        response = superuser_client.get("/api/auth/admin/dashboard/")
        test_user = next(
            entry for entry in response.json()["users"]
            if entry["email"] == "test@example.com"
        )
        assert test_user["visits_count"] == 2

    def test_dashboard_top_pages_returns_top_ten_only(self, superuser_client):
        for index in range(15):
            for _ in range(index + 1):
                PageView.objects.create(path=f"/page-{index}", ip_hash="a")

        response = superuser_client.get("/api/auth/admin/dashboard/")
        assert len(response.json()["top_pages"]) == 10

    def test_admin_top_pages_endpoint_returns_all_pages(self, superuser_client):
        for index in range(25):
            PageView.objects.create(path=f"/page-{index}", ip_hash="a")

        response = superuser_client.get("/api/auth/admin/top-pages/")
        assert response.status_code == 200
        assert len(response.json()["pages"]) >= 25

    def test_admin_top_pages_endpoint_requires_superuser(self, authenticated_client):
        response = authenticated_client.get("/api/auth/admin/top-pages/")
        assert response.status_code == 403

    def test_dashboard_user_entries_have_visit_counts(self, superuser_client, user):
        PageView.objects.create(
            path="/PETR4",
            ip_hash=PageView.hash_ip("1.1.1.1"),
            user=user,
        )
        response = superuser_client.get("/api/auth/admin/dashboard/")
        data = response.json()

        test_user = next(
            entry for entry in data["users"] if entry["email"] == "test@example.com"
        )
        assert test_user["page_views"]["day"] >= 1
        assert "lookups" in test_user
        assert "favorites_count" in test_user

    def test_user_view_counts_not_inflated_by_cross_product(self, superuser_client, user):
        """Multiple annotations must use distinct=True to avoid cartesian product.

        Without distinct=True, a user with 2 page views and 3 lookups would
        show 6 page views (2 × 3) instead of the correct 2.
        """
        PageView.objects.create(path="/PETR4", ip_hash="a", user=user)
        PageView.objects.create(path="/VALE3", ip_hash="a", user=user)
        LookupLog.objects.create(user=user, ticker="PETR4")
        LookupLog.objects.create(user=user, ticker="VALE3")
        LookupLog.objects.create(user=user, ticker="WEGE3")

        response = superuser_client.get("/api/auth/admin/dashboard/")
        test_user = next(
            entry for entry in response.json()["users"]
            if entry["email"] == "test@example.com"
        )
        # Without distinct=True these would be 6 and 6 (cross product)
        assert test_user["page_views"]["day"] == 2
        assert test_user["lookups"]["day"] == 3

    def test_dashboard_uses_bounded_query_count(self, superuser_client, user):
        """The dashboard must not scale queries with the number of periods.

        Before optimization: 25+ queries (separate COUNT per period per metric).
        After optimization: should be under 15 total queries.
        """
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        PageView.objects.create(path="/", ip_hash="aaa", user=user)
        PageView.objects.create(path="/PETR4", ip_hash="bbb")
        LookupLog.objects.create(user=user, ticker="PETR4")

        with CaptureQueriesContext(connection) as context:
            response = superuser_client.get("/api/auth/admin/dashboard/")

        assert response.status_code == 200
        query_count = len(context)
        # Allow some overhead for auth/session, but the core dashboard
        # queries must be consolidated. 15 is generous; before fix it was 25+.
        assert query_count <= 15, (
            f"Dashboard used {query_count} queries, expected <= 15. "
            f"Queries: {[q['sql'][:80] for q in context]}"
        )

    def test_me_returns_is_superuser_true_for_admin(self, superuser_client):
        response = superuser_client.get("/api/auth/me/")
        assert response.json()["is_superuser"] is True

    def test_me_returns_is_superuser_false_for_regular_user(self, authenticated_client):
        response = authenticated_client.get("/api/auth/me/")
        assert response.json()["is_superuser"] is False

    def test_me_returns_email_verified(self, authenticated_client):
        response = authenticated_client.get("/api/auth/me/")
        assert response.json()["email_verified"] is False


# ── Email Verification ──


class TestEmailVerification:
    def test_signup_sends_verification_email(self, api_client, db):
        from django.core import mail

        api_client.post(
            "/api/auth/signup/",
            {"email": "verify@example.com", "password": "testpass123", "language": "pt"},
            content_type="application/json",
        )
        # Should have 2 emails: welcome + verification
        assert len(mail.outbox) == 2
        verification_email = mail.outbox[1]
        assert "Confirme seu email" in verification_email.subject
        assert "verify-email?token=" in verification_email.body

    def test_verify_email_success(self, api_client, user):
        token_obj = EmailVerificationToken.create_for_user(user)
        response = api_client.post(
            "/api/auth/verify-email/",
            {"token": token_obj.token},
            content_type="application/json",
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.email_verified is True

    def test_verify_email_marks_token_used(self, api_client, user):
        token_obj = EmailVerificationToken.create_for_user(user)
        api_client.post(
            "/api/auth/verify-email/",
            {"token": token_obj.token},
            content_type="application/json",
        )
        token_obj.refresh_from_db()
        assert token_obj.used is True

    def test_verify_email_invalid_token(self, api_client, db):
        response = api_client.post(
            "/api/auth/verify-email/",
            {"token": "invalid-token-xyz"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_verify_email_used_token(self, api_client, user):
        token_obj = EmailVerificationToken.create_for_user(user)
        token_obj.used = True
        token_obj.save()
        response = api_client.post(
            "/api/auth/verify-email/",
            {"token": token_obj.token},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_resend_verification(self, authenticated_client, db):
        from django.core import mail

        response = authenticated_client.post("/api/auth/resend-verification/")
        assert response.status_code == 200
        assert len(mail.outbox) == 1
        assert "Confirm" in mail.outbox[0].subject

    def test_resend_verification_already_verified(self, authenticated_client, user):
        user.email_verified = True
        user.save()
        response = authenticated_client.post("/api/auth/resend-verification/")
        assert response.status_code == 400

    def test_resend_verification_requires_auth(self, api_client, db):
        response = api_client.post("/api/auth/resend-verification/")
        assert response.status_code == 403


# ── Operation Limits ──


class TestOperationLimits:
    def test_unverified_user_can_perform_operations(self, authenticated_client, user):
        """Unverified user should be able to favorite within daily limit."""
        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        assert response.status_code == 201

    def test_daily_limit_enforced(self, authenticated_client, user):
        """After 14 operations today, should be blocked."""
        for i in range(14):
            UserOperation.record(user, "favorite")

        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "NEWONE"},
            content_type="application/json",
        )
        assert response.status_code == 403
        assert "Limite" in response.json()["error"]

    def test_verified_user_ignores_daily_limit(self, authenticated_client, user):
        """Verified users have no daily limit."""
        user.email_verified = True
        user.save()

        for i in range(14):
            UserOperation.record(user, "favorite")

        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "UNLIMITED"},
            content_type="application/json",
        )
        assert response.status_code == 201

    def test_verification_required_after_five_active_days(self, authenticated_client, user):
        """After 5 distinct days with operations, must verify email."""
        from datetime import timedelta
        now = timezone.now()
        for day_offset in range(5):
            op = UserOperation.objects.create(user=user, operation="favorite")
            UserOperation.objects.filter(pk=op.pk).update(
                created_at=now - timedelta(days=day_offset)
            )

        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "BLOCKED"},
            content_type="application/json",
        )
        assert response.status_code == 403
        assert "Verifique" in response.json()["error"]
        assert response.json()["verification_required"] is True

    def test_verified_user_ignores_active_days_limit(self, authenticated_client, user):
        """Verified users are not affected by the 5-day rule."""
        user.email_verified = True
        user.save()

        from datetime import timedelta
        now = timezone.now()
        for day_offset in range(5):
            op = UserOperation.objects.create(user=user, operation="favorite")
            UserOperation.objects.filter(pk=op.pk).update(
                created_at=now - timedelta(days=day_offset)
            )

        response = authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "ALLOWED"},
            content_type="application/json",
        )
        assert response.status_code == 201

    def test_operations_recorded_on_favorite(self, authenticated_client, user):
        authenticated_client.post(
            "/api/auth/favorites/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        assert UserOperation.objects.filter(user=user, operation="favorite").count() == 1

    def test_operations_recorded_on_save_list(self, authenticated_client, user):
        authenticated_client.post(
            "/api/auth/lists/",
            {"name": "Test", "tickers": ["PETR4"], "years": 10},
            content_type="application/json",
        )
        assert UserOperation.objects.filter(user=user, operation="save_list").count() == 1

    def test_operations_recorded_on_delete_list(self, authenticated_client, user):
        saved_list = SavedList.objects.create(
            user=user, name="Del", tickers=["PETR4"],
            share_token=SavedList.generate_share_token(),
        )
        authenticated_client.delete(f"/api/auth/lists/{saved_list.pk}/")
        assert UserOperation.objects.filter(user=user, operation="delete_list").count() == 1
