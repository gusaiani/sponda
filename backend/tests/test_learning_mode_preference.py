"""Tests for the ``learning_mode_enabled`` user preference.

Available to every authenticated user. Anonymous visitors persist the
preference client-side via localStorage; the backend endpoint requires
auth as usual.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        username="regular@example.com",
        email="regular@example.com",
        password="securepass123",
    )


@pytest.fixture
def super_user(db):
    return User.objects.create_user(
        username="admin@example.com",
        email="admin@example.com",
        password="securepass123",
        is_superuser=True,
        is_staff=True,
    )


@pytest.fixture
def regular_client(api_client, regular_user):
    api_client.login(username="regular@example.com", password="securepass123")
    return api_client


@pytest.fixture
def super_client(api_client, super_user):
    api_client.login(username="admin@example.com", password="securepass123")
    return api_client


@pytest.mark.django_db
class TestLearningModePreferenceWrite:
    def test_superuser_can_enable_learning_mode(self, super_client, super_user):
        response = super_client.patch(
            "/api/auth/preferences/",
            {"learning_mode_enabled": True},
            content_type="application/json",
        )
        assert response.status_code == 200
        super_user.refresh_from_db()
        assert super_user.learning_mode_enabled is True

    def test_regular_user_can_enable_learning_mode(self, regular_client, regular_user):
        response = regular_client.patch(
            "/api/auth/preferences/",
            {"learning_mode_enabled": True},
            content_type="application/json",
        )
        assert response.status_code == 200
        regular_user.refresh_from_db()
        assert regular_user.learning_mode_enabled is True

    def test_regular_user_can_disable_learning_mode(self, regular_client, regular_user):
        regular_user.learning_mode_enabled = True
        regular_user.save(update_fields=["learning_mode_enabled"])

        response = regular_client.patch(
            "/api/auth/preferences/",
            {"learning_mode_enabled": False},
            content_type="application/json",
        )
        assert response.status_code == 200
        regular_user.refresh_from_db()
        assert regular_user.learning_mode_enabled is False

    def test_unauthenticated_cannot_set_learning_mode(self, api_client, db):
        response = api_client.patch(
            "/api/auth/preferences/",
            {"learning_mode_enabled": True},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_existing_allow_contact_path_still_works(self, regular_client, regular_user):
        response = regular_client.patch(
            "/api/auth/preferences/",
            {"allow_contact": True},
            content_type="application/json",
        )
        assert response.status_code == 200
        regular_user.refresh_from_db()
        assert regular_user.allow_contact is True


@pytest.mark.django_db
class TestLearningModePreferenceMeView:
    def test_superuser_me_includes_learning_mode_enabled(self, super_client, super_user):
        super_user.learning_mode_enabled = True
        super_user.save(update_fields=["learning_mode_enabled"])

        response = super_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert response.json().get("learning_mode_enabled") is True

    def test_regular_user_me_includes_learning_mode_enabled(self, regular_client, regular_user):
        regular_user.learning_mode_enabled = True
        regular_user.save(update_fields=["learning_mode_enabled"])

        response = regular_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert response.json().get("learning_mode_enabled") is True
