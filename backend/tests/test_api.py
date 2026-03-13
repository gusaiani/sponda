"""Integration tests for API endpoints."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client

from quotes.models import LookupLog, QuarterlyEarnings


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def mock_brapi_quote():
    return {
        "symbol": "PETR4",
        "longName": "Petroleo Brasileiro SA Pfd",
        "regularMarketPrice": 45.0,
        "marketCap": 585000000000,
    }


class TestHealthEndpoint:
    def test_returns_200(self, api_client, db):
        response = api_client.get("/api/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPE10Endpoint:
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_earnings")
    def test_returns_pe10_data(
        self, mock_sync, mock_quote, api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "PETR4"
        assert data["pe10"] is not None
        assert data["currentPrice"] == 45.0
        assert data["yearsOfData"] == 10
        assert data["label"] == "PE10"

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_earnings")
    def test_logs_lookup(
        self, mock_sync, mock_quote, api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        api_client.get("/api/quote/PETR4/")
        assert LookupLog.objects.filter(ticker="PETR4").count() == 1

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_earnings")
    def test_ticker_is_uppercased(
        self, mock_sync, mock_quote, api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/petr4/")
        assert response.status_code == 200
        assert response.json()["ticker"] == "PETR4"

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_earnings")
    def test_handles_brapi_error(self, mock_sync, mock_quote, api_client, db):
        from quotes.brapi import BRAPIError

        mock_quote.side_effect = BRAPIError("Service unavailable")
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 502

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_earnings")
    def test_returns_no_data_for_unknown_ticker(
        self, mock_sync, mock_quote, api_client, db, sample_ipca
    ):
        mock_quote.return_value = {
            "symbol": "FAKE3",
            "shortName": "Fake Corp",
            "regularMarketPrice": 10.0,
            "marketCap": 1000000000,
        }
        response = api_client.get("/api/quote/FAKE3/")
        assert response.status_code == 200
        data = response.json()
        assert data["pe10"] is None
        assert data["yearsOfData"] == 0



class TestSignupEndpoint:
    def test_creates_user(self, api_client, db):
        response = api_client.post(
            "/api/auth/signup/",
            {"email": "new@test.com", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["email"] == "new@test.com"

    def test_rejects_short_password(self, api_client, db):
        response = api_client.post(
            "/api/auth/signup/",
            {"email": "new@test.com", "password": "short"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_rejects_duplicate_email(self, api_client, db):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="existing@test.com", email="existing@test.com", password="pass12345"
        )
        response = api_client.post(
            "/api/auth/signup/",
            {"email": "existing@test.com", "password": "securepass123"},
            content_type="application/json",
        )
        assert response.status_code == 400


class TestLoginEndpoint:
    def test_login_success(self, api_client, db):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="user@test.com", email="user@test.com", password="testpass123"
        )
        response = api_client.post(
            "/api/auth/login/",
            {"email": "user@test.com", "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["email"] == "user@test.com"

    def test_login_invalid_credentials(self, api_client, db):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "wrong@test.com", "password": "wrongpass"},
            content_type="application/json",
        )
        assert response.status_code == 401
