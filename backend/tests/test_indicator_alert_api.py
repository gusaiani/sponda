"""Tests for IndicatorAlert CRUD endpoints."""
from decimal import Decimal

import pytest
from django.test import Client

from accounts.models import IndicatorAlert, User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="analyst@example.com", username="analyst", password="secretpw",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@example.com", username="other", password="secretpw",
    )


@pytest.fixture
def logged_in_client(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def anonymous_client():
    return Client()


@pytest.mark.django_db
class TestIndicatorAlertListCreate:
    def test_list_requires_authentication(self, anonymous_client):
        response = anonymous_client.get("/api/auth/alerts/")
        assert response.status_code in (401, 403)

    def test_list_returns_empty_when_user_has_no_alerts(self, logged_in_client):
        response = logged_in_client.get("/api/auth/alerts/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_only_current_user_alerts(
        self, logged_in_client, user, other_user,
    ):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        IndicatorAlert.objects.create(
            user=other_user, ticker="VALE3", indicator="pe10",
            comparison="lte", threshold=Decimal("8"),
        )
        response = logged_in_client.get("/api/auth/alerts/")
        tickers = {row["ticker"] for row in response.json()}
        assert tickers == {"PETR4"}

    def test_list_filters_by_ticker_query_param(self, logged_in_client, user):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        IndicatorAlert.objects.create(
            user=user, ticker="VALE3", indicator="pe10",
            comparison="lte", threshold=Decimal("8"),
        )
        response = logged_in_client.get("/api/auth/alerts/?ticker=PETR4")
        tickers = {row["ticker"] for row in response.json()}
        assert tickers == {"PETR4"}

    def test_create_alert(self, logged_in_client, user):
        response = logged_in_client.post(
            "/api/auth/alerts/",
            data={
                "ticker": "PETR4",
                "indicator": "pe10",
                "comparison": "lte",
                "threshold": "10",
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["ticker"] == "PETR4"
        assert body["indicator"] == "pe10"
        assert body["comparison"] == "lte"
        assert Decimal(str(body["threshold"])) == Decimal("10")
        assert body["active"] is True
        assert IndicatorAlert.objects.filter(user=user, ticker="PETR4").exists()

    def test_create_normalizes_ticker_uppercase(self, logged_in_client, user):
        response = logged_in_client.post(
            "/api/auth/alerts/",
            data={
                "ticker": "petr4",
                "indicator": "pe10",
                "comparison": "lte",
                "threshold": "10",
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        assert IndicatorAlert.objects.get(user=user).ticker == "PETR4"

    def test_create_rejects_invalid_indicator(self, logged_in_client):
        response = logged_in_client.post(
            "/api/auth/alerts/",
            data={
                "ticker": "PETR4",
                "indicator": "market_return",
                "comparison": "lte",
                "threshold": "10",
            },
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_create_rejects_invalid_comparison(self, logged_in_client):
        response = logged_in_client.post(
            "/api/auth/alerts/",
            data={
                "ticker": "PETR4",
                "indicator": "pe10",
                "comparison": "approximately",
                "threshold": "10",
            },
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_create_rejects_duplicate(self, logged_in_client, user):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        response = logged_in_client.post(
            "/api/auth/alerts/",
            data={
                "ticker": "PETR4",
                "indicator": "pe10",
                "comparison": "lte",
                "threshold": "12",
            },
            content_type="application/json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestIndicatorAlertDetail:
    def test_delete_own_alert(self, logged_in_client, user):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        response = logged_in_client.delete(f"/api/auth/alerts/{alert.id}/")
        assert response.status_code == 204
        assert not IndicatorAlert.objects.filter(id=alert.id).exists()

    def test_delete_other_users_alert_is_404(
        self, logged_in_client, other_user,
    ):
        alert = IndicatorAlert.objects.create(
            user=other_user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        response = logged_in_client.delete(f"/api/auth/alerts/{alert.id}/")
        assert response.status_code == 404
        assert IndicatorAlert.objects.filter(id=alert.id).exists()

    def test_update_threshold(self, logged_in_client, user):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        response = logged_in_client.patch(
            f"/api/auth/alerts/{alert.id}/",
            data={"threshold": "8"},
            content_type="application/json",
        )
        assert response.status_code == 200
        alert.refresh_from_db()
        assert alert.threshold == Decimal("8")

    def test_update_active_flag_pauses_alert(self, logged_in_client, user):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        response = logged_in_client.patch(
            f"/api/auth/alerts/{alert.id}/",
            data={"active": False},
            content_type="application/json",
        )
        assert response.status_code == 200
        alert.refresh_from_db()
        assert alert.active is False

    def test_list_requires_authentication_for_create(self, anonymous_client):
        response = anonymous_client.post(
            "/api/auth/alerts/",
            data={
                "ticker": "PETR4",
                "indicator": "pe10",
                "comparison": "lte",
                "threshold": "10",
            },
            content_type="application/json",
        )
        assert response.status_code in (401, 403)
