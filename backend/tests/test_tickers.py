"""Tests for ticker list sync and API endpoint."""
from unittest.mock import patch

import pytest
from django.test import Client

from quotes.brapi import fetch_ticker_list, sync_tickers
from quotes.models import Ticker


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def sample_tickers(db):
    return [
        Ticker.objects.create(
            symbol="PETR4", name="Petroleo Brasileiro", sector="Energy Minerals", type="stock",
        ),
        Ticker.objects.create(
            symbol="VALE3", name="Vale", sector="Non-Energy Minerals", type="stock",
        ),
        Ticker.objects.create(
            symbol="ITUB4", name="Itau Unibanco", sector="Finance", type="stock",
        ),
    ]


@pytest.fixture
def sample_tickers_mixed(db):
    return [
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock"),
        Ticker.objects.create(symbol="KNRI11", name="Kinea Renda", type="fund"),
    ]


MOCK_TICKER_LIST_PAGE_1 = {
    "stocks": [
        {"stock": "PETR4", "name": "PETROLEO BRASILEIRO S.A. PETROBRAS", "sector": "Energy Minerals", "type": "stock", "logo": "https://example.com/petr4.svg"},
        {"stock": "VALE3", "name": "VALE S.A.", "sector": "Non-Energy Minerals", "type": "stock", "logo": "https://example.com/vale3.svg"},
    ],
    "hasNextPage": True,
}

MOCK_TICKER_LIST_PAGE_2 = {
    "stocks": [
        {"stock": "ITUB4", "name": "ITAU UNIBANCO HOLDING", "sector": "Finance", "type": "stock", "logo": "https://example.com/itub4.svg"},
    ],
    "hasNextPage": False,
}


class TestFetchTickerList:
    @patch("quotes.brapi._get")
    def test_fetches_all_pages(self, mock_get):
        mock_get.side_effect = [MOCK_TICKER_LIST_PAGE_1, MOCK_TICKER_LIST_PAGE_2]
        result = fetch_ticker_list()
        assert len(result) == 3
        assert result[0]["stock"] == "PETR4"
        assert result[2]["stock"] == "ITUB4"

    @patch("quotes.brapi._get")
    def test_stops_on_empty_page(self, mock_get):
        mock_get.side_effect = [MOCK_TICKER_LIST_PAGE_1, {"stocks": []}]
        result = fetch_ticker_list()
        assert len(result) == 2

    @patch("quotes.brapi._get")
    def test_stops_on_has_next_page_false(self, mock_get):
        mock_get.return_value = {
            "stocks": [{"stock": "A", "name": "A Corp"}],
            "hasNextPage": False,
        }
        result = fetch_ticker_list()
        assert len(result) == 1
        assert mock_get.call_count == 1


class TestSyncTickers:
    @patch("quotes.brapi.fetch_ticker_list")
    def test_creates_ticker_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_TICKER_LIST_PAGE_1["stocks"] + MOCK_TICKER_LIST_PAGE_2["stocks"]
        count = sync_tickers()
        assert count == 3
        assert Ticker.objects.count() == 3

    @patch("quotes.brapi.fetch_ticker_list")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_TICKER_LIST_PAGE_1["stocks"]
        sync_tickers()
        sync_tickers()  # Second call should update, not duplicate
        assert Ticker.objects.count() == 2

    @patch("quotes.brapi.fetch_ticker_list")
    def test_handles_none_fields(self, mock_fetch, db):
        mock_fetch.return_value = [
            {"stock": "TEST3", "name": None, "sector": None, "type": None, "logo": None},
        ]
        count = sync_tickers()
        assert count == 1
        ticker = Ticker.objects.get(symbol="TEST3")
        assert ticker.name == ""
        assert ticker.sector == ""

    @patch("quotes.brapi.fetch_ticker_list")
    def test_skips_empty_symbol(self, mock_fetch, db):
        mock_fetch.return_value = [
            {"stock": "", "name": "No Symbol"},
            {"stock": "OK3", "name": "OK Corp"},
        ]
        count = sync_tickers()
        assert count == 1
        assert Ticker.objects.filter(symbol="OK3").exists()

    @patch("quotes.brapi.fetch_ticker_list")
    def test_uppercases_symbol(self, mock_fetch, db):
        mock_fetch.return_value = [{"stock": "petr4", "name": "Petrobras"}]
        sync_tickers()
        assert Ticker.objects.filter(symbol="PETR4").exists()

    @patch("quotes.brapi.fetch_ticker_list")
    def test_skips_non_company_instruments(self, mock_fetch, db):
        mock_fetch.return_value = [
            {"stock": "PETR4", "name": "Petrobras"},
            {"stock": "PETR4F", "name": "Petrobras Frac"},
            {"stock": "VALE3", "name": "Vale"},
            {"stock": "VALE3F", "name": "Vale Frac"},
            {"stock": "AAPL34", "name": "Apple BDR"},
            {"stock": "SANB39", "name": "Santander Receipt"},
            {"stock": "KNRI11", "name": "Kinea Renda"},
            {"stock": "ABCB10", "name": "Banco ABC Brasil", "type": "bdr"},
            {"stock": "PINE10", "name": "Banco Pine", "type": "bdr"},
            {"stock": "XPBR31", "name": "XP Inc", "type": "bdr"},
        ]
        count = sync_tickers()
        assert count == 2
        assert Ticker.objects.filter(symbol="PETR4").exists()
        assert Ticker.objects.filter(symbol="VALE3").exists()
        assert not Ticker.objects.filter(symbol="PETR4F").exists()
        assert not Ticker.objects.filter(symbol="VALE3F").exists()
        assert not Ticker.objects.filter(symbol="AAPL34").exists()
        assert not Ticker.objects.filter(symbol="SANB39").exists()
        assert not Ticker.objects.filter(symbol="KNRI11").exists()
        assert not Ticker.objects.filter(symbol="ABCB10").exists()
        assert not Ticker.objects.filter(symbol="PINE10").exists()
        assert not Ticker.objects.filter(symbol="XPBR31").exists()

    @patch("quotes.brapi.fetch_ticker_list")
    def test_strips_brapi_placeholder_logo_url(self, mock_fetch, db):
        """BRAPI returns its generic placeholder URL (BRAPI.svg) for unknown tickers.
        We must not persist that URL — it leads to wasted fetches that are always rejected."""
        mock_fetch.return_value = [
            {"stock": "KLBN4", "name": "KLABIN", "type": "stock",
             "logo": "https://icons.brapi.dev/icons/BRAPI.svg"},
            {"stock": "VALE3", "name": "VALE", "type": "stock",
             "logo": "https://icons.brapi.dev/icons/VALE3.svg"},
        ]
        sync_tickers()
        assert Ticker.objects.get(symbol="KLBN4").logo == ""
        assert Ticker.objects.get(symbol="VALE3").logo == "https://icons.brapi.dev/icons/VALE3.svg"

    @patch("quotes.brapi.fetch_ticker_list")
    def test_deletes_tickers_no_longer_in_source(self, mock_fetch, db):
        Ticker.objects.create(symbol="AAPL34", name="Apple BDR", type="bdr")
        Ticker.objects.create(symbol="KNRI11", name="Kinea Renda", type="fund")
        Ticker.objects.create(symbol="OLD3", name="Old Company", type="stock")
        mock_fetch.return_value = [
            {"stock": "PETR4", "name": "Petrobras"},
        ]
        sync_tickers()
        assert Ticker.objects.filter(symbol="PETR4").exists()
        assert not Ticker.objects.filter(symbol="AAPL34").exists()
        assert not Ticker.objects.filter(symbol="KNRI11").exists()
        assert not Ticker.objects.filter(symbol="OLD3").exists()


class TestTickerListEndpoint:
    def test_returns_ticker_list(self, api_client, sample_tickers):
        response = api_client.get("/api/tickers/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        symbols = [t["symbol"] for t in data]
        assert "PETR4" in symbols
        assert "VALE3" in symbols

    def test_returns_expected_fields(self, api_client, sample_tickers):
        response = api_client.get("/api/tickers/")
        item = response.json()[0]
        assert "symbol" in item
        assert "name" in item
        assert "sector" in item
        assert "type" in item
        assert "logo" in item

    def test_returns_empty_list_when_no_tickers(self, api_client, db):
        response = api_client.get("/api/tickers/")
        assert response.status_code == 200
        assert response.json() == []

    def test_has_cache_header(self, api_client, sample_tickers):
        response = api_client.get("/api/tickers/")
        assert "max-age=3600" in response["Cache-Control"]

    def test_excludes_fractional_tickers(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock")
        Ticker.objects.create(symbol="PETR4F", name="Petrobras Frac", type="stock")
        Ticker.objects.create(symbol="VALE3", name="Vale", type="stock")
        response = api_client.get("/api/tickers/")
        symbols = [t["symbol"] for t in response.json()]
        assert "PETR4" in symbols
        assert "VALE3" in symbols
        assert "PETR4F" not in symbols

    def test_excludes_non_stock_types(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock")
        Ticker.objects.create(symbol="KNRI11", name="Kinea Renda", type="fund")
        Ticker.objects.create(symbol="BOVA11", name="iShares Ibov", type="bdr")
        response = api_client.get("/api/tickers/")
        symbols = [t["symbol"] for t in response.json()]
        assert "PETR4" in symbols
        assert "KNRI11" not in symbols
        assert "BOVA11" not in symbols


class TestTickerPeersEndpoint:
    def test_returns_peers_for_same_sector(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", sector="Energy Minerals", type="stock")
        Ticker.objects.create(symbol="PRIO3", name="PRIO", sector="Energy Minerals", type="stock")
        Ticker.objects.create(symbol="RECV3", name="PetroReconcavo", sector="Energy Minerals", type="stock")
        Ticker.objects.create(symbol="VALE3", name="Vale", sector="Non-Energy Minerals", type="stock")
        response = api_client.get("/api/tickers/PETR4/peers/")
        assert response.status_code == 200
        symbols = [p["symbol"] for p in response.json()]
        assert "PRIO3" in symbols
        assert "RECV3" in symbols
        assert "VALE3" not in symbols
        assert "PETR4" not in symbols

    def test_returns_name_in_response(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", sector="Energy Minerals", type="stock")
        Ticker.objects.create(symbol="PRIO3", name="PRIO", sector="Energy Minerals", type="stock")
        response = api_client.get("/api/tickers/PETR4/peers/")
        peer = response.json()[0]
        assert "symbol" in peer
        assert "name" in peer

    def test_returns_404_for_unknown_ticker(self, api_client, db):
        response = api_client.get("/api/tickers/ZZZZ3/peers/")
        assert response.status_code == 404

    def test_returns_empty_for_no_sector(self, api_client, db):
        Ticker.objects.create(symbol="TEST3", name="Test", sector="", type="stock")
        response = api_client.get("/api/tickers/TEST3/peers/")
        assert response.status_code == 200
        assert response.json() == []

    @patch("quotes.views.fetch_profile")
    def test_lazy_fetches_sector_for_us_ticker(self, mock_fetch_profile, api_client, db):
        """US tickers without sector should fetch it from FMP profile on demand."""
        Ticker.objects.create(symbol="TEAM", name="Atlassian", sector="", type="stock")
        Ticker.objects.create(symbol="CRM", name="Salesforce", sector="Technology", type="stock")
        Ticker.objects.create(symbol="NOW", name="ServiceNow", sector="Technology", type="stock")
        Ticker.objects.create(symbol="SNOW", name="Snowflake", sector="Technology", type="stock")

        mock_fetch_profile.return_value = {"sector": "Technology", "industry": "Software"}

        response = api_client.get("/api/tickers/TEAM/peers/")
        assert response.status_code == 200
        symbols = [p["symbol"] for p in response.json()]
        assert "CRM" in symbols

        # Sector should be saved to DB
        team = Ticker.objects.get(symbol="TEAM")
        assert team.sector == "Technology"

    @patch("quotes.views.fetch_profile")
    def test_lazy_fetch_does_not_apply_to_brazilian_tickers(self, mock_fetch_profile, api_client, db):
        """Brazilian tickers should not trigger FMP profile fetch."""
        Ticker.objects.create(symbol="TEST3", name="Test Co", sector="", type="stock")
        response = api_client.get("/api/tickers/TEST3/peers/")
        assert response.status_code == 200
        mock_fetch_profile.assert_not_called()

    def test_deduplicates_on_pn_variants(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", sector="Energy Minerals", type="stock")
        Ticker.objects.create(symbol="CSAN3", name="Cosan", sector="Energy Minerals", type="stock")
        Ticker.objects.create(symbol="CSAN4", name="Cosan", sector="Energy Minerals", type="stock")
        response = api_client.get("/api/tickers/PETR4/peers/")
        symbols = [p["symbol"] for p in response.json()]
        assert len(symbols) == 1

    def test_has_cache_header(self, api_client, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", sector="Energy Minerals", type="stock")
        response = api_client.get("/api/tickers/PETR4/peers/")
        assert "max-age=3600" in response["Cache-Control"]

    def test_finance_subsector_ranks_banks_before_insurance(self, api_client, db):
        """Same-subsector peers come first; different-subsector same-sector peers fill the tail."""
        Ticker.objects.create(symbol="ITUB4", name="Itau Unibanco", sector="Finance", type="stock")
        Ticker.objects.create(symbol="BBDC4", name="BCO Bradesco", sector="Finance", type="stock")
        Ticker.objects.create(symbol="BBAS3", name="BCO Brasil", sector="Finance", type="stock")
        Ticker.objects.create(symbol="SANB11", name="Banco Santander", sector="Finance", type="stock")
        Ticker.objects.create(symbol="SULA11", name="Sul America Seguros", sector="Finance", type="stock")
        response = api_client.get("/api/tickers/ITUB4/peers/")
        symbols = [p["symbol"] for p in response.json()]
        assert "BBDC4" in symbols
        assert "BBAS3" in symbols
        assert "SANB11" in symbols
        # Insurer may fill the tail but must come after all banks
        if "SULA11" in symbols:
            assert symbols.index("SULA11") > symbols.index("BBDC4")
            assert symbols.index("SULA11") > symbols.index("BBAS3")
            assert symbols.index("SULA11") > symbols.index("SANB11")

    def test_fills_with_broader_sector_when_few_subsector_peers(self, api_client, db):
        Ticker.objects.create(symbol="SULA11", name="Sul America Seguros", sector="Finance", type="stock")
        Ticker.objects.create(symbol="ITUB4", name="Itau Unibanco", sector="Finance", type="stock")
        Ticker.objects.create(symbol="BBDC4", name="BCO Bradesco", sector="Finance", type="stock")
        Ticker.objects.create(symbol="BBAS3", name="BCO Brasil", sector="Finance", type="stock")
        # SULA11's subsector is "Seguros", 0 peers there → fills with broader "Finance"
        response = api_client.get("/api/tickers/SULA11/peers/")
        symbols = [p["symbol"] for p in response.json()]
        assert len(symbols) >= 2

    def test_ranks_same_subsector_before_other_subsectors_within_sector(self, api_client, db):
        """Vale (Mineração) should show Mineração/Siderurgia peers before Papel e Celulose peers,
        regardless of market cap. Klabin must fall below smaller mining/steel peers."""
        Ticker.objects.create(
            symbol="VALE3", name="VALE S.A.", sector="Non-Energy Minerals",
            type="stock", market_cap=300_000_000_000,
        )
        # Klabin is heavier than most miners — without subsector logic, it would
        # rank above them on market cap alone.
        Ticker.objects.create(
            symbol="KLBN4", name="KLABIN S.A.", sector="Non-Energy Minerals",
            type="stock", market_cap=50_000_000_000,
        )
        Ticker.objects.create(
            symbol="ETER3", name="ETERNIT S.A.", sector="Non-Energy Minerals",
            type="stock", market_cap=45_000_000_000,
        )
        Ticker.objects.create(
            symbol="EUCA4", name="EUCATEX S.A. INDUSTRIA E COMERCIO",
            sector="Non-Energy Minerals", type="stock", market_cap=40_000_000_000,
        )
        # Mining/Siderurgia peers have smaller caps but share Vale's subsector.
        Ticker.objects.create(
            symbol="CMIN3", name="CSN MINERAÇÃO S.A.", sector="Non-Energy Minerals",
            type="stock", market_cap=10_000_000_000,
        )
        Ticker.objects.create(
            symbol="GGBR4", name="GERDAU S.A.", sector="Non-Energy Minerals",
            type="stock", market_cap=8_000_000_000,
        )
        Ticker.objects.create(
            symbol="CSNA3", name="CIA SIDERURGICA NACIONAL", sector="Non-Energy Minerals",
            type="stock", market_cap=5_000_000_000,
        )
        response = api_client.get("/api/tickers/VALE3/peers/")
        symbols = [p["symbol"] for p in response.json()]
        # Mineração/Siderurgia peers (CMIN3, GGBR4, CSNA3) must all come before
        # Papel (KLBN4) and Construção (ETER3, EUCA4).
        assert symbols.index("CMIN3") < symbols.index("KLBN4")
        assert symbols.index("GGBR4") < symbols.index("KLBN4")
        assert symbols.index("CSNA3") < symbols.index("KLBN4")
        assert symbols.index("CMIN3") < symbols.index("ETER3")
        assert symbols.index("CMIN3") < symbols.index("EUCA4")

    def test_fills_from_adjacent_sector_when_sector_is_small(self, api_client, db):
        """If same-sector peer pool is thin, fill with adjacent-sector peers (after in-sector ones)."""
        # Source sits in a thin sector with only 1 in-sector peer available.
        Ticker.objects.create(
            symbol="SOLO3", name="Solo Only Co", sector="Health Services",
            type="stock", market_cap=5_000_000_000,
        )
        Ticker.objects.create(
            symbol="HAPV3", name="Hapvida", sector="Health Services",
            type="stock", market_cap=40_000_000_000,
        )
        # Adjacent sector (Health Technology) should fill remaining slots.
        Ticker.objects.create(
            symbol="FLRY3", name="Fleury", sector="Health Technology",
            type="stock", market_cap=7_000_000_000,
        )
        Ticker.objects.create(
            symbol="RDOR3", name="Rede D'Or", sector="Health Technology",
            type="stock", market_cap=60_000_000_000,
        )
        # Unrelated sector must not appear.
        Ticker.objects.create(
            symbol="PETR4", name="Petrobras", sector="Energy Minerals",
            type="stock", market_cap=400_000_000_000,
        )
        response = api_client.get("/api/tickers/SOLO3/peers/")
        symbols = [p["symbol"] for p in response.json()]
        assert "HAPV3" in symbols
        # Adjacent-sector peers fill after in-sector
        assert "FLRY3" in symbols or "RDOR3" in symbols
        # Same-sector peer always ranks above adjacent-sector peers
        if "FLRY3" in symbols:
            assert symbols.index("HAPV3") < symbols.index("FLRY3")
        if "RDOR3" in symbols:
            assert symbols.index("HAPV3") < symbols.index("RDOR3")
        # Unrelated sector stays out
        assert "PETR4" not in symbols

    def test_brazilian_source_prefers_brazilian_peers_over_foreign(self, api_client, db):
        """When source is Brazilian, Brazilian peers in same sector come before foreign peers."""
        Ticker.objects.create(
            symbol="VALE3", name="Vale", sector="Non-Energy Minerals", type="stock",
            market_cap=50_000_000_000,
        )
        Ticker.objects.create(
            symbol="AA", name="Alcoa Corporation", sector="Non-Energy Minerals", type="stock",
            market_cap=10_000_000_000,
        )
        Ticker.objects.create(
            symbol="BRAP4", name="Bradespar", sector="Non-Energy Minerals", type="stock",
            market_cap=5_000_000_000,
        )
        Ticker.objects.create(
            symbol="GGBR4", name="Gerdau", sector="Non-Energy Minerals", type="stock",
            market_cap=8_000_000_000,
        )
        response = api_client.get("/api/tickers/VALE3/peers/")
        symbols = [p["symbol"] for p in response.json()]
        # Brazilian peers (GGBR4, BRAP4) must appear before the foreign peer (AA),
        # even though AA has a higher market cap than either.
        assert symbols.index("GGBR4") < symbols.index("AA")
        assert symbols.index("BRAP4") < symbols.index("AA")

    def test_foreign_source_prefers_foreign_peers_over_brazilian(self, api_client, db):
        """When source is a US ticker, US peers come before Brazilian peers in the same sector."""
        Ticker.objects.create(
            symbol="AAPL", name="Apple", sector="Technology Services", type="stock",
            market_cap=3_000_000_000_000,
        )
        Ticker.objects.create(
            symbol="MSFT", name="Microsoft", sector="Technology Services", type="stock",
            market_cap=2_800_000_000_000,
        )
        Ticker.objects.create(
            symbol="GOOGL", name="Alphabet", sector="Technology Services", type="stock",
            market_cap=2_000_000_000_000,
        )
        Ticker.objects.create(
            symbol="TOTS3", name="Totvs", sector="Technology Services", type="stock",
            market_cap=5_000_000_000,
        )
        response = api_client.get("/api/tickers/AAPL/peers/")
        symbols = [p["symbol"] for p in response.json()]
        assert symbols.index("MSFT") < symbols.index("TOTS3")
        assert symbols.index("GOOGL") < symbols.index("TOTS3")

    def test_sorts_same_country_peers_by_market_cap_descending(self, api_client, db):
        """Within same-country group, higher market cap comes first."""
        Ticker.objects.create(
            symbol="PETR4", name="Petrobras", sector="Energy Minerals", type="stock",
            market_cap=400_000_000_000,
        )
        Ticker.objects.create(
            symbol="PRIO3", name="PRIO", sector="Energy Minerals", type="stock",
            market_cap=40_000_000_000,
        )
        Ticker.objects.create(
            symbol="RECV3", name="PetroReconcavo", sector="Energy Minerals", type="stock",
            market_cap=5_000_000_000,
        )
        Ticker.objects.create(
            symbol="RRRP3", name="3R Petroleum", sector="Energy Minerals", type="stock",
            market_cap=12_000_000_000,
        )
        response = api_client.get("/api/tickers/PETR4/peers/")
        symbols = [p["symbol"] for p in response.json()]
        assert symbols == ["PRIO3", "RRRP3", "RECV3"]

    def test_peers_with_null_market_cap_come_last_within_country_group(self, api_client, db):
        """Peers missing market_cap should sort after peers with a known market cap in the same country group."""
        Ticker.objects.create(
            symbol="PETR4", name="Petrobras", sector="Energy Minerals", type="stock",
            market_cap=400_000_000_000,
        )
        Ticker.objects.create(
            symbol="PRIO3", name="PRIO", sector="Energy Minerals", type="stock",
            market_cap=40_000_000_000,
        )
        Ticker.objects.create(
            symbol="RECV3", name="PetroReconcavo", sector="Energy Minerals", type="stock",
            market_cap=None,
        )
        response = api_client.get("/api/tickers/PETR4/peers/")
        symbols = [p["symbol"] for p in response.json()]
        assert symbols.index("PRIO3") < symbols.index("RECV3")


class TestTickerDetailEndpoint:
    def test_returns_single_ticker(self, api_client, sample_tickers):
        response = api_client.get("/api/tickers/PETR4/")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "PETR4"
        assert data["name"] == "Petroleo Brasileiro"
        assert data["sector"] == "Energy Minerals"

    def test_returns_expected_fields(self, api_client, sample_tickers):
        response = api_client.get("/api/tickers/PETR4/")
        data = response.json()
        assert "symbol" in data
        assert "name" in data
        assert "sector" in data
        assert "type" in data
        assert "logo" in data

    def test_case_insensitive_lookup(self, api_client, sample_tickers):
        response = api_client.get("/api/tickers/petr4/")
        assert response.status_code == 200
        assert response.json()["symbol"] == "PETR4"

    def test_returns_404_for_unknown_ticker(self, api_client, sample_tickers):
        response = api_client.get("/api/tickers/ZZZZ3/")
        assert response.status_code == 404

    def test_has_cache_header(self, api_client, sample_tickers):
        response = api_client.get("/api/tickers/PETR4/")
        assert "max-age=3600" in response["Cache-Control"]

    def test_uses_display_name_when_available(self, api_client, db):
        Ticker.objects.create(
            symbol="WEGE3", name="WEG S.A.", display_name="WEG", sector="Tech", type="stock",
        )
        response = api_client.get("/api/tickers/WEGE3/")
        assert response.json()["name"] == "WEG"

    def test_excludes_non_stock_types(self, api_client, db):
        Ticker.objects.create(symbol="KNRI11", name="Kinea Renda", type="fund")
        response = api_client.get("/api/tickers/KNRI11/")
        assert response.status_code == 404
