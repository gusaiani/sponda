"""Integration tests for API endpoints."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client

from quotes.models import BalanceSheet, LookupLog, QuarterlyEarnings
from quotes.views import _clean_company_name


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


class TestCleanCompanyName:
    def test_strips_sa_pfd(self):
        assert _clean_company_name("Petroleo Brasileiro SA Pfd") == "Petroleo Brasileiro"

    def test_strips_sa_dot(self):
        assert _clean_company_name("Eucatex S.A. Industria E Comercio") == "Eucatex"

    def test_strips_sa(self):
        assert _clean_company_name("Vale SA") == "Vale"

    def test_keeps_ticker_unchanged(self):
        assert _clean_company_name("PETR3") == "PETR3"

    def test_keeps_cia_at_start(self):
        assert _clean_company_name("Cia Siderurgica Nacional") == "Cia Siderurgica Nacional"

    def test_handles_on_nm(self):
        assert _clean_company_name("WEG SA ON NM") == "WEG"

    def test_b3_with_suffix(self):
        assert _clean_company_name("B3 SA - Brasil Bolsa Balcao") == "B3"


class TestHealthEndpoint:
    def test_returns_200(self, api_client, db):
        response = api_client.get("/api/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPE10Endpoint:
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_pe10_data(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "PETR4"
        assert data["pe10"] is not None
        assert data["currentPrice"] == 45.0
        assert data["pe10YearsOfData"] == 10
        assert data["pe10Label"] == "PE10"

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_pfcf10_data(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_cash_flows, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 200
        data = response.json()
        assert data["pfcf10"] is not None
        assert data["pfcf10YearsOfData"] == 10
        assert data["pfcf10Label"] == "PFCF10"

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_pfcf10_includes_calculation_details(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_cash_flows, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        data = response.json()
        details = data["pfcf10CalculationDetails"]
        assert len(details) == 10
        first = details[0]
        assert "nominalFCF" in first
        assert "ipcaFactor" in first
        assert "adjustedFCF" in first
        assert "quarterlyDetail" in first

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_pfcf10_avg_adjusted_fcf_returned(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_cash_flows, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        data = response.json()
        assert data["avgAdjustedFCF"] is not None
        assert data["avgAdjustedFCF"] > 0

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_pfcf10_null_without_cash_flow_data(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        """PFCF10 is null when there are no cash flow records."""
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        data = response.json()
        assert data["pfcf10"] is None
        assert data["pfcf10YearsOfData"] == 0
        assert data["pfcf10Error"] is not None

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_logs_lookup(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        api_client.get("/api/quote/PETR4/")
        assert LookupLog.objects.filter(ticker="PETR4").count() == 1

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_ticker_is_uppercased(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/petr4/")
        assert response.status_code == 200
        assert response.json()["ticker"] == "PETR4"

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_handles_brapi_error(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, api_client, db
    ):
        from quotes.brapi import BRAPIError

        mock_quote.side_effect = BRAPIError("Service unavailable")
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 502

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_no_data_for_unknown_ticker(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, db, sample_ipca
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
        assert data["pe10YearsOfData"] == 0
        assert data["pfcf10"] is None
        assert data["pfcf10YearsOfData"] == 0
        assert data["debtToEquity"] is None
        assert data["liabilitiesToEquity"] is None

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_leverage_data(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, sample_balance_sheet, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 200
        data = response.json()
        assert data["debtToEquity"] == 1.5
        assert data["liabilitiesToEquity"] == 2.5
        assert data["leverageDate"] == "2025-09-30"
        assert data["leverageError"] is None

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_leverage_null_without_balance_sheet(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/")
        data = response.json()
        assert data["debtToEquity"] is None
        assert data["liabilitiesToEquity"] is None
        assert data["leverageError"] is not None


class TestFundamentalsEndpoint:
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_per_year_data(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_cash_flows, sample_balance_sheet, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/fundamentals/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Years sorted descending
        years = [row["year"] for row in data]
        assert years == sorted(years, reverse=True)

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_includes_balance_sheet_fields(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_balance_sheet, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/fundamentals/")
        data = response.json()
        year_2025 = next(row for row in data if row["year"] == 2025)
        assert year_2025["totalDebt"] == 300_000_000_000
        assert year_2025["totalLiabilities"] == 500_000_000_000
        assert year_2025["stockholdersEquity"] == 200_000_000_000

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_includes_earnings_and_cash_flow(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_cash_flows, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/fundamentals/")
        data = response.json()
        year_2024 = next(row for row in data if row["year"] == 2024)
        assert year_2024["netIncome"] is not None
        assert year_2024["fcf"] is not None
        assert year_2024["operatingCashFlow"] is not None
        assert year_2024["quarters"] == 4

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_has_cache_header(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/fundamentals/")
        assert "max-age=3600" in response["Cache-Control"]

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_404_for_unknown_ticker(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, db
    ):
        from quotes.brapi import BRAPIError
        mock_quote.side_effect = BRAPIError("No results for ticker FAKE3")
        response = api_client.get("/api/quote/FAKE3/fundamentals/")
        assert response.status_code == 404

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_empty_list_without_data(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, db, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/PETR4/fundamentals/")
        assert response.status_code == 200
        assert response.json() == []

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_ticker_is_uppercased(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        response = api_client.get("/api/quote/petr4/fundamentals/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0


MOCK_HISTORICAL_PRICES = [
    {"date": 1704067200, "adjustedClose": 30.0},  # 2024-01-01
    {"date": 1706745600, "adjustedClose": 32.0},  # 2024-02-01
    {"date": 1735689600, "adjustedClose": 35.0},  # 2025-01-01
    {"date": 1738368000, "adjustedClose": 37.0},  # 2025-02-01
]


class TestMultiplesHistoryEndpoint:
    @patch("quotes.views.fetch_historical_prices")
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_prices_and_multiples(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, mock_hist,
        api_client, sample_earnings, sample_cash_flows, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        mock_hist.return_value = MOCK_HISTORICAL_PRICES
        response = api_client.get("/api/quote/PETR4/multiples-history/")
        assert response.status_code == 200
        data = response.json()
        assert "prices" in data
        assert "multiples" in data
        assert "pl" in data["multiples"]
        assert "pfcl" in data["multiples"]
        assert len(data["prices"]) == 4

    @patch("quotes.views.fetch_historical_prices")
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_ticker_is_uppercased(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, mock_hist,
        api_client, sample_earnings, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        mock_hist.return_value = MOCK_HISTORICAL_PRICES
        response = api_client.get("/api/quote/petr4/multiples-history/")
        assert response.status_code == 200

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_404_for_unknown_ticker(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, api_client, db
    ):
        from quotes.brapi import BRAPIError
        mock_quote.side_effect = BRAPIError("No results for ticker FAKE3")
        response = api_client.get("/api/quote/FAKE3/multiples-history/")
        assert response.status_code == 404

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_502_on_brapi_error(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, api_client, db
    ):
        from quotes.brapi import BRAPIError
        mock_quote.side_effect = BRAPIError("Service unavailable")
        response = api_client.get("/api/quote/PETR4/multiples-history/")
        assert response.status_code == 502

    @patch("quotes.views.fetch_historical_prices")
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_returns_502_when_historical_prices_fail(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, mock_hist,
        api_client, db, mock_brapi_quote
    ):
        from quotes.brapi import BRAPIError
        mock_quote.return_value = mock_brapi_quote
        mock_hist.side_effect = BRAPIError("Timeout")
        response = api_client.get("/api/quote/PETR4/multiples-history/")
        assert response.status_code == 502

    @patch("quotes.views.fetch_historical_prices")
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_has_cache_header(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, mock_hist,
        api_client, sample_earnings, mock_brapi_quote
    ):
        mock_quote.return_value = mock_brapi_quote
        mock_hist.return_value = MOCK_HISTORICAL_PRICES
        response = api_client.get("/api/quote/PETR4/multiples-history/")
        assert "max-age=3600" in response["Cache-Control"]


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


class TestTickerRateLimit:
    """Tests for the distinct-ticker-per-day rate limit."""

    def test_same_ticker_multiple_times_counts_as_one(self, api_client, db):
        """Querying the same ticker repeatedly should only count once."""
        for _ in range(5):
            LookupLog.objects.create(session_key="sess1", ticker="PETR4")

        distinct = LookupLog.objects.filter(
            session_key="sess1"
        ).values("ticker").distinct().count()
        assert distinct == 1

    def test_different_tickers_count_separately(self, api_client, db):
        """Each unique ticker is a separate count."""
        for i, ticker in enumerate(["PETR4", "VALE3", "ITUB4"]):
            LookupLog.objects.create(session_key="sess2", ticker=ticker)

        distinct = LookupLog.objects.filter(
            session_key="sess2"
        ).values("ticker").distinct().count()
        assert distinct == 3

    def test_limit_is_200_distinct_tickers(self, db):
        """Verify the limit constant is 200."""
        from quotes.views import PE10View
        assert PE10View.DAILY_DISTINCT_TICKER_LIMIT == 200
