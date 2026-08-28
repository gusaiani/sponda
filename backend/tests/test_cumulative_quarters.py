"""BRAPI's income statement differences Q2 and Q3 twice for some filers.

Every figure in these tests is a real one, pulled from BRAPI on 2026-08-27 and
checked against the company's own audited annual filing. The bug and the
companies free of it are both represented, because a repair that cannot tell
them apart would corrupt the healthy ones.
"""
from datetime import date
from decimal import Decimal

from quotes.cumulative_quarters import (
    AS_REPORTED,
    RUNNING_SUM,
    UNDECIDED,
    AnnualIncome,
    choose_restatement,
    restate_quarterly_earnings,
    running_sum_restatement,
)
from quotes.models import QuarterlyEarnings

# Kepler Weber, 2025. The annual filing reports R$1,490,300,000 of revenue and
# R$156,270,000 of net income; the quarterly feed reports two negative
# quarters that sum, with the other two, to a bit over half of it.
KEPLER_REPORTED_REVENUE = {1: 357_230_020, 2: -46_157_000, 3: 112_262_000, 4: 398_662_020}
KEPLER_REPORTED_NET_INCOME = {1: 25_552_000, 2: -11_156_000, 3: 37_174_000, 4: 64_752_000}
KEPLER_ANNUAL = AnnualIncome(revenue=1_490_300_000, net_income=156_270_000)

# Petrobras, 2025. Same shape at a thousand times the size.
PETROBRAS_REPORTED_REVENUE = {
    1: 123_144_000_000, 2: -4_016_000_000, 3: 8_778_000_000, 4: 127_371_000_000,
}
PETROBRAS_REPORTED_NET_INCOME = {
    1: 35_331_000_000, 2: -8_557_000_000, 3: 6_073_000_000, 4: 15_653_000_000,
}
PETROBRAS_ANNUAL = AnnualIncome(revenue=497_549_000_000, net_income=110_605_000_000)

# Embraer, 2025. Same provider, same quarters, no bug. The control.
EMBRAER_REPORTED_REVENUE = {
    1: 6_405_270_000, 2: 10_270_363_000, 3: 10_866_683_000, 4: 14_340_918_000,
}
EMBRAER_REPORTED_NET_INCOME = {
    1: 470_895_000, 2: 397_477_000, 3: 688_122_000, 4: 435_543_000,
}
EMBRAER_ANNUAL = AnnualIncome(revenue=41_883_234_000, net_income=1_992_037_000)


class TestRunningSumRestatement:
    """Q1 to Q3 are cumulative sums of what was reported; Q4 stands alone.

    Q4 is never filed as a standalone period in Brazil. BRAPI derives it from
    the audited annual less the nine months already filed, which is the one
    part of its own arithmetic that uses a genuine year-to-date figure, so it
    arrives correct and must not be touched.
    """

    def test_reconstructs_kepler_weber(self):
        assert running_sum_restatement(KEPLER_REPORTED_REVENUE) == {
            1: 357_230_020, 2: 311_073_020, 3: 423_335_020, 4: 398_662_020,
        }

    def test_reconstructed_year_ties_to_the_audited_annual(self):
        restated = running_sum_restatement(KEPLER_REPORTED_NET_INCOME)
        assert sum(restated.values()) == KEPLER_ANNUAL.net_income

    def test_leaves_the_fourth_quarter_alone(self):
        restated = running_sum_restatement(KEPLER_REPORTED_REVENUE)
        assert restated[4] == KEPLER_REPORTED_REVENUE[4]

    def test_restates_a_year_still_in_progress(self):
        """2026 has two quarters filed and no annual to check against yet."""
        assert running_sum_restatement({1: 318_059_000, 2: -18_988_000}) == {
            1: 318_059_000, 2: 299_071_000,
        }

    def test_refuses_without_a_first_quarter_to_build_on(self):
        """Q2 and Q3 are differences against Q1. Absent it, nothing follows."""
        assert running_sum_restatement({2: -46_157_000, 3: 112_262_000}) is None

    def test_refuses_when_a_quarter_in_the_run_is_missing(self):
        assert running_sum_restatement({1: 100, 3: 50}) is None

    def test_carries_a_missing_value_through_without_inventing_one(self):
        """A null fourth quarter stays null rather than becoming a zero."""
        assert running_sum_restatement({1: 100, 2: 20, 3: 5, 4: None}) == {
            1: 100, 2: 120, 3: 125, 4: None,
        }

    def test_refuses_when_a_value_inside_the_run_is_missing(self):
        assert running_sum_restatement({1: 100, 2: None, 3: 5}) is None

    def test_works_on_decimals_for_per_share_figures(self):
        restated = running_sum_restatement(
            {1: Decimal("27.30"), 2: Decimal("-6.60"), 3: Decimal("4.70")},
        )
        assert restated == {1: Decimal("27.30"), 2: Decimal("20.70"), 3: Decimal("25.40")}


class TestChooseRestatement:
    """The audited annual decides, and it is allowed to decide neither."""

    def test_detects_the_bug_on_kepler_weber(self):
        assert choose_restatement(
            KEPLER_REPORTED_REVENUE, KEPLER_REPORTED_NET_INCOME, KEPLER_ANNUAL,
        ) == RUNNING_SUM

    def test_detects_the_bug_on_petrobras(self):
        assert choose_restatement(
            PETROBRAS_REPORTED_REVENUE, PETROBRAS_REPORTED_NET_INCOME, PETROBRAS_ANNUAL,
        ) == RUNNING_SUM

    def test_leaves_embraer_alone(self):
        assert choose_restatement(
            EMBRAER_REPORTED_REVENUE, EMBRAER_REPORTED_NET_INCOME, EMBRAER_ANNUAL,
        ) == AS_REPORTED

    def test_tolerates_the_provider_rounding_its_own_quarters(self):
        """Kepler's restated revenue misses its annual by R$80 in R$1.49bn."""
        assert choose_restatement(
            KEPLER_REPORTED_REVENUE, {}, AnnualIncome(revenue=1_490_300_000),
        ) == RUNNING_SUM

    def test_refuses_when_neither_reading_ties_to_the_annual(self):
        assert choose_restatement(
            {1: 10, 2: 20, 3: 30, 4: 40}, {}, AnnualIncome(revenue=999_999),
        ) == UNDECIDED

    def test_refuses_when_revenue_and_net_income_disagree(self):
        """One field cannot be differenced while the other is not."""
        assert choose_restatement(
            EMBRAER_REPORTED_REVENUE, KEPLER_REPORTED_NET_INCOME,
            AnnualIncome(revenue=EMBRAER_ANNUAL.revenue, net_income=KEPLER_ANNUAL.net_income),
        ) == UNDECIDED

    def test_decides_on_net_income_when_revenue_is_unavailable(self):
        """Banks and holdings often report no revenue line at all."""
        assert choose_restatement(
            {}, KEPLER_REPORTED_NET_INCOME, AnnualIncome(net_income=156_270_000),
        ) == RUNNING_SUM

    def test_refuses_with_no_annual_to_check_against(self):
        assert choose_restatement(
            KEPLER_REPORTED_REVENUE, KEPLER_REPORTED_NET_INCOME, AnnualIncome(),
        ) == UNDECIDED

    def test_refuses_on_a_part_year(self):
        """Three quarters cannot be compared with a twelve-month total."""
        assert choose_restatement(
            {1: 357_230_020, 2: -46_157_000, 3: 112_262_000}, {}, KEPLER_ANNUAL,
        ) == UNDECIDED

    def test_refuses_when_the_annual_is_zero(self):
        assert choose_restatement(
            {1: 1, 2: 2, 3: 3, 4: 4}, {}, AnnualIncome(revenue=0),
        ) == UNDECIDED


def _quarters(ticker, values_by_end_date):
    return [
        QuarterlyEarnings(
            ticker=ticker, end_date=end_date,
            revenue=revenue, net_income=net_income, eps=eps,
        )
        for end_date, (revenue, net_income, eps) in values_by_end_date.items()
    ]


class TestRestateQuarterlyEarnings:
    """The whole-company pass, which is what ingestion and the repair share."""

    def test_restates_only_the_year_the_annual_condemns(self):
        """BRAPI's pipeline broke in 2025. Kepler's 2024 came through clean."""
        quarters = _quarters("KEPL3", {
            date(2024, 3, 31): (380_311_000, 52_156_000, None),
            date(2024, 6, 30): (327_833_980, 37_004_000, None),
            date(2024, 9, 30): (439_052_000, 59_641_000, None),
            date(2024, 12, 31): (460_100_000, 50_382_008, None),
            date(2025, 3, 31): (357_230_020, 25_552_000, None),
            date(2025, 6, 30): (-46_157_000, -11_156_000, None),
            date(2025, 9, 30): (112_262_000, 37_174_000, None),
            date(2025, 12, 31): (398_662_020, 64_752_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2024: AnnualIncome(revenue=1_607_297_000, net_income=199_183_010),
            2025: KEPLER_ANNUAL,
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2024, 6, 30)].revenue == 327_833_980
        assert by_date[date(2025, 6, 30)].revenue == 311_073_020
        assert by_date[date(2025, 9, 30)].revenue == 423_335_020
        assert by_date[date(2025, 12, 31)].revenue == 398_662_020

    def test_carries_the_verdict_into_the_year_still_in_progress(self):
        """2026 has no annual yet, and is the year a reader is looking at.

        The verdict is a property of the provider's pipeline, not of the
        quarter, so the most recent year it was measured on is the best
        evidence available for the one still open.
        """
        quarters = _quarters("KEPL3", {
            date(2025, 3, 31): (357_230_020, 25_552_000, None),
            date(2025, 6, 30): (-46_157_000, -11_156_000, None),
            date(2025, 9, 30): (112_262_000, 37_174_000, None),
            date(2025, 12, 31): (398_662_020, 64_752_000, None),
            date(2026, 3, 31): (318_059_000, 17_128_000, None),
            date(2026, 6, 30): (-18_988_000, -10_810_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {2025: KEPLER_ANNUAL})
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2026, 6, 30)].revenue == 299_071_000
        assert by_date[date(2026, 6, 30)].net_income == 6_318_000

    def test_does_not_carry_a_clean_verdict_backwards(self):
        """A year before any measured one keeps what the provider sent."""
        quarters = _quarters("EMBR3", {
            date(2023, 3, 31): (100, 10, None),
            date(2023, 6, 30): (-500, -50, None),
            date(2023, 9, 30): (200, 20, None),
            date(2023, 12, 31): (300, 30, None),
            date(2025, 3, 31): (6_405_270_000, 470_895_000, None),
            date(2025, 6, 30): (10_270_363_000, 397_477_000, None),
            date(2025, 9, 30): (10_866_683_000, 688_122_000, None),
            date(2025, 12, 31): (14_340_918_000, 435_543_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {2025: EMBRAER_ANNUAL})
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2023, 6, 30)].revenue == -500

    def test_restates_earnings_per_share_alongside_net_income(self):
        """EPS is net income over shares, so it carries the same defect."""
        quarters = _quarters("PETR4", {
            date(2025, 3, 31): (123_144_000_000, 35_331_000_000, Decimal("27.30")),
            date(2025, 6, 30): (-4_016_000_000, -8_557_000_000, Decimal("-6.60")),
            date(2025, 9, 30): (8_778_000_000, 6_073_000_000, Decimal("4.70")),
            date(2025, 12, 31): (127_371_000_000, 15_653_000_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {2025: PETROBRAS_ANNUAL})
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2025, 6, 30)].eps == Decimal("20.70")
        assert by_date[date(2025, 9, 30)].eps == Decimal("25.40")
        assert by_date[date(2025, 12, 31)].eps is None

    def test_leaves_plausible_figures_alone_with_no_annuals_at_all(self):
        """A provider outage on the annual module must not restate anything.

        Nothing here is impossible as filed, so there is no evidence to act
        on and no guess is made. A year that *is* impossible as filed is a
        different matter, covered by TestAStaleCleanVerdictIsNotTrusted.
        """
        quarters = _quarters("EMBR3", {
            date(2025, 3, 31): (6_405_270_000, 470_895_000, None),
            date(2025, 6, 30): (10_270_363_000, 397_477_000, None),
            date(2025, 9, 30): (10_866_683_000, 688_122_000, None),
            date(2025, 12, 31): (14_340_918_000, 435_543_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {})

        assert [quarter.revenue for quarter in restated] == [
            6_405_270_000, 10_270_363_000, 10_866_683_000, 14_340_918_000,
        ]

    def test_refuses_a_carried_verdict_that_would_invent_negative_revenue(self):
        """The carried verdict is evidence, not proof, so it is still checked.

        If BRAPI repairs its pipeline mid-year the carried verdict becomes
        wrong, and the tell is a restatement that drives revenue below zero.
        No company earns negative revenue, so the reading is rejected and the
        year is left as filed until its own annual can settle it.
        """
        quarters = _quarters("KEPL3", {
            date(2025, 3, 31): (357_230_020, 25_552_000, None),
            date(2025, 6, 30): (-46_157_000, -11_156_000, None),
            date(2025, 9, 30): (112_262_000, 37_174_000, None),
            date(2025, 12, 31): (398_662_020, 64_752_000, None),
            date(2026, 3, 31): (100_000, 5_000, None),
            date(2026, 6, 30): (-900_000, -50_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {2025: KEPLER_ANNUAL})
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2026, 6, 30)].revenue == -900_000

    def test_returns_the_same_objects_it_was_given(self):
        """Ingestion hands these straight to bulk_create, so identity matters."""
        quarters = _quarters("KEPL3", {date(2025, 3, 31): (1, 1, None)})
        assert restate_quarterly_earnings(quarters, {}) is not None
        assert all(isinstance(quarter, QuarterlyEarnings) for quarter in quarters)


# Sao Martinho closes its books on 31 March, so its fiscal 2026 runs from the
# June 2025 quarter to the March 2026 one. Camil closes on 28 February. Both
# are real B3 filers on this path, and neither is a calendar-year company.
SAO_MARTINHO_YEAR_END_MONTH = 3
CAMIL_YEAR_END_MONTH = 2


class TestOffCalendarFilers:
    """Not every B3 company closes its books on 31 December.

    Sugar and ethanol producers close after the harvest. Grouping their
    quarters by calendar year splits one fiscal year across two buckets, so
    no bucket ever holds the four quarters the annual covers and the
    reconciliation can never decide anything.
    """

    def test_groups_a_march_year_end_into_one_fiscal_year(self):
        quarters = _quarters("SMTO3", {
            date(2025, 6, 30): (1_857_161_000, 100, None),
            date(2025, 9, 30): (-118_517_000, 100, None),
            date(2025, 12, 31): (-146_342_000, 100, None),
            date(2026, 3, 31): (2_243_658_000, 100, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2026: AnnualIncome(revenue=7_431_765_000, end_month=SAO_MARTINHO_YEAR_END_MONTH),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2025, 9, 30)].revenue == 1_738_644_000
        assert by_date[date(2025, 12, 31)].revenue == 1_592_302_000
        assert sum(q.revenue for q in restated) == 7_431_765_000

    def test_exempts_the_quarter_that_closes_the_fiscal_year(self):
        """March is this filer's fourth quarter, not its first."""
        quarters = _quarters("SMTO3", {
            date(2025, 6, 30): (1_857_161_000, 100, None),
            date(2025, 9, 30): (-118_517_000, 100, None),
            date(2025, 12, 31): (-146_342_000, 100, None),
            date(2026, 3, 31): (2_243_658_000, 100, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2026: AnnualIncome(revenue=7_431_765_000, end_month=SAO_MARTINHO_YEAR_END_MONTH),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2026, 3, 31)].revenue == 2_243_658_000

    def test_handles_a_february_year_end(self):
        quarters = _quarters("CAML3", {
            date(2025, 5, 31): (2_687_327_000, 100, None),
            date(2025, 8, 31): (292_342_020, 100, None),
            date(2025, 11, 30): (-34_418_000, 100, None),
            date(2026, 2, 28): (2_502_755_960, 100, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2026: AnnualIncome(revenue=11_115_003_000, end_month=CAMIL_YEAR_END_MONTH),
        })

        assert sum(quarter.revenue for quarter in restated) == 11_115_003_000

    def test_still_treats_a_december_filer_as_a_calendar_year(self):
        quarters = _quarters("KEPL3", {
            date(2025, 3, 31): (357_230_020, 25_552_000, None),
            date(2025, 6, 30): (-46_157_000, -11_156_000, None),
            date(2025, 9, 30): (112_262_000, 37_174_000, None),
            date(2025, 12, 31): (398_662_020, 64_752_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2025: AnnualIncome(revenue=1_490_300_000, net_income=156_270_000, end_month=12),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2025, 6, 30)].revenue == 311_073_020


class TestAStaleCleanVerdictIsNotTrusted:
    """BRAPI's pipeline broke during 2025, so 2024 clears nothing about 2025.

    Natura's 2024 reconciles as filed to the rupiah, and BRAPI publishes no
    2025 annual, so the carried verdict says the company is healthy while its
    June 2025 quarter reports minus R$2.5bn of revenue. No company earns
    negative revenue. Where one reading of an undecided year is impossible
    and the other is not, the possible one wins.
    """

    def test_repairs_a_negative_year_a_clean_predecessor_would_suppress(self):
        quarters = _quarters("NTCO3", {
            date(2024, 3, 31): (6_105_253_000, 100, None),
            date(2024, 6, 30): (7_352_632_000, 100, None),
            date(2024, 9, 30): (2_884_559_000, 100, None),
            date(2024, 12, 31): (7_747_361_000, 100, None),
            date(2025, 3, 31): (6_679_433_000, 100, None),
            date(2025, 6, 30): (-2_528_602_000, 100, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2024: AnnualIncome(revenue=24_089_805_000, end_month=12),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2024, 6, 30)].revenue == 7_352_632_000
        assert by_date[date(2025, 6, 30)].revenue == 4_150_831_000

    def test_leaves_a_negative_the_running_sum_cannot_resolve(self):
        """If both readings are impossible, neither is evidence for the other."""
        quarters = _quarters("XXXX3", {
            date(2025, 3, 31): (100, 10, None),
            date(2025, 6, 30): (-900, -50, None),
        })
        restated = restate_quarterly_earnings(quarters, {})
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2025, 6, 30)].revenue == -900

    def test_leaves_a_year_with_no_negative_alone(self):
        """Absent a negative there is no evidence, and no guess is made."""
        quarters = _quarters("EMBR3", {
            date(2026, 3, 31): (7_584_756_000, 100, None),
            date(2026, 6, 30): (11_335_557_000, 100, None),
        })
        restated = restate_quarterly_earnings(quarters, {})
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2026, 6, 30)].revenue == 11_335_557_000


class TestAnAnnualThatSettlesNothing:
    """An annual that cannot be compared has not cleared the year.

    For a filer closing in March, BRAPI publishes no quarter for the closing
    period at all, so the fiscal year holds three quarters and can never be
    summed against a twelve-month total. Treating that silence as a clean
    bill of health left Sao Martinho, Camil and Jalles Machado reporting
    negative revenue with an annual filing sitting right beside them.
    """

    def test_falls_back_to_the_undecided_reading(self):
        quarters = _quarters("SMTO3", {
            date(2025, 6, 30): (1_857_161_000, 100, None),
            date(2025, 9, 30): (-118_517_000, 100, None),
            date(2025, 12, 31): (-146_342_000, 100, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2026: AnnualIncome(revenue=7_431_765_000, end_month=3),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2025, 9, 30)].revenue == 1_738_644_000
        assert by_date[date(2025, 12, 31)].revenue == 1_592_302_000

    def test_does_not_update_the_carried_verdict(self):
        """No verdict was reached, so the next year inherits nothing from it."""
        quarters = _quarters("SMTO3", {
            date(2025, 6, 30): (1_000, 100, None),
            date(2025, 9, 30): (2_000, 100, None),
            date(2025, 12, 31): (3_000, 100, None),
            date(2026, 6, 30): (4_000, 100, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2026: AnnualIncome(revenue=99_999_999, end_month=3),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2026, 6, 30)].revenue == 4_000


class TestAnAnnualFiledAsTheClosingQuarter:
    """An earlier sync stored annual statements in quarter rows.

    ``fetch_income_statements`` falls back to the annual module when the
    quarterly one comes back empty, and those statements were written as
    reporting periods. For a filer closing in March the annual lands on
    31 March, which is exactly where its closing quarter belongs, so it
    masqueraded as that quarter and survived every later sync. Sao Martinho's
    fiscal 2026 summed to R$12.6bn against R$7.4bn filed, overstated by 70%.

    A closing quarter equal to the whole year, beside three other quarters
    that are not zero, is arithmetically impossible. It is derived from the
    year less the three, the same way ``cvm_fourth_quarter`` derives it.
    """

    def test_derives_the_closing_quarter_from_the_year(self):
        quarters = _quarters("SMTO3", {
            date(2025, 6, 30): (1_857_161_000, 62_829_000, None),
            date(2025, 9, 30): (-118_517_000, 113_587_000, None),
            date(2025, 12, 31): (-146_342_000, 247_664_990, None),
            date(2026, 3, 31): (7_431_765_000, 836_177_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2026: AnnualIncome(
                revenue=7_431_765_000, net_income=836_177_000, end_month=3,
            ),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2025, 9, 30)].revenue == 1_738_644_000
        assert by_date[date(2025, 12, 31)].revenue == 1_592_302_000
        assert by_date[date(2026, 3, 31)].revenue == 2_243_658_000
        assert sum(quarter.revenue for quarter in restated) == 7_431_765_000

    def test_leaves_a_company_that_really_earns_it_all_in_one_quarter(self):
        """Deriving is self-consistent when the other quarters are zero."""
        quarters = _quarters("XXXX3", {
            date(2025, 3, 31): (0, 0, None),
            date(2025, 6, 30): (0, 0, None),
            date(2025, 9, 30): (0, 0, None),
            date(2025, 12, 31): (5_000, 500, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2025: AnnualIncome(revenue=5_000, net_income=500, end_month=12),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2025, 12, 31)].revenue == 5_000

    def test_does_not_fire_on_a_year_that_reconciles(self):
        quarters = _quarters("EMBR3", {
            date(2025, 3, 31): (6_405_270_000, 470_895_000, None),
            date(2025, 6, 30): (10_270_363_000, 397_477_000, None),
            date(2025, 9, 30): (10_866_683_000, 688_122_000, None),
            date(2025, 12, 31): (14_340_918_000, 435_543_000, None),
        })
        restated = restate_quarterly_earnings(quarters, {
            2025: AnnualIncome(
                revenue=41_883_234_000, net_income=1_992_037_000, end_month=12,
            ),
        })
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2025, 12, 31)].revenue == 14_340_918_000

    def test_leaves_the_quarter_alone_without_an_annual_to_derive_from(self):
        quarters = _quarters("SMTO3", {
            date(2025, 6, 30): (1_857_161_000, 100, None),
            date(2025, 9, 30): (-118_517_000, 100, None),
            date(2025, 12, 31): (-146_342_000, 100, None),
            date(2026, 3, 31): (7_431_765_000, 100, None),
        })
        restated = restate_quarterly_earnings(quarters, {})
        by_date = {quarter.end_date: quarter for quarter in restated}

        assert by_date[date(2026, 3, 31)].revenue == 7_431_765_000

    def test_deriving_twice_changes_nothing(self):
        """The derived year ties as it stands, so the second pass is a no-op."""
        stored = {
            date(2025, 6, 30): (1_857_161_000, 62_829_000, None),
            date(2025, 9, 30): (-118_517_000, 113_587_000, None),
            date(2025, 12, 31): (-146_342_000, 247_664_990, None),
            date(2026, 3, 31): (7_431_765_000, 836_177_000, None),
        }
        annuals = {2026: AnnualIncome(
            revenue=7_431_765_000, net_income=836_177_000, end_month=3,
        )}
        quarters = _quarters("SMTO3", stored)
        restate_quarterly_earnings(quarters, annuals)
        once = {quarter.end_date: quarter.revenue for quarter in quarters}
        restate_quarterly_earnings(quarters, annuals)
        twice = {quarter.end_date: quarter.revenue for quarter in quarters}

        assert once == twice
        assert twice[date(2026, 3, 31)] == 2_243_658_000
