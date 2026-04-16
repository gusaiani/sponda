"""Tests for compute_company_indicators — the service used by the screener + alerts."""
from datetime import date
from decimal import Decimal

import pytest

from quotes.indicators import compute_company_indicators
from quotes.models import BalanceSheet, IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings


@pytest.fixture
def ipca_stub(db):
    """Populate IPCA with annual_rate=0 for 2010-2025 so inflation adjustment is a no-op."""
    for year in range(2010, 2027):
        IPCAIndex.objects.update_or_create(
            date=date(year, 12, 31), defaults={"annual_rate": Decimal("0")},
        )


@pytest.fixture
def earnings_petr4(ipca_stub):
    """10 years of flat quarterly earnings (net_income = 2.5B each quarter → 10B/year)."""
    for year in range(2016, 2026):
        for quarter_end in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="PETR4",
                end_date=date(year, *quarter_end),
                net_income=2_500_000_000,
            )


@pytest.fixture
def cashflow_petr4(ipca_stub):
    """10 years of flat quarterly cash flow (OCF - InvCF = 2B/quarter → 8B/year FCF)."""
    for year in range(2016, 2026):
        for quarter_end in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyCashFlow.objects.create(
                ticker="PETR4",
                end_date=date(year, *quarter_end),
                operating_cash_flow=3_000_000_000,
                investment_cash_flow=-1_000_000_000,
                dividends_paid=0,
            )


@pytest.fixture
def balance_petr4(db):
    return BalanceSheet.objects.create(
        ticker="PETR4",
        end_date=date(2025, 9, 30),
        total_debt=300_000_000_000,
        total_lease=50_000_000_000,
        total_liabilities=500_000_000_000,
        stockholders_equity=200_000_000_000,
        current_assets=150_000_000_000,
        current_liabilities=100_000_000_000,
    )


@pytest.mark.django_db
class TestComputeCompanyIndicators:
    def test_returns_dict_with_all_snapshot_fields(
        self, earnings_petr4, cashflow_petr4, balance_petr4,
    ):
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        # Returns all fields the snapshot model expects, keyed by model field name
        expected_keys = {
            "pe10", "pfcf10", "peg", "pfcf_peg",
            "debt_to_equity", "debt_ex_lease_to_equity",
            "liabilities_to_equity", "current_ratio",
            "debt_to_avg_earnings", "debt_to_avg_fcf",
            "market_cap", "current_price",
        }
        assert expected_keys.issubset(result.keys())

    def test_computes_pe10_from_market_cap_and_average_earnings(
        self, earnings_petr4, balance_petr4,
    ):
        # avg earnings = 10B/year for 10 years → PE10 = 400B / 10B = 40
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        assert result["pe10"] == Decimal("40")

    def test_computes_pfcf10_from_market_cap_and_average_fcf(
        self, cashflow_petr4, balance_petr4,
    ):
        # avg FCF = 8B/year → PFCF10 = 400B / 8B = 50
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        assert result["pfcf10"] == Decimal("50")

    def test_computes_leverage_ratios_from_balance_sheet(self, balance_petr4):
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        assert result["debt_to_equity"] == Decimal("1.5")  # 300B / 200B
        assert result["liabilities_to_equity"] == Decimal("2.5")  # 500B / 200B
        assert result["current_ratio"] == Decimal("1.5")  # 150B / 100B
        # debt_ex_lease = 300B - 50B = 250B → 250B / 200B = 1.25
        assert result["debt_ex_lease_to_equity"] == Decimal("1.25")

    def test_computes_debt_coverage_ratios(
        self, earnings_petr4, cashflow_petr4, balance_petr4,
    ):
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        # avg earnings = 10B/year, total_debt = 300B → debt/avg_earnings = 30
        assert result["debt_to_avg_earnings"] == Decimal("30")
        # avg FCF = 8B/year, total_debt = 300B → debt/avg_fcf = 37.5
        assert result["debt_to_avg_fcf"] == Decimal("37.5")

    def test_passes_through_market_cap_and_current_price(self, db):
        result = compute_company_indicators(
            "NEW3", market_cap=123_000_000_000, current_price=Decimal("42.50"),
        )
        assert result["market_cap"] == 123_000_000_000
        assert result["current_price"] == Decimal("42.50")

    def test_current_price_optional(self, db):
        result = compute_company_indicators("NEW3", market_cap=100_000_000)
        assert result["current_price"] is None

    def test_returns_nulls_when_data_missing(self, db):
        # No earnings, no cash flow, no balance sheet — every indicator is None
        result = compute_company_indicators("EMPTY3", market_cap=None)
        assert result["pe10"] is None
        assert result["pfcf10"] is None
        assert result["debt_to_equity"] is None
        assert result["current_ratio"] is None
        assert result["debt_to_avg_earnings"] is None
        assert result["market_cap"] is None

    def test_ticker_case_insensitive(self, earnings_petr4, balance_petr4):
        upper = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        lower = compute_company_indicators("petr4", market_cap=400_000_000_000)
        assert upper["pe10"] == lower["pe10"]

    def test_does_not_raise_on_missing_market_cap(self, earnings_petr4):
        # Screener snapshot refresh should tolerate tickers whose market cap we don't know
        result = compute_company_indicators("PETR4", market_cap=None)
        assert result["pe10"] is None
        assert result["pfcf10"] is None
