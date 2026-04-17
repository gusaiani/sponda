"""Tests for the screener API endpoint — filter companies by indicator thresholds."""
from decimal import Decimal

import pytest
from django.test import Client

from quotes.models import IndicatorSnapshot, Ticker


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def snapshot_universe(db):
    """Three companies with distinct indicator profiles for filter/sort testing."""
    # Cheap value stock: low PE10, moderate leverage
    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", display_name="Petrobras",
        sector="Oil", type="stock", logo="https://example.com/petr4.png",
        market_cap=400_000_000_000,
    )
    IndicatorSnapshot.objects.create(
        ticker="PETR4",
        pe10=Decimal("6.5"), pfcf10=Decimal("8.0"), peg=Decimal("0.5"),
        debt_to_equity=Decimal("1.2"), liabilities_to_equity=Decimal("2.0"),
        current_ratio=Decimal("1.4"),
        debt_to_avg_earnings=Decimal("3.0"), debt_to_avg_fcf=Decimal("4.5"),
        market_cap=400_000_000_000, current_price=Decimal("35.75"),
    )

    # Expensive growth stock: high PE10, low leverage
    Ticker.objects.create(
        symbol="WEGE3", name="Weg", display_name="WEG",
        sector="Industrial", type="stock", logo="https://example.com/wege3.png",
        market_cap=200_000_000_000,
    )
    IndicatorSnapshot.objects.create(
        ticker="WEGE3",
        pe10=Decimal("35.0"), pfcf10=Decimal("40.0"), peg=Decimal("2.5"),
        debt_to_equity=Decimal("0.3"), liabilities_to_equity=Decimal("0.8"),
        current_ratio=Decimal("2.5"),
        debt_to_avg_earnings=Decimal("1.0"), debt_to_avg_fcf=Decimal("1.5"),
        market_cap=200_000_000_000, current_price=Decimal("42.00"),
    )

    # Small-cap with high leverage
    Ticker.objects.create(
        symbol="MICRO3", name="Micro", display_name="Micro",
        sector="Retail", type="stock", logo="",
        market_cap=1_000_000_000,
    )
    IndicatorSnapshot.objects.create(
        ticker="MICRO3",
        pe10=Decimal("12.0"), pfcf10=Decimal("15.0"), peg=Decimal("1.2"),
        debt_to_equity=Decimal("4.0"), liabilities_to_equity=Decimal("6.0"),
        current_ratio=Decimal("0.8"),
        debt_to_avg_earnings=Decimal("10.0"), debt_to_avg_fcf=Decimal("12.0"),
        market_cap=1_000_000_000, current_price=Decimal("2.50"),
    )


@pytest.mark.django_db
class TestScreenerAPI:
    def test_returns_all_snapshots_when_no_filters(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 3
        tickers = {row["ticker"] for row in body["results"]}
        assert tickers == {"PETR4", "WEGE3", "MICRO3"}

    def test_includes_ticker_metadata_in_each_row(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/")
        row = next(r for r in response.json()["results"] if r["ticker"] == "PETR4")
        assert row["name"] == "Petrobras"
        assert row["sector"] == "Oil"
        assert row["logo"] == "https://example.com/petr4.png"
        # Indicator values serialized as numbers (strings also acceptable for Decimal)
        assert Decimal(str(row["pe10"])) == Decimal("6.5")
        assert row["market_cap"] == 400_000_000_000

    def test_filter_pe10_max(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?pe10_max=10")
        tickers = {r["ticker"] for r in response.json()["results"]}
        # Only PETR4 has PE10 <= 10
        assert tickers == {"PETR4"}

    def test_filter_pe10_min(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?pe10_min=20")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"WEGE3"}

    def test_filter_pe10_range(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?pe10_min=10&pe10_max=20")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"MICRO3"}

    def test_filter_multiple_indicators_combined(self, api_client, snapshot_universe):
        # PE10 <= 20 AND debt_to_equity <= 1.5 → only PETR4
        response = api_client.get(
            "/api/screener/?pe10_max=20&debt_to_equity_max=1.5",
        )
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4"}

    def test_market_cap_filter_is_ignored(self, api_client, snapshot_universe):
        """market_cap is deliberately not filterable — the param is silently
        ignored so older clients or URL shares don't break, but no filter is
        applied. All three tickers are returned."""
        response = api_client.get("/api/screener/?market_cap_min=100000000000")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4", "WEGE3", "MICRO3"}

    def test_filter_current_ratio_min(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?current_ratio_min=1.5")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"WEGE3"}

    def test_sort_by_pe10_ascending_by_default(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sort=pe10")
        ordered = [r["ticker"] for r in response.json()["results"]]
        assert ordered == ["PETR4", "MICRO3", "WEGE3"]

    def test_sort_by_pe10_descending(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sort=-pe10")
        ordered = [r["ticker"] for r in response.json()["results"]]
        assert ordered == ["WEGE3", "MICRO3", "PETR4"]

    def test_sort_by_market_cap_descending(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sort=-market_cap")
        ordered = [r["ticker"] for r in response.json()["results"]]
        assert ordered == ["PETR4", "WEGE3", "MICRO3"]

    def test_invalid_sort_field_returns_400(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sort=evil; DROP TABLE")
        assert response.status_code == 400

    def test_limit_caps_results(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?limit=2&sort=pe10")
        body = response.json()
        # count reflects total matching, not the page
        assert body["count"] == 3
        assert len(body["results"]) == 2
        assert [r["ticker"] for r in body["results"]] == ["PETR4", "MICRO3"]

    def test_offset_skips_rows(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sort=pe10&offset=1&limit=5")
        ordered = [r["ticker"] for r in response.json()["results"]]
        assert ordered == ["MICRO3", "WEGE3"]

    def test_excludes_rows_missing_the_filtered_indicator(self, api_client, db):
        # If a snapshot has a null for the filtered field, it should NOT pass
        # the filter (consistent with "<= threshold" semantics).
        Ticker.objects.create(symbol="T1", name="T1", market_cap=100_000_000_000)
        Ticker.objects.create(symbol="T2", name="T2", market_cap=100_000_000_000)
        IndicatorSnapshot.objects.create(
            ticker="T1", pe10=Decimal("5"), market_cap=100_000_000_000,
        )
        IndicatorSnapshot.objects.create(
            ticker="T2", pe10=None, market_cap=100_000_000_000,
        )
        response = api_client.get("/api/screener/?pe10_max=10")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"T1"}

    def test_invalid_numeric_filter_returns_400(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?pe10_max=not-a-number")
        assert response.status_code == 400

    def test_unknown_filter_field_is_ignored(self, api_client, snapshot_universe):
        # Unknown params shouldn't break the request — just ignored.
        response = api_client.get("/api/screener/?pe10_max=100&bogus_field_max=1")
        assert response.status_code == 200
        assert response.json()["count"] == 3
