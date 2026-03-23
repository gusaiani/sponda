"""Tests for the fundamentals (per-year) aggregation logic."""
from datetime import date
from decimal import Decimal

import pytest

from quotes.fundamentals import compute_fundamentals
from quotes.models import BalanceSheet, IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings


@pytest.fixture
def multi_year_balance_sheets(db):
    """Create balance sheets for multiple years with all fields."""
    records = []
    # 2024 — full year (Q4 latest)
    for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
        records.append(BalanceSheet(
            ticker="WEGE3", end_date=date(2024, month, day),
            total_debt=10_000_000_000, total_lease=1_000_000_000,
            total_liabilities=20_000_000_000, stockholders_equity=15_000_000_000,
            current_assets=12_000_000_000, current_liabilities=8_000_000_000,
        ))
    # 2023 — full year
    for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
        records.append(BalanceSheet(
            ticker="WEGE3", end_date=date(2023, month, day),
            total_debt=8_000_000_000, total_lease=800_000_000,
            total_liabilities=16_000_000_000, stockholders_equity=12_000_000_000,
            current_assets=10_000_000_000, current_liabilities=7_000_000_000,
        ))
    BalanceSheet.objects.bulk_create(records)
    return records


@pytest.fixture
def multi_year_earnings(db):
    """Create earnings for multiple years with revenue."""
    records = []
    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    # 2024
    for i, (month, day) in enumerate(quarter_ends):
        records.append(QuarterlyEarnings(
            ticker="WEGE3", end_date=date(2024, month, day),
            net_income=1_000_000_000 * (i + 1),
            revenue=5_000_000_000 * (i + 1),
        ))
    # 2023
    for i, (month, day) in enumerate(quarter_ends):
        records.append(QuarterlyEarnings(
            ticker="WEGE3", end_date=date(2023, month, day),
            net_income=800_000_000 * (i + 1),
            revenue=4_000_000_000 * (i + 1),
        ))
    QuarterlyEarnings.objects.bulk_create(records)
    return records


@pytest.fixture
def multi_year_cash_flows(db):
    """Create cash flows for multiple years with dividends."""
    records = []
    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    # 2024
    for i, (month, day) in enumerate(quarter_ends):
        records.append(QuarterlyCashFlow(
            ticker="WEGE3", end_date=date(2024, month, day),
            operating_cash_flow=2_000_000_000,
            investment_cash_flow=-800_000_000,
            dividends_paid=-500_000_000,
        ))
    # 2023
    for i, (month, day) in enumerate(quarter_ends):
        records.append(QuarterlyCashFlow(
            ticker="WEGE3", end_date=date(2023, month, day),
            operating_cash_flow=1_500_000_000,
            investment_cash_flow=-600_000_000,
            dividends_paid=-400_000_000,
        ))
    QuarterlyCashFlow.objects.bulk_create(records)
    return records


@pytest.fixture
def ipca_entries(db):
    """Create IPCA entries for 2023 and 2024."""
    entries = [
        IPCAIndex(date=date(2023, 12, 1), annual_rate=Decimal("4.62")),
        IPCAIndex(date=date(2024, 12, 1), annual_rate=Decimal("4.83")),
    ]
    IPCAIndex.objects.bulk_create(entries)
    return entries


class TestComputeFundamentals:
    def test_returns_years_sorted_descending(
        self, multi_year_balance_sheets, multi_year_earnings, multi_year_cash_flows, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        years = [row["year"] for row in result]
        assert years == [2024, 2023]

    def test_balance_sheet_uses_latest_quarter(
        self, multi_year_balance_sheets, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        year_2024 = result[0]
        assert year_2024["balanceSheetDate"] == "2024-12-31"

    def test_debt_ex_lease_calculation(
        self, multi_year_balance_sheets, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        year_2024 = result[0]
        # total_debt=10B, total_lease=1B → debt_ex_lease=9B
        assert year_2024["debtExLease"] == 9_000_000_000

    def test_ratios(self, multi_year_balance_sheets, ipca_entries):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        year_2024 = result[0]
        # debt_ex_lease=9B / equity=15B = 0.6
        assert year_2024["debtToEquity"] == 0.6
        # total_liabilities=20B / equity=15B = 1.33
        assert year_2024["liabilitiesToEquity"] == 1.33
        # current_assets=12B / current_liabilities=8B = 1.5
        assert year_2024["currentRatio"] == 1.5

    def test_earnings_summed_per_year(
        self, multi_year_earnings, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        year_2024 = result[0]
        # net_income: 1B + 2B + 3B + 4B = 10B
        assert year_2024["netIncome"] == 10_000_000_000
        # revenue: 5B + 10B + 15B + 20B = 50B
        assert year_2024["revenue"] == 50_000_000_000

    def test_cash_flows_summed_per_year(
        self, multi_year_cash_flows, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        year_2024 = result[0]
        # operating: 2B * 4 = 8B
        assert year_2024["operatingCashFlow"] == 8_000_000_000
        # fcf: (2B - 0.8B) * 4 = 4.8B
        assert year_2024["fcf"] == 4_800_000_000
        # dividends: -500M * 4 = -2B
        assert year_2024["dividendsPaid"] == -2_000_000_000

    def test_quarters_count(
        self, multi_year_earnings, multi_year_cash_flows, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        assert result[0]["quarters"] == 4  # 2024
        assert result[1]["quarters"] == 4  # 2023

    def test_partial_year(self, db, ipca_entries):
        """A year with only 2 quarters should report quarters=2."""
        for month, day in [(3, 31), (6, 30)]:
            QuarterlyEarnings.objects.create(
                ticker="PART3", end_date=date(2024, month, day),
                net_income=1_000_000_000, revenue=5_000_000_000,
            )
        result = compute_fundamentals("PART3", market_cap=None, current_price=None)
        assert result[0]["quarters"] == 2

    def test_ipca_adjustment_applied(
        self, multi_year_earnings, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        year_2023 = result[1]
        # 2023 earnings should be adjusted by 2024 IPCA factor
        # factor = 1 + 4.83/100 = 1.0483
        expected_net_income = float(Decimal("8000000000") * Decimal("1.0483"))
        assert abs(year_2023["netIncomeAdjusted"] - expected_net_income) < 1

    def test_empty_ticker_returns_empty_list(self, db):
        result = compute_fundamentals("NONE3", market_cap=None, current_price=None)
        assert result == []

    def test_null_values_handled_gracefully(self, db, ipca_entries):
        """Balance sheet with all null values should produce null ratios."""
        BalanceSheet.objects.create(
            ticker="NULL3", end_date=date(2024, 12, 31),
            total_debt=None, total_lease=None,
            total_liabilities=None, stockholders_equity=None,
            current_assets=None, current_liabilities=None,
        )
        result = compute_fundamentals("NULL3", market_cap=None, current_price=None)
        assert len(result) == 1
        assert result[0]["debtToEquity"] is None
        assert result[0]["liabilitiesToEquity"] is None
        assert result[0]["currentRatio"] is None

    def test_ticker_case_insensitive(
        self, multi_year_balance_sheets, ipca_entries
    ):
        result = compute_fundamentals("wege3", market_cap=None, current_price=None)
        assert len(result) == 2
