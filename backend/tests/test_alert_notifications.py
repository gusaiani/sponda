"""Tests for alert notification endpoints: list, dismiss, dismiss-all."""
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from accounts.models import AlertNotification

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


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        password="otherpass456",
    )


def _create_notification(user, ticker="PETR4", indicator="pe10", **kwargs):
    defaults = {
        "comparison": "lte",
        "threshold": Decimal("10"),
        "indicator_value": Decimal("6.5"),
    }
    defaults.update(kwargs)
    return AlertNotification.objects.create(
        user=user, ticker=ticker, indicator=indicator, **defaults,
    )


@pytest.mark.django_db
class TestAlertNotificationList:
    def test_lists_undismissed_notifications(self, authenticated_client, user):
        _create_notification(user, ticker="PETR4")
        _create_notification(user, ticker="VALE3")
        _create_notification(user, ticker="OLD1", dismissed_at=timezone.now())
        response = authenticated_client.get("/api/auth/alert-notifications/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        tickers = [notification["ticker"] for notification in data["notifications"]]
        assert "PETR4" in tickers
        assert "VALE3" in tickers
        assert "OLD1" not in tickers

    def test_unauthenticated_returns_403(self, api_client):
        response = api_client.get("/api/auth/alert-notifications/")
        assert response.status_code == 403

    def test_does_not_show_other_users_notifications(
        self, authenticated_client, user, other_user,
    ):
        _create_notification(user, ticker="PETR4")
        _create_notification(other_user, ticker="VALE3")
        response = authenticated_client.get("/api/auth/alert-notifications/")
        data = response.json()
        assert data["count"] == 1
        assert data["notifications"][0]["ticker"] == "PETR4"


@pytest.mark.django_db
class TestDismissAlertNotification:
    def test_dismiss_sets_dismissed_at(self, authenticated_client, user):
        notification = _create_notification(user)
        response = authenticated_client.post(
            f"/api/auth/alert-notifications/{notification.id}/dismiss/",
        )
        assert response.status_code == 200
        notification.refresh_from_db()
        assert notification.dismissed_at is not None

    def test_dismiss_nonexistent_returns_404(self, authenticated_client):
        response = authenticated_client.post(
            "/api/auth/alert-notifications/99999/dismiss/",
        )
        assert response.status_code == 404

    def test_cannot_dismiss_other_users_notification(
        self, authenticated_client, other_user,
    ):
        notification = _create_notification(other_user)
        response = authenticated_client.post(
            f"/api/auth/alert-notifications/{notification.id}/dismiss/",
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestDismissAllAlertNotifications:
    def test_dismiss_all_sets_dismissed_at_on_pending(
        self, authenticated_client, user,
    ):
        notification_a = _create_notification(user, ticker="PETR4")
        notification_b = _create_notification(user, ticker="VALE3")
        already_dismissed = _create_notification(
            user, ticker="OLD1", dismissed_at=timezone.now(),
        )
        response = authenticated_client.post(
            "/api/auth/alert-notifications/dismiss-all/",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dismissed"] == 2
        notification_a.refresh_from_db()
        notification_b.refresh_from_db()
        assert notification_a.dismissed_at is not None
        assert notification_b.dismissed_at is not None
