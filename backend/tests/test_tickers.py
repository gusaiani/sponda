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
