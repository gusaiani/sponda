"""Tests for compute_company_indicators — the service used by the screener + alerts."""
from datetime import date
from decimal import Decimal

import pytest

from quotes.indicators import compute_company_indicators
from quotes.models import (
    BalanceSheet,
    IndicatorSnapshot,
    IPCAIndex,
    QuarterlyCashFlow,
    QuarterlyEarnings,
)


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


@pytest.mark.django_db
class TestComputePEWindows:
    """The snapshot dict carries the whole strict P/E window family."""

    def test_returns_every_pe_window_field(self, earnings_petr4, balance_petr4):
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        for years in range(1, 16):
            assert f"pe{years}" in result
        assert "pe_years_available" in result

    def test_windows_within_history_share_the_flat_average(
        self, earnings_petr4, balance_petr4,
    ):
        # Flat 10B/year: every window up to 10 years is 400B / 10B = 40.
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        assert result["pe1"] == Decimal("40")
        assert result["pe5"] == Decimal("40")
        assert result["pe10"] == Decimal("40")
        assert result["pe_years_available"] == 10

    def test_windows_beyond_history_are_strictly_none(
        self, earnings_petr4, balance_petr4,
    ):
        # Ten years of data: pe11–pe15 must be None, not a disguised PE10.
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        for years in range(11, 16):
            assert result[f"pe{years}"] is None

    def test_thin_history_nulls_pe10_but_keeps_short_windows(self, ipca_stub):
        # Three years of history: strict pe10 is gone, pe3 remains.
        for year in [2023, 2024, 2025]:
            for quarter_end in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="FEW3",
                    end_date=date(year, *quarter_end),
                    net_income=2_500_000_000,
                )
        result = compute_company_indicators("FEW3", market_cap=400_000_000_000)
        assert result["pe10"] is None
        assert result["pe3"] == Decimal("40")
        assert result["pe_years_available"] == 3

    def test_thin_history_keeps_loose_debt_coverage(self, ipca_stub):
        # debt_to_avg_earnings keeps its "up to 10 years" average even when
        # no strict 10-year window exists.
        for year in [2023, 2024, 2025]:
            for quarter_end in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="FEW3",
                    end_date=date(year, *quarter_end),
                    net_income=2_500_000_000,
                )
        BalanceSheet.objects.create(
            ticker="FEW3",
            end_date=date(2025, 9, 30),
            total_debt=300_000_000_000,
            stockholders_equity=200_000_000_000,
        )
        result = compute_company_indicators("FEW3", market_cap=400_000_000_000)
        # avg earnings = 10B/year over the 3 available years → 300B / 10B = 30
        assert result["debt_to_avg_earnings"] == Decimal("30")

    def test_no_market_cap_reports_available_years_without_windows(
        self, earnings_petr4,
    ):
        result = compute_company_indicators("PETR4", market_cap=None)
        assert result["pe_years_available"] == 10
        assert result["pe5"] is None


@pytest.mark.django_db
class TestComputeDebtCoverageWindows:
    """The snapshot dict carries strict debt-coverage windows next to the
    loose ``debt_to_avg_earnings`` / ``debt_to_avg_fcf`` pair: total debt over
    the average of exactly N years, None when the company lacks N years."""

    def test_returns_every_debt_coverage_window_field(
        self, earnings_petr4, cashflow_petr4, balance_petr4,
    ):
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        for years in range(1, 16):
            assert f"debt_to_avg_earnings_{years}" in result
            assert f"debt_to_avg_fcf_{years}" in result

    def test_windows_within_history_share_the_flat_ratio(
        self, earnings_petr4, cashflow_petr4, balance_petr4,
    ):
        # Flat 10B/year earnings and 8B/year FCF, 300B of debt.
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        for years in (1, 5, 10):
            assert result[f"debt_to_avg_earnings_{years}"] == Decimal("30")
            assert result[f"debt_to_avg_fcf_{years}"] == Decimal("37.5")

    def test_windows_beyond_history_are_strictly_none(
        self, earnings_petr4, cashflow_petr4, balance_petr4,
    ):
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        for years in range(11, 16):
            assert result[f"debt_to_avg_earnings_{years}"] is None
            assert result[f"debt_to_avg_fcf_{years}"] is None

    def test_thin_history_keeps_short_windows_and_the_loose_ratio(self, ipca_stub):
        for year in [2023, 2024, 2025]:
            for quarter_end in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="FEW3", end_date=date(year, *quarter_end),
                    net_income=2_500_000_000,
                )
        BalanceSheet.objects.create(
            ticker="FEW3", end_date=date(2025, 9, 30),
            total_debt=300_000_000_000, stockholders_equity=200_000_000_000,
        )
        result = compute_company_indicators("FEW3", market_cap=400_000_000_000)
        assert result["debt_to_avg_earnings"] == Decimal("30")
        assert result["debt_to_avg_earnings_3"] == Decimal("30")
        assert result["debt_to_avg_earnings_5"] is None
        assert result["debt_to_avg_earnings_10"] is None

    def test_windows_do_not_need_a_market_cap(
        self, earnings_petr4, cashflow_petr4, balance_petr4,
    ):
        result = compute_company_indicators("PETR4", market_cap=None)
        assert result["debt_to_avg_earnings_5"] == Decimal("30")
        assert result["debt_to_avg_fcf_5"] == Decimal("37.5")

    def test_loss_making_window_is_none_without_hiding_longer_windows(self, ipca_stub):
        # 2025 loses 10B; 2016–2024 earn 10B/year. The 1-year window has a
        # negative average; the 10-year window is still positive.
        for year in range(2016, 2025):
            for quarter_end in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="LOSS3", end_date=date(year, *quarter_end),
                    net_income=2_500_000_000,
                )
        for quarter_end in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="LOSS3", end_date=date(2025, *quarter_end),
                net_income=-2_500_000_000,
            )
        BalanceSheet.objects.create(
            ticker="LOSS3", end_date=date(2025, 9, 30),
            total_debt=300_000_000_000, stockholders_equity=200_000_000_000,
        )
        result = compute_company_indicators("LOSS3", market_cap=400_000_000_000)
        assert result["debt_to_avg_earnings_1"] is None
        # (9 × 10B − 10B) / 10 = 8B/year → 300B / 8B = 37.5
        assert result["debt_to_avg_earnings_10"] == Decimal("37.5")

    def test_ratio_too_large_for_the_snapshot_column_is_none(self, ipca_stub):
        # Earnings of 1 unit a quarter against 300B of debt: the ratio has
        # more digits than the snapshot column holds, so it is reported as
        # None instead of crashing the whole snapshot write.
        for quarter_end in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="TINY3", end_date=date(2025, *quarter_end), net_income=1,
            )
        BalanceSheet.objects.create(
            ticker="TINY3", end_date=date(2025, 9, 30),
            total_debt=300_000_000_000, stockholders_equity=200_000_000_000,
        )
        result = compute_company_indicators("TINY3", market_cap=400_000_000_000)
        assert result["debt_to_avg_earnings_1"] is None
        assert result["debt_to_avg_earnings"] is None

    def test_no_balance_sheet_means_no_windows(self, earnings_petr4, cashflow_petr4):
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        assert result["debt_to_avg_earnings_5"] is None
        assert result["debt_to_avg_fcf_5"] is None

    def test_snapshot_row_accepts_every_window_field(
        self, earnings_petr4, cashflow_petr4, balance_petr4,
    ):
        result = compute_company_indicators("PETR4", market_cap=400_000_000_000)
        snapshot = IndicatorSnapshot.objects.create(ticker="PETR4", **result)
        snapshot.refresh_from_db()
        assert snapshot.debt_to_avg_earnings_5 == Decimal("30")
        assert snapshot.debt_to_avg_fcf_15 is None
