"""Tests for the DB-only company payloads behind the markdown pages.

The whole markdown feature rests on one claim: rendering a company page
costs two indexed reads and never touches a data provider. These tests
pin that claim, so a future refactor that reaches for
``_compute_quote_payload`` fails here instead of on the BRAPI invoice.
"""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from quotes.company_snapshot import (
    company_fundamentals,
    company_snapshot,
    company_snapshots,
)
from quotes.models import (
    BalanceSheet,
    IndicatorSnapshot,
    IPCAIndex,
    QuarterlyCashFlow,
    QuarterlyEarnings,
    Ticker,
)
from quotes.screener import SCREENER_FILTERABLE_FIELDS


@pytest.fixture
def snapshot_universe(db):
    """One fully populated company, one with a Ticker but no snapshot, and
    one non-stock instrument that must stay invisible to every accessor."""
    Ticker.objects.create(
        symbol="PETR4", name="Petroleo Brasileiro", display_name="Petrobras",
        sector="Oil", type="stock", country="BR", reported_currency="BRL",
        market_cap=400_000_000_000,
    )
    IndicatorSnapshot.objects.create(
        ticker="PETR4",
        pe10=Decimal("6.5"), pe_years_available=15,
        pfcf10=Decimal("8.0"), peg=Decimal("0.5"), pfcf_peg=Decimal("0.7"),
        debt_to_equity=Decimal("1.2"), debt_ex_lease_to_equity=Decimal("1.0"),
        liabilities_to_equity=Decimal("2.0"), current_ratio=Decimal("1.4"),
        debt_to_avg_earnings=Decimal("3.0"), debt_to_avg_fcf=Decimal("4.5"),
        market_cap=400_000_000_000, current_price=Decimal("35.75"),
    )

    Ticker.objects.create(
        symbol="WEGE3", name="Weg", display_name="WEG",
        sector="Industrial", type="stock", country="BR", reported_currency="BRL",
        market_cap=200_000_000_000,
    )
    IndicatorSnapshot.objects.create(
        ticker="WEGE3",
        pe10=Decimal("35.0"), pe_years_available=12,
        market_cap=200_000_000_000, current_price=Decimal("52.10"),
    )

    # Known ticker, no snapshot row: the refresh job only snapshots tickers
    # with a market cap, so this state is common in production.
    Ticker.objects.create(
        symbol="NOSNAP3", name="No Snapshot", type="stock", country="BR",
    )

    # Funds and ETFs are out of scope for company pages.
    Ticker.objects.create(symbol="BOVA11", name="Bova", type="fund", country="BR")
    IndicatorSnapshot.objects.create(ticker="BOVA11", pe10=Decimal("9.9"))


# --- company_snapshot ---------------------------------------------------

@pytest.mark.django_db
class TestCompanySnapshot:
    def test_happy_path(self, snapshot_universe):
        result = company_snapshot("PETR4")
        assert result["symbol"] == "PETR4"
        assert result["name"] == "Petrobras"
        assert result["sector"] == "Oil"
        assert result["country"] == "BR"
        assert result["reported_currency"] == "BRL"
        assert result["pe10"] == 6.5
        assert isinstance(result["pe10"], float)

    def test_carries_every_screener_field(self, snapshot_universe):
        result = company_snapshot("PETR4")
        for field in SCREENER_FILTERABLE_FIELDS:
            assert field in result, f"{field} missing from company_snapshot"

    def test_exposes_computed_at_so_pages_can_date_themselves(self, snapshot_universe):
        assert company_snapshot("PETR4")["computed_at"] is not None

    def test_json_dumpable(self, snapshot_universe):
        json.dumps(company_snapshot("PETR4"))

    def test_case_insensitive(self, snapshot_universe):
        assert company_snapshot("petr4")["symbol"] == "PETR4"

    def test_unknown_symbol_is_none(self, snapshot_universe):
        assert company_snapshot("NOPE99") is None

    def test_missing_snapshot_is_none(self, snapshot_universe):
        assert company_snapshot("NOSNAP3") is None

    def test_non_stock_is_none(self, snapshot_universe):
        assert company_snapshot("BOVA11") is None

    def test_blank_symbol_is_none(self, snapshot_universe):
        assert company_snapshot("") is None
        assert company_snapshot(None) is None

    def test_null_indicators_stay_null(self, snapshot_universe):
        result = company_snapshot("WEGE3")
        assert result["pe10"] == 35.0
        assert result["peg"] is None

    def test_falls_back_to_name_when_display_name_blank(self, snapshot_universe):
        Ticker.objects.filter(symbol="PETR4").update(display_name="")
        assert company_snapshot("PETR4")["name"] == "Petroleo Brasileiro"


# --- company_snapshots (bulk) -------------------------------------------

@pytest.mark.django_db
class TestCompanySnapshots:
    def test_returns_dict_keyed_by_upper_symbol(self, snapshot_universe):
        result = company_snapshots(["petr4", "WEGE3"])
        assert set(result) == {"PETR4", "WEGE3"}
        assert result["PETR4"]["pe10"] == 6.5

    def test_skips_symbols_without_a_snapshot(self, snapshot_universe):
        result = company_snapshots(["PETR4", "NOSNAP3", "NOPE99"])
        assert set(result) == {"PETR4"}

    def test_empty_input(self, snapshot_universe):
        assert company_snapshots([]) == {}

    def test_is_two_queries_regardless_of_symbol_count(
        self, snapshot_universe, django_assert_num_queries,
    ):
        with django_assert_num_queries(2):
            company_snapshots(["PETR4", "WEGE3", "NOSNAP3"])


# --- company_fundamentals -----------------------------------------------

@pytest.fixture
def statements(db, snapshot_universe):
    """Two years of statements for PETR4, straight in the DB."""
    for year in (2024, 2025):
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            QuarterlyEarnings.objects.create(
                ticker="PETR4", end_date=date(year, month, day),
                net_income=10_000_000_000, revenue=50_000_000_000,
            )
            QuarterlyCashFlow.objects.create(
                ticker="PETR4", end_date=date(year, month, day),
                operating_cash_flow=20_000_000_000,
                investment_cash_flow=-8_000_000_000,
            )
        BalanceSheet.objects.create(
            ticker="PETR4", end_date=date(year, 12, 31),
            total_debt=100_000_000_000, stockholders_equity=300_000_000_000,
            total_liabilities=500_000_000_000,
        )
        IPCAIndex.objects.create(date=date(year, 12, 1), annual_rate=Decimal("4.5"))


@pytest.mark.django_db
class TestCompanyFundamentals:
    def test_returns_years_descending(self, statements):
        result = company_fundamentals("PETR4")
        years = [row["year"] for row in result["years"]]
        assert years == sorted(years, reverse=True)

    def test_carries_currencies(self, statements):
        result = company_fundamentals("PETR4")
        assert result["listingCurrency"] == "BRL"
        assert result["reportedCurrency"] == "BRL"

    def test_unknown_symbol_is_none(self, statements):
        assert company_fundamentals("NOPE99") is None

    def test_json_dumpable(self, statements):
        json.dumps(company_fundamentals("PETR4"))


# --- the load-bearing claim: no provider calls --------------------------

PROVIDER_ENTRY_POINTS = (
    "fetch_quote",
    "fetch_quotes_batch",
    "fetch_dividends",
    "fetch_historical_prices",
    "sync_earnings",
    "sync_cash_flows",
    "sync_balance_sheets",
)


@pytest.mark.django_db
class TestNoProviderCalls:
    """Every markdown-facing accessor must be pure DB.

    The daily lookup cap exists to protect the BRAPI/FMP budget. These
    accessors are deliberately exempt from that cap, which is only safe
    for as long as they never reach a provider.
    """

    def _assert_pure(self, call):
        with patch.multiple(
            "quotes.providers", **{name: None for name in PROVIDER_ENTRY_POINTS},
        ) as mocks:
            call()
        for name, mock in mocks.items():
            assert not mock.called, f"quotes.providers.{name} was called"

    def test_company_snapshot_is_pure(self, snapshot_universe):
        self._assert_pure(lambda: company_snapshot("PETR4"))

    def test_company_snapshots_is_pure(self, snapshot_universe):
        self._assert_pure(lambda: company_snapshots(["PETR4", "WEGE3"]))

    def test_company_fundamentals_is_pure(self, statements):
        self._assert_pure(lambda: company_fundamentals("PETR4"))


# --- the HTTP endpoint --------------------------------------------------

@pytest.mark.django_db
class TestTickerIndicatorsView:
    def _url(self, symbol):
        return reverse("ticker-indicators", args=[symbol])

    def test_returns_payload(self, client, snapshot_universe):
        response = client.get(self._url("PETR4"))
        assert response.status_code == 200
        assert response.json()["pe10"] == 6.5

    def test_lowercase_symbol(self, client, snapshot_universe):
        assert client.get(self._url("petr4")).status_code == 200

    def test_unknown_symbol_404s(self, client, snapshot_universe):
        assert client.get(self._url("NOPE99")).status_code == 404

    def test_is_publicly_cacheable(self, client, snapshot_universe):
        response = client.get(self._url("PETR4"))
        assert "public" in response["Cache-Control"]

    def test_bulk_form(self, client, snapshot_universe):
        response = client.get(self._url("PETR4"), {"symbols": "wege3,NOPE99"})
        payload = response.json()
        assert set(payload["companies"]) == {"WEGE3"}

    def test_fundamentals_flag(self, client, statements):
        response = client.get(self._url("PETR4"), {"fundamentals": "1"})
        assert "fundamentals" in response.json()

    def test_omits_fundamentals_by_default(self, client, statements):
        assert "fundamentals" not in client.get(self._url("PETR4")).json()

    def test_analysis_flag_carries_the_stored_markdown(self, client, snapshot_universe):
        from quotes.models import CompanyAnalysis
        CompanyAnalysis.objects.create(
            ticker="PETR4", content="## Tese\n\nTexto.", data_quarter="2026Q2",
        )
        payload = client.get(self._url("PETR4"), {"analysis": "1"}).json()
        assert payload["analysis"]["content"].startswith("## Tese")

    def test_analysis_flag_returns_null_rather_than_404ing(self, client, snapshot_universe):
        """A company with no analysis must still answer 200.

        Most companies have none. A 404 is not cacheable by the Next data
        cache, so a 404 here would mean one Django round trip per markdown
        page view for the whole catalogue, forever.
        """
        response = client.get(self._url("PETR4"), {"analysis": "1"})
        assert response.status_code == 200
        assert response.json()["analysis"] is None

    def test_omits_analysis_by_default(self, client, snapshot_universe):
        assert "analysis" not in client.get(self._url("PETR4")).json()

    def test_never_records_a_lookup(self, client, snapshot_universe):
        """The endpoint sits outside the daily cap on purpose."""
        from quotes.models import LookupLog
        client.get(self._url("PETR4"))
        assert LookupLog.objects.count() == 0

    def test_survives_past_the_anonymous_cap(self, client, snapshot_universe, settings):
        """20 anon lookups/day must not gate a page a crawler is meant to sweep."""
        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 0
        assert client.get(self._url("PETR4")).status_code == 200


# --- the indicator catalogue over HTTP ----------------------------------

@pytest.mark.django_db
class TestIndicatorCatalogueView:
    """The glossary the screener markdown page is generated from.

    The catalogue already exists as the single source of truth for the MCP
    tools (``assistant.tools.INDICATOR_CATALOGUE``). Exposing it over HTTP
    means the markdown pages describe the indicators from that same list
    rather than a hand-copied TypeScript duplicate.
    """

    def _url(self):
        return reverse("assistant-indicators")

    def test_returns_the_catalogue(self, client, snapshot_universe):
        payload = client.get(self._url()).json()
        keys = {entry["key"] for entry in payload["indicators"]}
        assert set(SCREENER_FILTERABLE_FIELDS) <= keys

    def test_every_entry_carries_a_definition(self, client, snapshot_universe):
        for entry in client.get(self._url()).json()["indicators"]:
            assert entry["definition"]
            assert entry["direction"] in ("lower_is_better", "higher_is_better", "neutral")

    def test_lists_countries_and_sectors_present_in_the_data(self, client, snapshot_universe):
        payload = client.get(self._url()).json()
        assert "BR" in payload["countries"]
        assert "Oil" in payload["sectors"]

    def test_names_what_sponda_does_not_track(self, client, snapshot_universe):
        assert client.get(self._url()).json()["unsupported_examples"]

    def test_is_publicly_cacheable(self, client, snapshot_universe):
        assert "public" in client.get(self._url())["Cache-Control"]


@pytest.mark.django_db
class TestCompanySnapshotDebtCoverageWindows:
    def test_carries_every_debt_coverage_window(self, snapshot_universe):
        IndicatorSnapshot.objects.filter(ticker="PETR4").update(
            debt_to_avg_earnings_5=Decimal("9.0"),
        )
        result = company_snapshot("PETR4")
        for field in IndicatorSnapshot.DEBT_COVERAGE_WINDOW_FIELDS:
            assert field in result, f"{field} missing from company_snapshot"
        assert result["debt_to_avg_earnings_5"] == 9.0
        assert result["debt_to_avg_fcf_5"] is None
