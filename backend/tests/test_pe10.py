"""Unit tests for PE10 calculation logic."""
from datetime import date
from decimal import Decimal

import pytest

from quotes.models import IPCAIndex, QuarterlyEarnings
from quotes.pe10 import calculate_pe10, get_annual_eps, get_ipca_adjustment_factors


class TestGetAnnualEPS:
    def test_sums_quarterly_eps_by_year(self, sample_earnings, shares_outstanding):
        result = get_annual_eps("PETR4", shares_outstanding=shares_outstanding)
        # Should have 10 years
        assert len(result) == 10
        # Most recent year first
        assert result[0]["year"] == 2025

    def test_derives_eps_from_net_income(self, sample_earnings, shares_outstanding):
        result = get_annual_eps("PETR4", shares_outstanding=shares_outstanding)
        year_2025 = next(r for r in result if r["year"] == 2025)
        # Sum of Q1-Q4 2025 net income / shares outstanding
        expected = Decimal("111_000_000_000") / shares_outstanding
        assert abs(year_2025["eps"] - expected) < Decimal("0.01")

    def test_counts_quarters(self, sample_earnings, shares_outstanding):
        result = get_annual_eps("PETR4", shares_outstanding=shares_outstanding)
        for year_data in result:
            assert year_data["quarters"] == 4

    def test_respects_max_years(self, sample_earnings, shares_outstanding):
        result = get_annual_eps("PETR4", shares_outstanding=shares_outstanding, max_years=5)
        assert len(result) == 5
        assert result[0]["year"] == 2025
        assert result[-1]["year"] == 2021

    def test_returns_empty_for_unknown_ticker(self, db, shares_outstanding):
        result = get_annual_eps("FAKE3", shares_outstanding=shares_outstanding)
        assert result == []

    def test_returns_empty_without_shares_outstanding(self, sample_earnings):
        result = get_annual_eps("PETR4", shares_outstanding=None)
        assert result == []


class TestGetIPCAAdjustmentFactors:
    def test_most_recent_year_factor_is_one(self, sample_ipca):
        factors = get_ipca_adjustment_factors([2025])
        assert factors[2025] == Decimal("1")

    def test_older_years_have_higher_factors(self, sample_ipca):
        factors = get_ipca_adjustment_factors([2020, 2025])
        assert factors[2020] > factors[2025]

    def test_compounds_rates(self, sample_ipca):
        factors = get_ipca_adjustment_factors([2024, 2025])
        # 2024 earnings adjusted by 2025 rate: factor = (1 + 4.26/100) = 1.0426
        expected = Decimal("1") * (1 + Decimal("4.26") / 100)
        assert abs(factors[2024] - expected) < Decimal("0.001")

    def test_returns_empty_without_ipca_data(self, db):
        factors = get_ipca_adjustment_factors([2020, 2025])
        assert factors == {}

    def test_returns_empty_for_empty_years(self, sample_ipca):
        factors = get_ipca_adjustment_factors([])
        assert factors == {}


class TestCalculatePE10:
    def test_basic_calculation(self, sample_earnings, sample_ipca, shares_outstanding):
        result = calculate_pe10("PETR4", Decimal("45"), shares_outstanding)
        assert result["pe10"] is not None
        assert result["years_of_data"] == 10
        assert result["label"] == "PE10"
        assert result["error"] is None
        assert result["avg_adjusted_eps"] > 0

    def test_pe10_is_price_over_avg_eps(self, sample_earnings, sample_ipca, shares_outstanding):
        price = Decimal("45")
        result = calculate_pe10("PETR4", price, shares_outstanding)
        expected_pe10 = float(price / Decimal(str(result["avg_adjusted_eps"])))
        assert abs(result["pe10"] - expected_pe10) < 0.02

    def test_no_earnings_data(self, db, sample_ipca):
        result = calculate_pe10("FAKE3", Decimal("45"), Decimal("1000000"))
        assert result["pe10"] is None
        assert result["years_of_data"] == 0
        assert result["label"] == "PE0"
        assert result["error"] == "No earnings data available"

    def test_negative_average_earnings(self, db, sample_ipca, shares_outstanding):
        # Create only losing years
        for year in [2024, 2025]:
            for q in range(4):
                month = [3, 6, 9, 12][q]
                day = [31, 30, 30, 31][q]
                QuarterlyEarnings.objects.create(
                    ticker="LOSS3",
                    end_date=date(year, month, day),
                    net_income=-1_000_000_000,
                )
        result = calculate_pe10("LOSS3", Decimal("10"), shares_outstanding)
        assert result["pe10"] is None
        assert "negative" in result["error"].lower()

    def test_fewer_than_10_years(self, db, sample_ipca, shares_outstanding):
        # Create only 3 years of data
        for year in [2023, 2024, 2025]:
            for q in range(4):
                month = [3, 6, 9, 12][q]
                day = [31, 30, 30, 31][q]
                QuarterlyEarnings.objects.create(
                    ticker="FEW3",
                    end_date=date(year, month, day),
                    net_income=5_000_000_000,
                )
        result = calculate_pe10("FEW3", Decimal("30"), shares_outstanding)
        assert result["years_of_data"] == 3
        assert result["label"] == "PE3"
        assert result["pe10"] is not None

    def test_no_ipca_uses_nominal(self, sample_earnings, shares_outstanding):
        # No IPCA data loaded — should still calculate using nominal values
        result = calculate_pe10("PETR4", Decimal("45"), shares_outstanding)
        assert result["pe10"] is not None
        assert result["years_of_data"] == 10
