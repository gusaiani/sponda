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
        market_cap=400_000_000_000, country="BR",
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
        market_cap=200_000_000_000, country="BR",
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
        market_cap=1_000_000_000, country="US",
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

    def test_filter_by_single_sector(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sector=Oil")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4"}

    def test_filter_by_multiple_sectors(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sector=Oil,Industrial")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4", "WEGE3"}

    def test_blank_sector_param_is_ignored(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sector=")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4", "WEGE3", "MICRO3"}

    def test_sector_filter_combines_with_indicator_filters(
        self, api_client, snapshot_universe,
    ):
        # MICRO3 has PE10 = 12, sector = Retail. Filtering Retail + PE10 <= 10
        # should yield no rows.
        response = api_client.get("/api/screener/?sector=Retail&pe10_max=10")
        assert response.json()["results"] == []

    def test_unknown_sector_yields_no_rows(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?sector=NoSuchSector")
        body = response.json()
        assert body["count"] == 0
        assert body["results"] == []


@pytest.mark.django_db
class TestScreenerCountryFilter:
    def test_filter_by_single_country(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?country=BR")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4", "WEGE3"}

    def test_filter_by_multiple_countries(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?country=BR,US")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4", "WEGE3", "MICRO3"}

    def test_blank_country_param_is_ignored(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?country=")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4", "WEGE3", "MICRO3"}

    def test_country_filter_combines_with_indicator_filters(
        self, api_client, snapshot_universe,
    ):
        # Only MICRO3 is US, and has PE10 = 12. Filtering US + PE10 <= 10 → none.
        response = api_client.get("/api/screener/?country=US&pe10_max=10")
        assert response.json()["results"] == []

    def test_unknown_country_yields_no_rows(self, api_client, snapshot_universe):
        response = api_client.get("/api/screener/?country=XX")
        assert response.json() == {"count": 0, "results": []}

    def test_country_combines_with_sector(self, api_client, snapshot_universe):
        # Two BR tickers with different sectors; filter narrows to one.
        response = api_client.get("/api/screener/?country=BR&sector=Oil")
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert tickers == {"PETR4"}


@pytest.mark.django_db
class TestScreenerCountriesAPI:
    def test_returns_distinct_countries_present_in_data(
        self, api_client, snapshot_universe,
    ):
        response = api_client.get("/api/screener/countries/")
        assert response.status_code == 200
        body = response.json()
        assert sorted(body["countries"]) == ["BR", "US"]

    def test_excludes_blank_countries(self, api_client, db):
        Ticker.objects.create(symbol="WITH", name="With", country="BR")
        Ticker.objects.create(symbol="BLANK", name="Blank", country="")
        response = api_client.get("/api/screener/countries/")
        assert response.json()["countries"] == ["BR"]

    def test_countries_are_unique(self, api_client, db):
        Ticker.objects.create(symbol="A", name="A", country="BR")
        Ticker.objects.create(symbol="B", name="B", country="BR")
        Ticker.objects.create(symbol="C", name="C", country="US")
        response = api_client.get("/api/screener/countries/")
        assert sorted(response.json()["countries"]) == ["BR", "US"]


@pytest.mark.django_db
class TestScreenerSectorsAPI:
    def test_returns_distinct_sectors_present_in_data(
        self, api_client, snapshot_universe,
    ):
        response = api_client.get("/api/screener/sectors/")
        assert response.status_code == 200
        body = response.json()
        assert sorted(body["sectors"]) == ["Industrial", "Oil", "Retail"]

    def test_excludes_blank_sectors(self, api_client, db):
        Ticker.objects.create(symbol="WITH", name="With", sector="Tech")
        Ticker.objects.create(symbol="EMPTY", name="Empty", sector="")
        response = api_client.get("/api/screener/sectors/")
        assert response.json()["sectors"] == ["Tech"]

    def test_sectors_are_unique(self, api_client, db):
        Ticker.objects.create(symbol="A", name="A", sector="Tech")
        Ticker.objects.create(symbol="B", name="B", sector="Tech")
        Ticker.objects.create(symbol="C", name="C", sector="Health")
        response = api_client.get("/api/screener/sectors/")
        assert sorted(response.json()["sectors"]) == ["Health", "Tech"]
