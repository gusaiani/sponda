"""Unit tests for PFCF10 calculation logic."""
from datetime import date
from decimal import Decimal


from quotes.models import QuarterlyCashFlow
from quotes.pfcf10 import calculate_pfcf10, get_annual_fcf


class TestGetAnnualFCF:
    def test_sums_quarterly_fcf_by_year(self, sample_cash_flows):
        result = get_annual_fcf("PETR4")
        assert len(result) == 10
        assert result[0]["year"] == 2025

    def test_fcf_is_ocf_plus_icf(self, sample_cash_flows):
        result = get_annual_fcf("PETR4")
        year_2025 = next(r for r in result if r["year"] == 2025)
        # Sum of quarterly (OCF + ICF) for 2025
        expected = (45e9 - 15e9) + (38e9 - 12e9) + (42e9 - 14e9) + (30e9 - 10e9)
        assert abs(float(year_2025["fcf"]) - expected) < 1

    def test_counts_quarters(self, sample_cash_flows):
        result = get_annual_fcf("PETR4")
        for year_data in result:
            assert year_data["quarters"] == 4

    def test_includes_quarterly_detail(self, sample_cash_flows):
        result = get_annual_fcf("PETR4")
        year_2025 = next(r for r in result if r["year"] == 2025)
        assert len(year_2025["quarterly_detail"]) == 4
        q = year_2025["quarterly_detail"][0]
        assert "operating_cash_flow" in q
        assert "investment_cash_flow" in q
        assert "fcf" in q

    def test_respects_max_years(self, sample_cash_flows):
        result = get_annual_fcf("PETR4", max_years=5)
        assert len(result) == 5
        assert result[0]["year"] == 2025
        assert result[-1]["year"] == 2021

    def test_returns_empty_for_unknown_ticker(self, db):
        result = get_annual_fcf("FAKE3")
        assert result == []


class TestCalculatePFCF10:
    def test_basic_calculation(self, sample_cash_flows, sample_ipca):
        market_cap = Decimal("585_000_000_000")
        result = calculate_pfcf10("PETR4", market_cap)
        assert result["pfcf10"] is not None
        assert result["years_of_data"] == 10
        assert result["label"] == "PFCF10"
        assert result["error"] is None
        assert result["avg_adjusted_fcf"] > 0

    def test_pfcf10_is_market_cap_over_avg_fcf(self, sample_cash_flows, sample_ipca):
        market_cap = Decimal("585_000_000_000")
        result = calculate_pfcf10("PETR4", market_cap)
        expected = float(market_cap / Decimal(str(result["avg_adjusted_fcf"])))
        assert abs(result["pfcf10"] - expected) < 0.02

    def test_no_cash_flow_data(self, db, sample_ipca):
        result = calculate_pfcf10("FAKE3", Decimal("100_000_000_000"))
        assert result["pfcf10"] is None
        assert result["years_of_data"] == 0
        assert result["error"] == "Sem dados de fluxo de caixa disponíveis"

    def test_negative_average_fcf(self, db, sample_ipca):
        for year in [2024, 2025]:
            for q in range(4):
                month = [3, 6, 9, 12][q]
                day = [31, 30, 30, 31][q]
                QuarterlyCashFlow.objects.create(
                    ticker="LOSS3",
                    end_date=date(year, month, day),
                    operating_cash_flow=1_000_000_000,
                    investment_cash_flow=-3_000_000_000,
                )
        result = calculate_pfcf10("LOSS3", Decimal("50_000_000_000"))
        assert result["pfcf10"] is None
        assert "negativo" in result["error"].lower()

    def test_fewer_than_10_years(self, db, sample_ipca):
        for year in [2023, 2024, 2025]:
            for q in range(4):
                month = [3, 6, 9, 12][q]
                day = [31, 30, 30, 31][q]
                QuarterlyCashFlow.objects.create(
                    ticker="FEW3",
                    end_date=date(year, month, day),
                    operating_cash_flow=10_000_000_000,
                    investment_cash_flow=-3_000_000_000,
                )
        result = calculate_pfcf10("FEW3", Decimal("100_000_000_000"))
        assert result["years_of_data"] == 3
        assert result["label"] == "PFCF3"
        assert result["pfcf10"] is not None

    def test_no_ipca_uses_nominal(self, sample_cash_flows):
        result = calculate_pfcf10("PETR4", Decimal("585_000_000_000"))
        assert result["pfcf10"] is not None
        assert result["years_of_data"] == 10

    def test_calculation_details_included(self, sample_cash_flows, sample_ipca):
        result = calculate_pfcf10("PETR4", Decimal("585_000_000_000"))
        details = result["calculation_details"]
        assert len(details) == 10
        assert "nominalFCF" in details[0]
        assert "ipcaFactor" in details[0]
        assert "adjustedFCF" in details[0]
        assert "quarterlyDetail" in details[0]


class TestPFCF10TrailingQuarters:
    """Same partial-current-year regression as pe10: trailing N×4
    quarters must include a partial-tail year when the most recent
    fiscal year is not yet closed."""

    def test_partial_current_year_backfills_from_older_year(self, db):
        QuarterlyCashFlow.objects.create(
            ticker="TFCO4", end_date=date(2026, 3, 31),
            operating_cash_flow=10_000_000, investment_cash_flow=0,
        )
        for year in [2025, 2024, 2023]:
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyCashFlow.objects.create(
                    ticker="TFCO4", end_date=date(year, month, day),
                    operating_cash_flow=10_000_000, investment_cash_flow=0,
                )

        result = calculate_pfcf10("TFCO4", Decimal("400_000_000"), max_years=3)

        assert result["pfcf10"] == 10.0
        assert result["avg_adjusted_fcf"] == 40_000_000.0
        assert result["years_of_data"] == 3
        assert result["label"] == "PFCF3"

        details = result["calculation_details"]
        assert len(details) == 4
        assert details[3]["year"] == 2023 and details[3]["quarters"] == 3
        kept_dates = [q["end_date"] for q in details[3]["quarterlyDetail"]]
        assert kept_dates == ["2023-06-30", "2023-09-30", "2023-12-31"]
