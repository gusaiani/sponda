"""Unit tests for PE10 calculation logic."""
from datetime import date
from decimal import Decimal



from quotes.models import QuarterlyEarnings
from quotes.inflation import get_inflation_adjustment_factors
from quotes.pe10 import (
    PE_WINDOW_YEARS,
    calculate_pe10,
    calculate_pe_windows,
    get_annual_earnings,
)


def create_flat_quarterly_earnings(ticker, first_year, last_year, quarterly_net_income):
    """Create four identical quarters per year for [first_year, last_year]."""
    for year in range(first_year, last_year + 1):
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker=ticker,
                end_date=date(year, month, day),
                net_income=quarterly_net_income,
            )


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


class TestPe10CrossCurrency:
    """When a ticker lists in USD but reports in another currency (e.g.
    NVO listed on NYSE, files in DKK), PE10 must translate the market cap
    into the statement currency before dividing by earnings."""

    def test_translates_market_cap_to_reported_currency(self, db):
        from quotes.models import FxRate, Ticker

        Ticker.objects.create(symbol="NVO", name="Novo Nordisk", reported_currency="DKK")
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 12, 31), rate=Decimal("6.85"),
        )
        # 4 quarters of DKK earnings, 25B DKK each (≈ 3.65B USD)
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="NVO", end_date=date(2025, month, day),
                net_income=25_000_000_000,
            )
        # Market cap in USD (the listing currency for NVO)
        market_cap_usd = Decimal("195_000_000_000")
        result = calculate_pe10("NVO", market_cap_usd)
        # Translated cap: $195B * 6.85 = 1335.75B DKK
        # Annual earnings: 100B DKK
        # PE = 1335.75 / 100 = 13.36 (a real-world ballpark, not 1.95)
        assert result["pe10"] is not None
        assert 12 < result["pe10"] < 15

    def test_returns_none_when_fx_unavailable(self, db):
        """No FX data for DKK → cannot compute. Return pe10=None with a
        clear error so the screener degrades gracefully."""
        from quotes.models import Ticker

        Ticker.objects.create(symbol="NVO", name="Novo Nordisk", reported_currency="DKK")
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="NVO", end_date=date(2025, month, day),
                net_income=25_000_000_000,
            )
        result = calculate_pe10("NVO", Decimal("195_000_000_000"))
        assert result["pe10"] is None
        assert "moeda" in result["error"].lower() or "currency" in result["error"].lower()

    def test_same_currency_passes_through_unchanged(self, sample_earnings, sample_ipca):
        """Brazilian ticker with BRL market cap and BRL statements: behaviour
        identical to before the FX path was added."""
        from quotes.models import Ticker

        Ticker.objects.create(symbol="PETR4", name="Petrobras", reported_currency="BRL")
        market_cap = Decimal("585_000_000_000")
        result = calculate_pe10("PETR4", market_cap)
        assert result["pe10"] is not None


class TestPe10TrailingQuarters:
    """TFCO4 regression: when the most recent fiscal year has only a
    partial set of quarters reported (e.g. mid-2026 with Q1 only), the
    N-year window must backfill from older years so it divides an
    honest N years of earnings — not pretend that partial year is a
    full year and under-weight the average."""

    def test_partial_current_year_backfills_from_older_year(self, db):
        # 1 quarter of 2026 + 4 quarters each of 2025, 2024, 2023.
        # PE3 (max_years=3) trailing 12 quarters MUST cover:
        #   Q1 2026 + full 2025 + full 2024 + Q2–Q4 2023.
        # OLD behaviour summed (Q1 2026 + 2025 + 2024) ÷ 3, undershooting.
        for month, day in [(3, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="TFCO4", end_date=date(2026, month, day),
                net_income=10_000_000,
            )
        for year in [2025, 2024, 2023]:
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="TFCO4", end_date=date(year, month, day),
                    net_income=10_000_000,
                )

        result = calculate_pe10("TFCO4", Decimal("400_000_000"), max_years=3)

        # Trailing 12 quarters × 10M each = 120M. ÷ 3 years = 40M avg.
        # PE = 400M / 40M = 10.
        assert result["pe10"] == 10.0
        assert result["avg_adjusted_net_income"] == 40_000_000.0
        assert result["years_of_data"] == 3
        assert result["label"] == "PE3"

        details = result["calculation_details"]
        # 4 calendar-year rows expected: 2026(1q) + 2025(4q) + 2024(4q) + 2023(synthetic 3q tail).
        assert len(details) == 4
        assert details[0]["year"] == 2026 and details[0]["quarters"] == 1
        assert details[1]["year"] == 2025 and details[1]["quarters"] == 4
        assert details[2]["year"] == 2024 and details[2]["quarters"] == 4
        assert details[3]["year"] == 2023 and details[3]["quarters"] == 3
        # The 2023 row holds only the latest 3 of its 4 quarters.
        kept_dates = [q["end_date"] for q in details[3]["quarterlyDetail"]]
        assert kept_dates == ["2023-06-30", "2023-09-30", "2023-12-31"]

    def test_caps_window_when_company_lacks_enough_quarters(self, db):
        # Only 8 quarters total (2 full years). max_years=10 must
        # downgrade to PE2 rather than divide by 10.
        for year in [2024, 2025]:
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="YOUNG3", end_date=date(year, month, day),
                    net_income=10_000_000,
                )
        result = calculate_pe10("YOUNG3", Decimal("160_000_000"), max_years=10)
        # 8 quarters × 10M = 80M. ÷ 2 years = 40M avg. PE = 160M/40M = 4.
        assert result["years_of_data"] == 2
        assert result["label"] == "PE2"
        assert result["pe10"] == 4.0


def create_semi_annual_earnings(ticker, years, net_income_per_half=10_000_000):
    """Half-year reporters (e.g. Rio Tinto) file H1 (June 30) and FY (Dec 31)."""
    for year in years:
        for month, day in [(6, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker=ticker, end_date=date(year, month, day),
                net_income=net_income_per_half,
            )


class TestPe10ReportingFrequency:
    """RIO regression: semi-annual reporters (H1 + FY filings only) were
    treated as quarterly reporters. ``total_filings // 4`` halved
    ``years_of_data`` (capping the slider at 6 for ~13 years of history)
    and the "N-year" window silently consumed 2N real years of earnings."""

    def test_semi_annual_reporter_counts_years_correctly(self, db):
        # 6 years × 2 filings = 12 periods → 6 years of data, not 3.
        create_semi_annual_earnings("RIO", range(2020, 2026))
        result = calculate_pe10("RIO", Decimal("300_000_000"), max_years=50)
        assert result["periods_per_year"] == 2
        assert result["years_of_data"] == 6
        assert result["label"] == "PE6"

    def test_semi_annual_window_covers_n_years_not_2n(self, db):
        # Old years earn 100× more; a 4-year window that leaks into them
        # would produce a wildly different average.
        create_semi_annual_earnings("RIO", range(2022, 2026), net_income_per_half=10_000_000)
        create_semi_annual_earnings("RIO", range(2018, 2022), net_income_per_half=1_000_000_000)
        result = calculate_pe10("RIO", Decimal("400_000_000"), max_years=4)
        # 8 latest half-years × 10M = 80M ÷ 4 years = 20M avg. PE = 400M/20M = 20.
        assert result["avg_adjusted_net_income"] == 20_000_000.0
        assert result["pe10"] == 20.0
        assert result["years_of_data"] == 4

    def test_semi_annual_partial_year_backfills_half_year(self, db):
        # Current year has only H1 filed. A 3-year window (6 half-years)
        # must trail one extra half-year into the oldest year.
        QuarterlyEarnings.objects.create(
            ticker="RIO", end_date=date(2026, 6, 30), net_income=10_000_000,
        )
        create_semi_annual_earnings("RIO", [2023, 2024, 2025])
        result = calculate_pe10("RIO", Decimal("400_000_000"), max_years=3)
        # 6 half-years × 10M = 60M ÷ 3 = 20M avg. PE = 400M/20M = 20.
        assert result["avg_adjusted_net_income"] == 20_000_000.0
        assert result["pe10"] == 20.0
        details = result["calculation_details"]
        # Oldest row is a synthetic partial tail holding only H2 2023.
        assert details[-1]["year"] == 2023
        assert details[-1]["quarters"] == 1
        assert [q["end_date"] for q in details[-1]["quarterlyDetail"]] == ["2023-12-31"]

    def test_semi_annual_reporter_is_not_flagged_annual(self, db):
        create_semi_annual_earnings("RIO", range(2020, 2026))
        result = calculate_pe10("RIO", Decimal("300_000_000"))
        assert result["annual_data_flag"] is False

    def test_annual_reporter_counts_years_correctly(self, db):
        # 1 filing per year → periods_per_year=1; 5 filings = 5 years.
        for year in range(2021, 2026):
            QuarterlyEarnings.objects.create(
                ticker="ANUAL3", end_date=date(year, 12, 31),
                net_income=10_000_000,
            )
        result = calculate_pe10("ANUAL3", Decimal("200_000_000"), max_years=50)
        assert result["periods_per_year"] == 1
        assert result["years_of_data"] == 5
        assert result["annual_data_flag"] is True
        # 5 years × 10M ÷ 5 = 10M avg. PE = 200M/10M = 20.
        assert result["avg_adjusted_net_income"] == 10_000_000.0
        assert result["pe10"] == 20.0

    def test_quarterly_reporter_reports_four_periods_per_year(self, sample_earnings):
        result = calculate_pe10("PETR4", Decimal("585_000_000_000"))
        assert result["periods_per_year"] == 4
        assert result["years_of_data"] == 10

    def test_lone_partial_year_defaults_to_quarterly(self, db):
        # Only the in-progress year exists (2 quarters). Without a
        # complete prior year the frequency is unknowable; assume
        # quarterly so a half-year is never presented as a full year.
        for month, day in [(3, 31), (6, 30)]:
            QuarterlyEarnings.objects.create(
                ticker="NEW3", end_date=date(2026, month, day),
                net_income=10_000_000,
            )
        result = calculate_pe10("NEW3", Decimal("100_000_000"))
        assert result["periods_per_year"] == 4
        assert result["years_of_data"] == 0
        assert result["pe10"] is None


class TestCalculatePEWindows:
    """calculate_pe_windows: every P/E window from 1 to 15 years, strict.

    Strict means a window is None unless the company has the full window of
    earnings history — a PE15 built from 8 years is not a PE15. The widest
    honest window is reported as years_available so callers can explain
    why a window is empty.
    """

    def test_full_history_fills_every_window(self, db):
        # 15 years × 4B/year, market cap 40B → every window is exactly 10.
        create_flat_quarterly_earnings("WIND3", 2011, 2025, 1_000_000_000)
        result = calculate_pe_windows("WIND3", Decimal("40_000_000_000"))
        assert result["years_available"] == 15
        assert set(result["pe_by_years"]) == set(PE_WINDOW_YEARS)
        for years in PE_WINDOW_YEARS:
            assert result["pe_by_years"][years] == 10.0

    def test_windows_beyond_available_history_are_none(self, db):
        # 8 years of history: pe1–pe8 exist, pe9–pe15 are strictly None.
        create_flat_quarterly_earnings("THIN3", 2018, 2025, 1_000_000_000)
        result = calculate_pe_windows("THIN3", Decimal("40_000_000_000"))
        assert result["years_available"] == 8
        for years in range(1, 9):
            assert result["pe_by_years"][years] == 10.0
        for years in range(9, 16):
            assert result["pe_by_years"][years] is None

    def test_each_window_averages_only_its_own_years(self, db):
        # 2025 earns 8B; 2011–2024 earn 4B/year. Market cap 40B.
        create_flat_quarterly_earnings("GROW3", 2011, 2024, 1_000_000_000)
        create_flat_quarterly_earnings("GROW3", 2025, 2025, 2_000_000_000)
        result = calculate_pe_windows("GROW3", Decimal("40_000_000_000"))
        assert result["pe_by_years"][1] == 5.0  # 40 / 8
        assert result["pe_by_years"][10] == 9.09  # 40 / ((8 + 9×4) / 10)
        assert result["pe_by_years"][15] == 9.38  # 40 / ((8 + 14×4) / 15)

    def test_partial_current_year_backfills_from_older_quarters(self, db):
        # Two quarters of 2026 plus 15 full years: the 1-year window is the
        # four most recent quarters (H1 2026 + H2 2025), never a half year.
        create_flat_quarterly_earnings("PART3", 2011, 2025, 1_000_000_000)
        for month, day in [(3, 31), (6, 30)]:
            QuarterlyEarnings.objects.create(
                ticker="PART3", end_date=date(2026, month, day),
                net_income=1_000_000_000,
            )
        result = calculate_pe_windows("PART3", Decimal("40_000_000_000"))
        assert result["years_available"] == 15
        assert result["pe_by_years"][1] == 10.0
        assert result["pe_by_years"][15] == 10.0

    def test_negative_window_average_is_none_without_hiding_others(self, db):
        # 2025 loses 8B; earlier years earn 4B. The 1-year window has a
        # negative average (None); the 15-year window is still positive.
        create_flat_quarterly_earnings("LOSS3", 2011, 2024, 1_000_000_000)
        create_flat_quarterly_earnings("LOSS3", 2025, 2025, -2_000_000_000)
        result = calculate_pe_windows("LOSS3", Decimal("40_000_000_000"))
        assert result["years_available"] == 15
        assert result["pe_by_years"][1] is None
        assert result["pe_by_years"][15] is not None

    def test_matches_calculate_pe10_for_the_ten_year_window(
        self, sample_earnings, sample_ipca,
    ):
        market_cap = Decimal("585_000_000_000")
        windows = calculate_pe_windows("PETR4", market_cap)
        legacy = calculate_pe10("PETR4", market_cap, max_years=10)
        assert windows["pe_by_years"][10] == legacy["pe10"]

    def test_semi_annual_reporter_counts_two_periods_per_year(self, db):
        # 12 semi-annual filings = 6 full years for a semi-annual reporter.
        create_semi_annual_earnings("RIO", range(2020, 2026))
        result = calculate_pe_windows("RIO", Decimal("300_000_000"))
        assert result["years_available"] == 6
        assert result["pe_by_years"][6] is not None
        assert result["pe_by_years"][7] is None

    def test_no_earnings_data(self, db):
        result = calculate_pe_windows("FAKE3", Decimal("100_000_000"))
        assert result["years_available"] == 0
        assert all(value is None for value in result["pe_by_years"].values())

    def test_average_net_income_still_spans_up_to_ten_loose_years(self, db):
        # Debt-coverage ratios keep the historical "up to 10 years"
        # average: 3 years of 4B/year averages to 4B even though no strict
        # 10-year window exists.
        create_flat_quarterly_earnings("FEW3", 2023, 2025, 1_000_000_000)
        result = calculate_pe_windows("FEW3", Decimal("40_000_000_000"))
        assert result["years_available"] == 3
        assert result["pe_by_years"][10] is None
        assert result["avg_adjusted_net_income"] == 4_000_000_000.0


class TestCalculatePEWindowsAverages:
    """calculate_pe_windows also reports the strict average behind each
    window, so debt coverage can divide by exactly N years of earnings."""

    def test_reports_the_strict_average_per_window(self, db):
        # 2025 earns 8B; 2011–2024 earn 4B/year.
        create_flat_quarterly_earnings("GROW3", 2011, 2024, 1_000_000_000)
        create_flat_quarterly_earnings("GROW3", 2025, 2025, 2_000_000_000)
        result = calculate_pe_windows("GROW3", Decimal("40_000_000_000"))
        averages = result["average_net_income_by_years"]
        assert set(averages) == set(PE_WINDOW_YEARS)
        assert averages[1] == Decimal("8_000_000_000")
        assert averages[10] == Decimal("4_400_000_000")

    def test_averages_beyond_history_are_none(self, db):
        create_flat_quarterly_earnings("THIN3", 2018, 2025, 1_000_000_000)
        result = calculate_pe_windows("THIN3", Decimal("40_000_000_000"))
        averages = result["average_net_income_by_years"]
        assert averages[8] == Decimal("4_000_000_000")
        for years in range(9, 16):
            assert averages[years] is None

    def test_averages_do_not_need_a_market_cap(self, db):
        create_flat_quarterly_earnings("NOCAP3", 2020, 2025, 1_000_000_000)
        result = calculate_pe_windows("NOCAP3", None)
        assert result["pe_by_years"][3] is None
        assert result["average_net_income_by_years"][3] == Decimal("4_000_000_000")

    def test_negative_averages_are_reported_not_hidden(self, db):
        # The P/E is None for a loss-making window, but the average itself
        # is a fact worth carrying so callers decide what to do with it.
        create_flat_quarterly_earnings("LOSS3", 2011, 2024, 1_000_000_000)
        create_flat_quarterly_earnings("LOSS3", 2025, 2025, -2_000_000_000)
        result = calculate_pe_windows("LOSS3", Decimal("40_000_000_000"))
        assert result["pe_by_years"][1] is None
        assert result["average_net_income_by_years"][1] == Decimal("-8_000_000_000")

    def test_no_history_reports_empty_averages(self, db):
        result = calculate_pe_windows("NONE3", Decimal("40_000_000_000"))
        assert result["average_net_income_by_years"] == {
            years: None for years in PE_WINDOW_YEARS
        }
