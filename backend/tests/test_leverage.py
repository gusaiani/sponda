"""Tests for leverage (Dívida Bruta/PL and Passivo/PL) calculation logic."""
from datetime import date

import pytest

from quotes.leverage import calculate_leverage
from quotes.models import BalanceSheet


@pytest.fixture
def sample_balance_sheet(db):
    """Create a recent balance sheet for PETR4."""
    return BalanceSheet.objects.create(
        ticker="PETR4",
        end_date=date(2025, 9, 30),
        total_debt=300_000_000_000,
        total_liabilities=500_000_000_000,
        stockholders_equity=200_000_000_000,
    )


class TestCalculateLeverage:
    def test_calculates_debt_to_equity(self, sample_balance_sheet):
        result = calculate_leverage("PETR4")
        assert result["debtToEquity"] == 1.5  # 300B / 200B

    def test_calculates_liabilities_to_equity(self, sample_balance_sheet):
        result = calculate_leverage("PETR4")
        assert result["liabilitiesToEquity"] == 2.5  # 500B / 200B

    def test_returns_balance_sheet_date(self, sample_balance_sheet):
        result = calculate_leverage("PETR4")
        assert result["leverageDate"] == "2025-09-30"

    def test_returns_raw_values(self, sample_balance_sheet):
        result = calculate_leverage("PETR4")
        assert result["totalDebt"] == 300_000_000_000
        assert result["totalLiabilities"] == 500_000_000_000
        assert result["stockholdersEquity"] == 200_000_000_000

    def test_no_error_when_data_available(self, sample_balance_sheet):
        result = calculate_leverage("PETR4")
        assert result["leverageError"] is None

    def test_null_when_no_balance_sheet(self, db):
        result = calculate_leverage("FAKE3")
        assert result["debtToEquity"] is None
        assert result["liabilitiesToEquity"] is None
        assert result["leverageError"] is not None

    def test_null_when_equity_is_zero(self, db):
        BalanceSheet.objects.create(
            ticker="ZERO3",
            end_date=date(2025, 9, 30),
            total_debt=100_000_000_000,
            total_liabilities=200_000_000_000,
            stockholders_equity=0,
        )
        result = calculate_leverage("ZERO3")
        assert result["debtToEquity"] is None
        assert result["liabilitiesToEquity"] is None
        assert result["leverageError"] is not None

    def test_uses_most_recent_balance_sheet(self, db):
        BalanceSheet.objects.create(
            ticker="PETR4",
            end_date=date(2025, 6, 30),
            total_debt=400_000_000_000,
            total_liabilities=600_000_000_000,
            stockholders_equity=100_000_000_000,
        )
        BalanceSheet.objects.create(
            ticker="PETR4",
            end_date=date(2025, 9, 30),
            total_debt=300_000_000_000,
            total_liabilities=500_000_000_000,
            stockholders_equity=200_000_000_000,
        )
        result = calculate_leverage("PETR4")
        assert result["debtToEquity"] == 1.5  # Uses Q3, not Q2

    def test_handles_missing_debt(self, db):
        BalanceSheet.objects.create(
            ticker="NODT3",
            end_date=date(2025, 9, 30),
            total_debt=None,
            total_liabilities=500_000_000_000,
            stockholders_equity=200_000_000_000,
        )
        result = calculate_leverage("NODT3")
        assert result["debtToEquity"] is None
        assert result["liabilitiesToEquity"] == 2.5

    def test_handles_negative_equity(self, db):
        BalanceSheet.objects.create(
            ticker="NEG3",
            end_date=date(2025, 9, 30),
            total_debt=300_000_000_000,
            total_liabilities=500_000_000_000,
            stockholders_equity=-100_000_000_000,
        )
        result = calculate_leverage("NEG3")
        assert result["debtToEquity"] == -3.0
        assert result["liabilitiesToEquity"] == -5.0

    def test_ticker_case_insensitive(self, sample_balance_sheet):
        result = calculate_leverage("petr4")
        assert result["debtToEquity"] == 1.5

    def test_calculates_current_ratio(self, db):
        BalanceSheet.objects.create(
            ticker="LIQC3",
            end_date=date(2025, 9, 30),
            total_debt=100_000_000_000,
            total_liabilities=200_000_000_000,
            stockholders_equity=100_000_000_000,
            current_assets=150_000_000_000,
            current_liabilities=100_000_000_000,
        )
        result = calculate_leverage("LIQC3")
        assert result["currentRatio"] == 1.5  # 150B / 100B

    def test_current_ratio_null_when_no_balance_sheet(self, db):
        result = calculate_leverage("FAKE3")
        assert result["currentRatio"] is None

    def test_current_ratio_null_when_current_liabilities_zero(self, db):
        BalanceSheet.objects.create(
            ticker="ZCLI3",
            end_date=date(2025, 9, 30),
            total_debt=100_000_000_000,
            total_liabilities=200_000_000_000,
            stockholders_equity=100_000_000_000,
            current_assets=150_000_000_000,
            current_liabilities=0,
        )
        result = calculate_leverage("ZCLI3")
        assert result["currentRatio"] is None

    def test_current_ratio_null_when_current_assets_missing(self, db):
        BalanceSheet.objects.create(
            ticker="NOCA3",
            end_date=date(2025, 9, 30),
            total_debt=100_000_000_000,
            total_liabilities=200_000_000_000,
            stockholders_equity=100_000_000_000,
            current_assets=None,
            current_liabilities=100_000_000_000,
        )
        result = calculate_leverage("NOCA3")
        assert result["currentRatio"] is None

    def test_current_ratio_available_when_equity_zero(self, db):
        BalanceSheet.objects.create(
            ticker="EQZR3",
            end_date=date(2025, 9, 30),
            total_debt=100_000_000_000,
            total_liabilities=200_000_000_000,
            stockholders_equity=0,
            current_assets=150_000_000_000,
            current_liabilities=100_000_000_000,
        )
        result = calculate_leverage("EQZR3")
        assert result["debtToEquity"] is None  # equity is zero
        assert result["currentRatio"] == 1.5  # still computed
