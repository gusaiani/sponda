"""Unit tests for PE10 calculation logic."""
from datetime import date
from decimal import Decimal

import pytest

from quotes.models import IPCAIndex, QuarterlyEarnings
from quotes.inflation import get_inflation_adjustment_factors
from quotes.pe10 import calculate_pe10, get_annual_earnings


class TestGetAnnualEarnings:
    def test_sums_quarterly_net_income_by_year(self, sample_earnings):
        result = get_annual_earnings("PETR4")
        # Should have 10 years
        assert len(result) == 10
        # Most recent year first
        assert result[0]["year"] == 2025

    def test_net_income_is_sum_of_quarters(self, sample_earnings):
        result = get_annual_earnings("PETR4")
        year_2025 = next(r for r in result if r["year"] == 2025)
        # Sum of Q1-Q4 2025 net income
        expected = 35_000_000_000 + 27_000_000_000 + 33_000_000_000 + 16_000_000_000
        assert year_2025["net_income"] == expected

    def test_counts_quarters(self, sample_earnings):
        result = get_annual_earnings("PETR4")
        for year_data in result:
            assert year_data["quarters"] == 4

    def test_includes_quarterly_detail(self, sample_earnings):
        result = get_annual_earnings("PETR4")
        year_2025 = next(r for r in result if r["year"] == 2025)
        assert len(year_2025["quarterly_detail"]) == 4
        # Sorted by end_date
        dates = [q["end_date"] for q in year_2025["quarterly_detail"]]
        assert dates == sorted(dates)

    def test_respects_max_years(self, sample_earnings):
        result = get_annual_earnings("PETR4", max_years=5)
        assert len(result) == 5
        assert result[0]["year"] == 2025
        assert result[-1]["year"] == 2021

    def test_returns_empty_for_unknown_ticker(self, db):
        result = get_annual_earnings("FAKE3")
        assert result == []


class TestGetIPCAAdjustmentFactors:
    def test_most_recent_year_factor_is_one(self, sample_ipca):
        factors = get_inflation_adjustment_factors("PETR4",[2025])
        assert factors[2025] == Decimal("1")

    def test_older_years_have_higher_factors(self, sample_ipca):
        factors = get_inflation_adjustment_factors("PETR4",[2020, 2025])
        assert factors[2020] > factors[2025]

    def test_compounds_rates(self, sample_ipca):
        factors = get_inflation_adjustment_factors("PETR4",[2024, 2025])
        # 2024 earnings adjusted by 2025 rate: factor = (1 + 4.26/100) = 1.0426
        expected = Decimal("1") * (1 + Decimal("4.26") / 100)
        assert abs(factors[2024] - expected) < Decimal("0.001")

    def test_returns_empty_without_ipca_data(self, db):
        factors = get_inflation_adjustment_factors("PETR4",[2020, 2025])
        assert factors == {}

    def test_returns_empty_for_empty_years(self, sample_ipca):
        factors = get_inflation_adjustment_factors("PETR4",[])
        assert factors == {}


class TestCalculatePE10:
    def test_basic_calculation(self, sample_earnings, sample_ipca):
        # Market cap = price * shares = 45 * 13B = 585B
        market_cap = Decimal("585_000_000_000")
        result = calculate_pe10("PETR4", market_cap)
        assert result["pe10"] is not None
        assert result["years_of_data"] == 10
        assert result["label"] == "PE10"
        assert result["error"] is None
        assert result["avg_adjusted_net_income"] > 0

    def test_pe10_is_market_cap_over_avg_net_income(self, sample_earnings, sample_ipca):
        market_cap = Decimal("585_000_000_000")
        result = calculate_pe10("PETR4", market_cap)
        expected_pe10 = float(market_cap / Decimal(str(result["avg_adjusted_net_income"])))
        assert abs(result["pe10"] - expected_pe10) < 0.02

    def test_no_earnings_data(self, db, sample_ipca):
        result = calculate_pe10("FAKE3", Decimal("100_000_000_000"))
        assert result["pe10"] is None
        assert result["years_of_data"] == 0
        assert result["label"] == "PE0"
        assert result["error"] == "Sem dados de lucro disponíveis"

    def test_negative_average_earnings(self, db, sample_ipca):
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
        result = calculate_pe10("LOSS3", Decimal("50_000_000_000"))
        assert result["pe10"] is None
        assert "negativo" in result["error"].lower()

    def test_fewer_than_10_years(self, db, sample_ipca):
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
        result = calculate_pe10("FEW3", Decimal("100_000_000_000"))
        assert result["years_of_data"] == 3
        assert result["label"] == "PE3"
        assert result["pe10"] is not None

    def test_no_ipca_uses_nominal(self, sample_earnings):
        # No IPCA data loaded — should still calculate using nominal values
        result = calculate_pe10("PETR4", Decimal("585_000_000_000"))
        assert result["pe10"] is not None
        assert result["years_of_data"] == 10

    def test_calculation_details_included(self, sample_earnings, sample_ipca):
        market_cap = Decimal("585_000_000_000")
        result = calculate_pe10("PETR4", market_cap)
        details = result["calculation_details"]
        assert len(details) == 10
        assert "nominalNetIncome" in details[0]
        assert "ipcaFactor" in details[0]
        assert "adjustedNetIncome" in details[0]
        assert "quarterlyDetail" in details[0]
