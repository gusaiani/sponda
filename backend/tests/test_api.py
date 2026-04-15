"""Integration tests for API endpoints."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client
from django.utils import timezone

from quotes.models import IPCAIndex, LookupLog, Ticker
from quotes.views import _clean_company_name, format_display_name


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


class TestFormatDisplayName:
    def test_extracts_trade_name_after_sa(self):
        assert format_display_name("PETROLEO BRASILEIRO S.A. PETROBRAS") == "Petrobras"

    def test_strips_sa_and_title_cases(self):
        assert format_display_name("VALE S.A.") == "Vale"

    def test_strips_sa_and_title_cases_multiword(self):
        assert format_display_name("MAGAZINE LUIZA S.A.") == "Magazine Luiza"

    def test_expands_bco_to_banco(self):
        assert format_display_name("BCO BRASIL S.A.") == "Banco do Brasil"

    def test_expands_bco_bradesco(self):
        assert format_display_name("BCO BRADESCO S.A.") == "Banco Bradesco"

    def test_cia_becomes_title_case(self):
        assert format_display_name("CIA SIDERURGICA NACIONAL") == "Cia Siderúrgica Nacional"

    def test_copel_extracts_trade_name_after_dash(self):
        assert format_display_name("CIA PARANAENSE DE ENERGIA - COPEL") == "Copel"

    def test_ambev(self):
        assert format_display_name("AMBEV S.A.") == "Ambev"

    def test_itau_unibanco(self):
        assert format_display_name("ITAU UNIBANCO HOLDING S.A.") == "Itaú Unibanco"

    def test_b3(self):
        assert format_display_name("B3 S.A. - BRASIL. BOLSA. BALCÃO") == "B3"

    def test_keeps_acronyms_uppercase(self):
        assert format_display_name("WEG S.A.") == "WEG"

    def test_lojas_renner(self):
        assert format_display_name("LOJAS RENNER S.A.") == "Lojas Renner"

    def test_returns_symbol_for_ticker_like_names(self):
        assert format_display_name("MBRF3") == "MBRF3"

    def test_empty_string(self):
        assert format_display_name("") == ""

    def test_braskem(self):
        assert format_display_name("BRASKEM S.A.") == "Braskem"

    def test_strips_holding_suffix(self):
        assert format_display_name("ITAUSA S.A.") == "Itaúsa"

    def test_bb_seguridade(self):
        assert format_display_name("BB SEGURIDADE PARTICIPAÇÕES S.A.") == "BB Seguridade"


class TestTickerSearchEndpoint:
    def test_returns_empty_without_query(self, api_client, db):
        response = api_client.get("/api/tickers/search/")
        assert response.status_code == 200
        assert response.json() == []

    def test_searches_by_symbol_prefix(self, api_client, db):
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", display_name="Apple", type="stock")
        Ticker.objects.create(symbol="AMZN", name="Amazon", display_name="Amazon", type="stock")
        Ticker.objects.create(symbol="PETR4", name="Petrobras", display_name="Petrobras", type="stock")
        response = api_client.get("/api/tickers/search/?q=AA")
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"

    def test_searches_by_name(self, api_client, db):
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", display_name="Apple", type="stock")
        Ticker.objects.create(symbol="MSFT", name="Microsoft", display_name="Microsoft", type="stock")
        response = api_client.get("/api/tickers/search/?q=micro")
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "MSFT"

    def test_limits_results_to_8(self, api_client, db):
        for i in range(15):
            Ticker.objects.create(symbol=f"T{i:03d}", name=f"Test Corp {i}", display_name=f"Test Corp {i}", type="stock")
        response = api_client.get("/api/tickers/search/?q=T")
        data = response.json()
        assert len(data) == 8

    def test_symbol_matches_come_first(self, api_client, db):
        Ticker.objects.create(symbol="MSFT", name="Microsoft", display_name="Microsoft", type="stock")
        Ticker.objects.create(symbol="AAPL", name="Apple has MSFT partnership", display_name="Apple has MSFT partnership", type="stock")
        response = api_client.get("/api/tickers/search/?q=MSFT")
        data = response.json()
        assert data[0]["symbol"] == "MSFT"

    def test_results_sorted_by_market_cap_descending(self, api_client, db):
        Ticker.objects.create(symbol="AAPL", name="Apple", display_name="Apple", type="stock", market_cap=3_000_000_000_000)
        Ticker.objects.create(symbol="AMZN", name="Amazon", display_name="Amazon", type="stock", market_cap=2_000_000_000_000)
        Ticker.objects.create(symbol="ABNB", name="Airbnb", display_name="Airbnb", type="stock", market_cap=80_000_000_000)
        response = api_client.get("/api/tickers/search/?q=A")
        data = response.json()
        assert data[0]["symbol"] == "AAPL"
        assert data[1]["symbol"] == "AMZN"
        assert data[2]["symbol"] == "ABNB"

    def test_null_market_cap_sorted_last(self, api_client, db):
        Ticker.objects.create(symbol="AAPL", name="Apple", display_name="Apple", type="stock", market_cap=3_000_000_000_000)
        Ticker.objects.create(symbol="ACME", name="Acme Corp", display_name="Acme Corp", type="stock", market_cap=None)
        response = api_client.get("/api/tickers/search/?q=A")
        data = response.json()
        assert data[0]["symbol"] == "AAPL"
        assert data[1]["symbol"] == "ACME"

    def test_name_matches_blend_with_symbol_matches(self, api_client, db):
        """When 8+ symbol prefix matches exist, name matches should still
        appear so that popular companies surface (e.g. Microsoft for 'mic')."""
        # Create many obscure tickers starting with "MIC"
        for i in range(10):
            Ticker.objects.create(
                symbol=f"MIC{chr(65 + i)}", name=f"Micro Corp {i}",
                display_name=f"Micro Corp {i}", type="stock",
            )
        # Microsoft doesn't start with MIC but its name contains "mic"
        Ticker.objects.create(
            symbol="MSFT", name="Microsoft Corporation",
            display_name="Microsoft Corporation", type="stock",
            market_cap=2_700_000_000_000,
        )
        response = api_client.get("/api/tickers/search/?q=mic")
        data = response.json()
        symbols = [d["symbol"] for d in data]
        assert "MSFT" in symbols, f"Microsoft should appear in results: {symbols}"

    def test_name_matches_with_market_cap_rank_higher(self, api_client, db):
        """Name matches with high market cap should appear before obscure
        symbol prefix matches with no market cap."""
        for i in range(10):
            Ticker.objects.create(
                symbol=f"MIC{chr(65 + i)}", name=f"Micro Corp {i}",
                display_name=f"Micro Corp {i}", type="stock",
            )
        Ticker.objects.create(
            symbol="MSFT", name="Microsoft Corporation",
            display_name="Microsoft Corporation", type="stock",
            market_cap=2_700_000_000_000,
        )
        Ticker.objects.create(
            symbol="MU", name="Micron Technology",
            display_name="Micron Technology", type="stock",
            market_cap=100_000_000_000,
        )
        response = api_client.get("/api/tickers/search/?q=mic")
        data = response.json()
        symbols = [d["symbol"] for d in data]
        # Both popular companies should appear
        assert "MSFT" in symbols
        assert "MU" in symbols


class TestHealthEndpoint:
    def test_returns_ok_when_data_is_fresh(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock")
        IPCAIndex.objects.create(date=date.today(), annual_rate=Decimal("4.5"))
        response = api_client.get("/api/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["tickers"]["stale"] is False
        assert data["ipca"]["stale"] is False

    def test_returns_degraded_when_tickers_are_stale(self, api_client, db):
        three_days_ago = timezone.now() - timedelta(days=3)
        ticker = Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock")
        Ticker.objects.filter(pk=ticker.pk).update(updated_at=three_days_ago)
        IPCAIndex.objects.create(date=date.today(), annual_rate=Decimal("4.5"))
        response = api_client.get("/api/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["tickers"]["stale"] is True

    def test_returns_degraded_when_ipca_is_stale(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock")
        IPCAIndex.objects.create(date=date.today() - timedelta(days=60), annual_rate=Decimal("4.5"))
        response = api_client.get("/api/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["ipca"]["stale"] is True

    def test_returns_degraded_when_no_data(self, api_client, db):
        response = api_client.get("/api/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["tickers"]["stale"] is True
        assert data["ipca"]["stale"] is True


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
        from quotes.providers import ProviderError as BRAPIError

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

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_second_request_served_from_cache(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        """Second request for the same ticker skips fetch_quote (served from Redis)."""
        mock_quote.return_value = mock_brapi_quote
        response_1 = api_client.get("/api/quote/PETR4/")
        assert response_1.status_code == 200
        response_2 = api_client.get("/api/quote/PETR4/")
        assert response_2.status_code == 200
        assert response_1.json()["pe10"] == response_2.json()["pe10"]
        # fetch_quote called only once — second request served from cache
        assert mock_quote.call_count == 1

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_cache_is_per_ticker(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_ipca, mock_brapi_quote
    ):
        """Different tickers are cached independently."""
        mock_quote.return_value = mock_brapi_quote
        api_client.get("/api/quote/PETR4/")
        mock_quote.return_value = {
            **mock_brapi_quote, "symbol": "VALE3",
            "longName": "Vale SA", "regularMarketPrice": 60.0,
        }
        api_client.get("/api/quote/VALE3/")
        assert mock_quote.call_count == 2

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_error_responses_are_not_cached(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, db, sample_ipca
    ):
        """A 502 error should not be cached — next request retries."""
        from quotes.providers import ProviderError
        mock_quote.side_effect = ProviderError("Service unavailable")
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 502
        # Fix the provider and retry
        mock_quote.side_effect = None
        mock_quote.return_value = {
            "symbol": "PETR4", "longName": "Petrobras",
            "regularMarketPrice": 45.0, "marketCap": 585000000000,
        }
        response = api_client.get("/api/quote/PETR4/")
        assert response.status_code == 200


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
        result = response.json()
        assert isinstance(result, dict)
        assert "years" in result
        assert "quarterlyRatios" in result
        data = result["years"]
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
        data = response.json()["years"]
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
        data = response.json()["years"]
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
        from quotes.providers import ProviderError as BRAPIError
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
        result = response.json()
        assert result["years"] == []
        assert result["quarterlyRatios"] == []

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
        data = response.json()["years"]
        assert len(data) > 0

    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_second_request_served_from_cache(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote,
        api_client, sample_earnings, sample_cash_flows, sample_balance_sheet, sample_ipca, mock_brapi_quote
    ):
        """Second request for fundamentals skips computation (served from cache)."""
        mock_quote.return_value = mock_brapi_quote
        response_1 = api_client.get("/api/quote/PETR4/fundamentals/")
        assert response_1.status_code == 200
        response_2 = api_client.get("/api/quote/PETR4/fundamentals/")
        assert response_2.status_code == 200
        assert response_1.json() == response_2.json()
        # fetch_quote called only once — second request served from cache
        assert mock_quote.call_count == 1


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
    def test_prices_sorted_ascending_even_when_source_descending(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, mock_hist,
        api_client, sample_earnings, mock_brapi_quote
    ):
        """FMP returns prices newest-first; the API must normalize to oldest-first
        so the frontend mini charts render the X axis chronologically."""
        mock_quote.return_value = mock_brapi_quote
        mock_hist.return_value = list(reversed(MOCK_HISTORICAL_PRICES))
        response = api_client.get("/api/quote/PETR4/multiples-history/")
        assert response.status_code == 200
        dates = [p["date"] for p in response.json()["prices"]]
        assert dates == sorted(dates)

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
        from quotes.providers import ProviderError as BRAPIError
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
        from quotes.providers import ProviderError as BRAPIError
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
        from quotes.providers import ProviderError as BRAPIError
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

    @patch("quotes.views.fetch_historical_prices")
    @patch("quotes.views.fetch_quote")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_second_request_served_from_cache(
        self, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_quote, mock_hist,
        api_client, sample_earnings, sample_cash_flows, mock_brapi_quote
    ):
        """Second request for multiples-history skips external calls (served from cache)."""
        mock_quote.return_value = mock_brapi_quote
        mock_hist.return_value = MOCK_HISTORICAL_PRICES
        response_1 = api_client.get("/api/quote/PETR4/multiples-history/")
        assert response_1.status_code == 200
        response_2 = api_client.get("/api/quote/PETR4/multiples-history/")
        assert response_2.status_code == 200
        assert response_1.json() == response_2.json()
        # fetch_quote and fetch_historical_prices called only once
        assert mock_quote.call_count == 1
        assert mock_hist.call_count == 1


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



class TestSitemap:
    def test_sitemap_returns_xml(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petroleo Brasileiro", sector="Energy", type="stock")
        response = api_client.get("/api/sitemap.xml")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/xml"
        content = response.content.decode()
        assert "https://sponda.capital/en" in content
        assert "https://sponda.capital/pt" in content

    def test_sitemap_has_locale_prefixed_ticker_urls(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petroleo Brasileiro", type="stock")
        content = api_client.get("/api/sitemap.xml").content.decode()
        for locale in ("en", "pt", "es", "zh", "fr", "de", "it"):
            assert f"https://sponda.capital/{locale}/PETR4" in content

    def test_sitemap_uses_localized_tab_slugs(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        content = api_client.get("/api/sitemap.xml").content.decode()
        # Portuguese slugs
        assert "https://sponda.capital/pt/PETR4/fundamentos" in content
        assert "https://sponda.capital/pt/PETR4/graficos" in content
        assert "https://sponda.capital/pt/PETR4/comparar" in content
        # English slugs
        assert "https://sponda.capital/en/PETR4/fundamentals" in content
        assert "https://sponda.capital/en/PETR4/charts" in content
        assert "https://sponda.capital/en/PETR4/compare" in content
        # French slugs
        assert "https://sponda.capital/fr/PETR4/fondamentaux" in content
        assert "https://sponda.capital/fr/PETR4/graphiques" in content
        # German slugs
        assert "https://sponda.capital/de/PETR4/fundamentaldaten" in content

    def test_sitemap_includes_hreflang_alternates(self, api_client, db):
        Ticker.objects.create(symbol="VALE3", name="Vale", type="stock")
        content = api_client.get("/api/sitemap.xml").content.decode()
        # Each URL group should advertise every locale via xhtml:link rel="alternate"
        assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in content
        assert 'hreflang="en"' in content
        assert 'hreflang="pt-BR"' in content
        assert 'hreflang="es"' in content
        assert 'hreflang="zh-CN"' in content
        assert 'hreflang="fr"' in content
        assert 'hreflang="de"' in content
        assert 'hreflang="it"' in content
        assert 'hreflang="x-default"' in content

    def test_sitemap_excludes_fractional_shares(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        Ticker.objects.create(symbol="PETR4F", name="Petroleo Frac", type="stock")
        response = api_client.get("/api/sitemap.xml")
        content = response.content.decode()
        assert "PETR4" in content
        assert "PETR4F" not in content

    def test_sitemap_excludes_non_stock(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        Ticker.objects.create(symbol="AAPL34", name="Apple BDR", type="bdr")
        response = api_client.get("/api/sitemap.xml")
        content = response.content.decode()
        assert "PETR4" in content
        assert "AAPL34" not in content

    def test_sitemap_root_url(self, api_client, db):
        Ticker.objects.create(symbol="VALE3", name="Vale", type="stock")
        response = api_client.get("/sitemap.xml")
        assert response.status_code == 200
        assert "VALE3" in response.content.decode()

    def test_sitemap_is_cached(self, api_client, db):
        response = api_client.get("/api/sitemap.xml")
        assert "max-age=86400" in response["Cache-Control"]


class TestOGTagInjection:
    def test_inject_og_tags_includes_company_name(self, db):
        from config.urls import _inject_og_tags

        Ticker.objects.create(symbol="PETR4", name="Petroleo Brasileiro", sector="Energy", type="stock")
        html = (
            '<html><head>'
            '<meta property="og:title" content="default" />'
            '<meta property="og:description" content="default" />'
            '<meta property="og:url" content="https://sponda.capital/" />'
            '<meta property="og:image" content="https://sponda.capital/images/sponda-og.jpg" />'
            '<meta name="twitter:title" content="default" />'
            '<meta name="twitter:description" content="default" />'
            '<meta name="twitter:image" content="https://sponda.capital/images/sponda-og.jpg" />'
            '<meta name="twitter:card" content="summary" />'
            '<meta name="description" content="default" />'
            '<link rel="canonical" href="https://sponda.capital/" />'
            '<title>Sponda</title>'
            '</head></html>'
        )
        result = _inject_og_tags(html, "PETR4")
        assert "Petroleo Brasileiro" in result
        assert "PETR4" in result
        assert 'content="summary_large_image"' in result

    def test_inject_og_tags_canonical_includes_locale_and_subpath(self, db):
        from config.urls import _inject_og_tags

        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        html = (
            '<head>'
            '<link rel="canonical" href="https://sponda.capital/" />'
            '</head>'
        )
        result = _inject_og_tags(html, "PETR4", "fundamentos", locale="pt")
        # Canonical URLs always embed the locale prefix so search engines
        # index the localized page, not a locale-less alias.
        assert 'href="https://sponda.capital/pt/PETR4/fundamentos"' in result

    def test_inject_og_tags_includes_json_ld(self, db):
        from config.urls import _inject_og_tags

        Ticker.objects.create(symbol="WEGE3", name="WEG", sector="Industrials", type="stock")
        html = '<head><title>Sponda</title></head>'
        result = _inject_og_tags(html, "WEGE3")
        assert '"@type": "Dataset"' in result
        assert '"@type": "BreadcrumbList"' in result
        assert "WEG" in result
        assert "Industrials" in result

    def test_inject_og_tags_uses_english_strings_for_en_locale(self, db):
        from config.urls import _inject_og_tags

        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        html = '<head><title>Sponda</title><meta name="description" content="default" /></head>'
        result = _inject_og_tags(html, "PETR4", locale="en")
        assert "Fundamental Indicators" in result
        assert "Fundamental indicators for" in result
        # Portuguese strings should not leak into the English version.
        assert "Indicadores Fundamentalistas" not in result
        assert "Indicadores fundamentalistas" not in result

    def test_inject_og_tags_uses_portuguese_strings_for_pt_locale(self, db):
        from config.urls import _inject_og_tags

        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        html = '<head><title>Sponda</title></head>'
        result = _inject_og_tags(html, "PETR4", locale="pt")
        assert "Indicadores Fundamentalistas" in result

    def test_inject_og_tags_canonical_for_english_locale_uses_localized_tab(self, db):
        from config.urls import _inject_og_tags

        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        html = '<head><link rel="canonical" href="https://sponda.capital/" /></head>'
        result = _inject_og_tags(html, "PETR4", "fundamentals", locale="en")
        assert 'href="https://sponda.capital/en/PETR4/fundamentals"' in result

    def test_inject_og_tags_localizes_tab_labels_in_breadcrumb(self, db):
        from config.urls import _inject_og_tags

        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        html = '<head><title>Sponda</title></head>'
        result = _inject_og_tags(html, "PETR4", "fundamentals", locale="en")
        # BreadcrumbList item for the tab should use the English label.
        assert '"Fundamentals"' in result

    def test_inject_og_tags_defaults_to_portuguese_without_locale(self, db):
        from config.urls import _inject_og_tags

        Ticker.objects.create(symbol="PETR4", name="Petroleo", type="stock")
        html = '<head><title>Sponda</title></head>'
        # Backward compat: calling without a locale keeps the previous PT output.
        result = _inject_og_tags(html, "PETR4")
        assert "Indicadores Fundamentalistas" in result


class TestTickerRegex:
    def test_ticker_regex_matches_bare_ticker(self):
        from config.urls import _TICKER_RE
        m = _TICKER_RE.match("PETR4")
        assert m is not None and m.group("ticker") == "PETR4"

    def test_ticker_regex_matches_ticker_with_portuguese_tab(self):
        from config.urls import _TICKER_RE
        m = _TICKER_RE.match("PETR4/graficos")
        assert m is not None and m.group("ticker") == "PETR4"

    def test_ticker_regex_matches_locale_prefixed_ticker(self):
        from config.urls import _TICKER_RE
        m = _TICKER_RE.match("en/PETR4")
        assert m is not None
        assert m.group("locale") == "en"
        assert m.group("ticker") == "PETR4"

    def test_ticker_regex_matches_locale_prefixed_with_english_tab(self):
        from config.urls import _TICKER_RE
        m = _TICKER_RE.match("en/PETR4/fundamentals")
        assert m is not None
        assert m.group("locale") == "en"
        assert m.group("ticker") == "PETR4"
        assert m.group("sub") == "fundamentals"

    def test_ticker_regex_matches_french_tab_with_locale(self):
        from config.urls import _TICKER_RE
        m = _TICKER_RE.match("fr/PETR4/fondamentaux")
        assert m is not None
        assert m.group("locale") == "fr"
        assert m.group("sub") == "fondamentaux"

    def test_ticker_regex_rejects_unsupported_locale(self):
        from config.urls import _TICKER_RE
        # "xx" is not a supported locale; the path shouldn't be treated as a ticker URL.
        assert _TICKER_RE.match("xx/PETR4") is None


class TestHomepageLayout:
    @pytest.fixture
    def authenticated_client(self, db):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(username="test@test.com", email="test@test.com", password="pass12345")
        client = Client()
        client.login(username="test@test.com", password="pass12345")
        return client, user

    def test_get_returns_empty_list_by_default(self, authenticated_client):
        client, _ = authenticated_client
        response = client.get("/api/auth/homepage-layout/")
        assert response.status_code == 200
        assert response.json() == {"layout": []}

    def test_save_and_retrieve_layout(self, authenticated_client):
        client, _ = authenticated_client
        layout = [
            {"type": "ticker", "id": "PETR4"},
            {"type": "list", "id": "1"},
            {"type": "ticker", "id": "VALE3"},
        ]
        response = client.put(
            "/api/auth/homepage-layout/",
            {"layout": layout},
            content_type="application/json",
        )
        assert response.status_code == 200

        response = client.get("/api/auth/homepage-layout/")
        assert response.json()["layout"] == layout

    def test_rejects_unauthenticated(self, api_client, db):
        response = api_client.get("/api/auth/homepage-layout/")
        assert response.status_code in [401, 403]

    def test_rejects_invalid_layout_items(self, authenticated_client):
        client, _ = authenticated_client
        response = client.put(
            "/api/auth/homepage-layout/",
            {"layout": [{"type": "invalid", "id": "x"}]},
            content_type="application/json",
        )
        assert response.status_code == 400
