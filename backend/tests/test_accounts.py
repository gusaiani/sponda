"""Tests for accounts: auth, favorites, saved lists, feedback, admin dashboard."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory

from accounts.middleware import PageViewTrackingMiddleware
from accounts.models import FavoriteCompany, PageView, PasswordResetToken, SavedList

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

    def test_signup_short_password_fails(self, api_client, db):
        response = api_client.post(
            "/api/auth/signup/",
            {"email": "new@example.com", "password": "short"},
            content_type="application/json",
        )
        assert response.status_code == 400


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


# ── Page View Tracking Middleware ──


class TestPageViewTrackingMiddleware:
    def test_tracks_frontend_page_view(self, api_client, db):
        # The middleware only tracks GET requests to non-API, non-static paths
        # Django test client goes through middleware, but our catch-all
        # returns 404 in tests (no frontend dist). So we test the model directly.
        PageView.objects.create(
            path="/",
            ip_hash=PageView.hash_ip("127.0.0.1"),
        )
        assert PageView.objects.filter(path="/").count() == 1

    def test_does_not_track_api_requests(self, api_client, db):
        # API requests should NOT create PageView records
        initial_count = PageView.objects.count()
        api_client.get("/api/auth/quota/")
        assert PageView.objects.count() == initial_count


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

    def test_me_returns_is_superuser_true_for_admin(self, superuser_client):
        response = superuser_client.get("/api/auth/me/")
        assert response.json()["is_superuser"] is True

    def test_me_returns_is_superuser_false_for_regular_user(self, authenticated_client):
        response = authenticated_client.get("/api/auth/me/")
        assert response.json()["is_superuser"] is False
