"""Tests for the fundamentals (per-year) aggregation logic."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from quotes.fundamentals import (
    aggregate_proventos_by_year,
    compute_fundamentals,
    compute_quarterly_balance_ratios,
)
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

    def test_ipca_adjustment_applied_to_balance_sheet(
        self, multi_year_balance_sheets, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        year_2023 = result[1]
        # 2023 balance sheet should be adjusted by IPCA factor
        # factor = 1 + 4.83/100 = 1.0483
        ipca_factor = Decimal("1.0483")

        # debt_ex_lease for 2023: total_debt=8B - total_lease=800M = 7.2B
        expected_debt_ex_lease = float(Decimal("7200000000") * ipca_factor)
        assert abs(year_2023["debtExLeaseAdjusted"] - expected_debt_ex_lease) < 1

        expected_total_liabilities = float(Decimal("16000000000") * ipca_factor)
        assert abs(year_2023["totalLiabilitiesAdjusted"] - expected_total_liabilities) < 1

        expected_equity = float(Decimal("12000000000") * ipca_factor)
        assert abs(year_2023["stockholdersEquityAdjusted"] - expected_equity) < 1

    def test_ipca_balance_sheet_null_when_values_null(self, db, ipca_entries):
        """Balance sheet with null values should produce null adjusted values."""
        BalanceSheet.objects.create(
            ticker="NULB3", end_date=date(2024, 12, 31),
            total_debt=None, total_lease=None,
            total_liabilities=None, stockholders_equity=None,
            current_assets=None, current_liabilities=None,
        )
        result = compute_fundamentals("NULB3", market_cap=None, current_price=None)
        assert result[0]["debtExLeaseAdjusted"] is None
        assert result[0]["totalLiabilitiesAdjusted"] is None
        assert result[0]["stockholdersEquityAdjusted"] is None

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

    def test_market_cap_historical(
        self, multi_year_balance_sheets, multi_year_earnings, ipca_entries
    ):
        """Historical years get market cap computed from year-end price * shares outstanding."""
        historical_prices = [
            {"date": int(datetime(2023, 12, 31, tzinfo=timezone.utc).timestamp()), "adjustedClose": 40.0},
            {"date": int(datetime(2024, 12, 31, tzinfo=timezone.utc).timestamp()), "adjustedClose": 50.0},
        ]
        # market_cap=200B, current_price=50 → shares_outstanding=4B
        result = compute_fundamentals(
            "WEGE3",
            market_cap=200_000_000_000,
            current_price=50.0,
            historical_prices=historical_prices,
        )
        # 2024 (latest year): uses current market_cap directly
        assert result[0]["marketCap"] == 200_000_000_000
        # 2023: year_end_price=40 * shares_outstanding=4B = 160B
        assert result[1]["marketCap"] == 160_000_000_000

    def test_market_cap_latest_year_only_without_historical_prices(
        self, multi_year_balance_sheets, multi_year_earnings, ipca_entries
    ):
        """Without historical prices, only the latest year gets market cap."""
        result = compute_fundamentals(
            "WEGE3", market_cap=200_000_000_000, current_price=50.0
        )
        assert result[0]["marketCap"] == 200_000_000_000  # 2024 (latest)
        assert result[1]["marketCap"] is None  # 2023 — no historical prices

    def test_market_cap_none_when_not_provided(
        self, multi_year_balance_sheets, ipca_entries
    ):
        result = compute_fundamentals("WEGE3", market_cap=None, current_price=None)
        assert result[0]["marketCap"] is None

    def test_ticker_case_insensitive(
        self, multi_year_balance_sheets, ipca_entries
    ):
        result = compute_fundamentals("wege3", market_cap=None, current_price=None)
        assert len(result) == 2


class TestAggregateProventosByYear:
    def test_sums_dividends_and_jcp_per_year(self):
        """Total proventos = sum of (rate × shares_at_time) per year."""
        cash_dividends = [
            {"paymentDate": "2024-03-15T03:00:00.000Z", "rate": 0.50, "label": "DIVIDENDO"},
            {"paymentDate": "2024-06-15T03:00:00.000Z", "rate": 0.30, "label": "JCP"},
            {"paymentDate": "2024-09-15T03:00:00.000Z", "rate": 0.20, "label": "DIVIDENDO"},
            {"paymentDate": "2023-12-15T03:00:00.000Z", "rate": 0.40, "label": "DIVIDENDO"},
        ]
        # 4B shares, no splits
        result = aggregate_proventos_by_year(
            cash_dividends=cash_dividends,
            stock_dividends=[],
            current_shares=4_000_000_000,
        )
        # 2024: (0.50 + 0.30 + 0.20) × 4B = 4.0B
        assert result[2024] == pytest.approx(4_000_000_000, rel=1e-6)
        # 2023: 0.40 × 4B = 1.6B
        assert result[2023] == pytest.approx(1_600_000_000, rel=1e-6)

    def test_adjusts_shares_for_splits(self):
        """Pre-split dividends use the pre-split share count."""
        cash_dividends = [
            # Before 2:1 split
            {"paymentDate": "2023-06-15T03:00:00.000Z", "rate": 1.00, "label": "DIVIDENDO"},
            # After 2:1 split
            {"paymentDate": "2024-06-15T03:00:00.000Z", "rate": 0.50, "label": "DIVIDENDO"},
        ]
        stock_dividends = [
            # 2:1 split on 2024-01-15
            {"lastDatePrior": "2024-01-15T03:00:00.000Z", "label": "DESDOBRAMENTO", "factor": 2.0},
        ]
        # Current shares: 4B (post-split)
        result = aggregate_proventos_by_year(
            cash_dividends=cash_dividends,
            stock_dividends=stock_dividends,
            current_shares=4_000_000_000,
        )
        # 2024: 0.50 × 4B = 2B (post-split, current shares)
        assert result[2024] == pytest.approx(2_000_000_000, rel=1e-6)
        # 2023: 1.00 × 2B = 2B (pre-split, half the current shares)
        assert result[2023] == pytest.approx(2_000_000_000, rel=1e-6)

    def test_handles_reverse_split(self):
        """Reverse split (grupamento) increases pre-split share count."""
        cash_dividends = [
            {"paymentDate": "2023-06-15T03:00:00.000Z", "rate": 0.10, "label": "DIVIDENDO"},
        ]
        stock_dividends = [
            # 1:5 reverse split (grupamento) on 2024-01-15: factor = 0.2
            {"lastDatePrior": "2024-01-15T03:00:00.000Z", "label": "GRUPAMENTO", "factor": 0.2},
        ]
        # Current shares: 1B (post-reverse-split)
        result = aggregate_proventos_by_year(
            cash_dividends=cash_dividends,
            stock_dividends=stock_dividends,
            current_shares=1_000_000_000,
        )
        # 2023: 0.10 × 5B = 500M (pre-reverse-split had 5× the shares)
        assert result[2023] == pytest.approx(500_000_000, rel=1e-6)

    def test_empty_dividends(self):
        result = aggregate_proventos_by_year(
            cash_dividends=[],
            stock_dividends=[],
            current_shares=4_000_000_000,
        )
        assert result == {}

    def test_multiple_splits(self):
        """Multiple splits compound correctly."""
        cash_dividends = [
            {"paymentDate": "2022-06-15T03:00:00.000Z", "rate": 2.00, "label": "DIVIDENDO"},
        ]
        stock_dividends = [
            # 2:1 split in 2023
            {"lastDatePrior": "2023-01-15T03:00:00.000Z", "label": "DESDOBRAMENTO", "factor": 2.0},
            # 3:1 split in 2024
            {"lastDatePrior": "2024-01-15T03:00:00.000Z", "label": "DESDOBRAMENTO", "factor": 3.0},
        ]
        # Current shares: 6B (after 2× then 3× = 6×)
        result = aggregate_proventos_by_year(
            cash_dividends=cash_dividends,
            stock_dividends=stock_dividends,
            current_shares=6_000_000_000,
        )
        # 2022: 2.00 × 1B = 2B (before both splits: 6B / 6 = 1B)
        assert result[2022] == pytest.approx(2_000_000_000, rel=1e-6)


class TestComputeQuarterlyBalanceRatios:
    def test_returns_all_quarters_sorted_ascending(self, multi_year_balance_sheets):
        result = compute_quarterly_balance_ratios("WEGE3")
        dates = [r["date"] for r in result]
        assert dates == sorted(dates)
        # 8 quarters total (4 per year × 2 years)
        assert len(result) == 8

    def test_computes_debt_to_equity_ratio(self, multi_year_balance_sheets):
        result = compute_quarterly_balance_ratios("WEGE3")
        # 2024 Q4: debt_ex_lease = 10B - 1B = 9B, equity = 15B → 0.6
        q4_2024 = [r for r in result if r["date"] == "2024-12-31"][0]
        assert q4_2024["debtToEquity"] == 0.6

    def test_computes_liabilities_to_equity_ratio(self, multi_year_balance_sheets):
        result = compute_quarterly_balance_ratios("WEGE3")
        # 2024 Q4: liabilities = 20B, equity = 15B → 1.33
        q4_2024 = [r for r in result if r["date"] == "2024-12-31"][0]
        assert q4_2024["liabilitiesToEquity"] == 1.33

    def test_handles_null_equity(self, db):
        BalanceSheet.objects.create(
            ticker="NULL3", end_date=date(2024, 12, 31),
            total_debt=10_000, total_lease=1_000,
            total_liabilities=20_000, stockholders_equity=None,
        )
        result = compute_quarterly_balance_ratios("NULL3")
        assert result[0]["debtToEquity"] is None
        assert result[0]["liabilitiesToEquity"] is None

    def test_handles_zero_equity(self, db):
        BalanceSheet.objects.create(
            ticker="ZERO3", end_date=date(2024, 12, 31),
            total_debt=10_000, total_lease=1_000,
            total_liabilities=20_000, stockholders_equity=0,
        )
        result = compute_quarterly_balance_ratios("ZERO3")
        assert result[0]["debtToEquity"] is None
        assert result[0]["liabilitiesToEquity"] is None

    def test_empty_ticker_returns_empty_list(self, db):
        result = compute_quarterly_balance_ratios("NONE3")
        assert result == []

    def test_ticker_case_insensitive(self, multi_year_balance_sheets):
        result = compute_quarterly_balance_ratios("wege3")
        assert len(result) == 8
