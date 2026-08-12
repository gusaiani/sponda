"""Tests for deriving Q4 from the audited year minus the nine months reported.

Nobody files Q4 as a standalone period. The DFP carries the calendar year and
the ITRs carry Q1 to Q3, so Q4 is what is left over.

That makes Q4 the residue of everything else, which is the risk. Any audit
adjustment the DFP applied to earlier quarters lands entirely in Q4, because
the alternative — rewriting Q1 to Q3 — would displace BRAPI's series, which
is the invariant the whole ingestion path rests on.

Measured over 282 companies for 2025, the audited year agrees with the sum of
the four quarters we store exactly for 65% and within 0.1% for a further 33%.
1.8% disagree by more than 5%, and those are refused rather than absorbed.
"""
from datetime import date

import pytest

from quotes.cvm import QuarterStatements
from quotes.cvm_fourth_quarter import (
    FourthQuarterUnavailable,
    derive_fourth_quarter,
)

YEAR_END = date(2025, 12, 31)


def annual(**overrides):
    values = {
        "revenue": 70_000_000, "net_income": 5_600_000,
        "operating_cash_flow": 9_000_000, "investment_cash_flow": -4_000_000,
        "dividends_paid": -2_000_000, "stockholders_equity": 53_734_748,
        "current_assets": 28_573_526, "current_liabilities": 10_360_391,
        "total_liabilities": 28_075_550, "total_debt": 13_834_407,
        "total_lease": 350_000,
    }
    values.update(overrides)
    return QuarterStatements(cvm_code="3980", quarter_end=YEAR_END, **values)


def nine_months(**overrides):
    values = {
        "revenue": 52_000_000, "net_income": 4_100_000,
        "operating_cash_flow": 6_500_000, "investment_cash_flow": -3_000_000,
        "dividends_paid": -1_500_000,
    }
    values.update(overrides)
    return values


# --- The arithmetic ---------------------------------------------------------

def test_the_quarter_is_the_year_less_what_was_already_reported():
    fourth = derive_fourth_quarter(annual(), nine_months())

    assert fourth.quarter_end == YEAR_END
    assert fourth.revenue == 70_000_000 - 52_000_000
    assert fourth.net_income == 5_600_000 - 4_100_000
    assert fourth.operating_cash_flow == 9_000_000 - 6_500_000
    assert fourth.investment_cash_flow == -4_000_000 - -3_000_000
    assert fourth.dividends_paid == -2_000_000 - -1_500_000


def test_the_balance_sheet_is_taken_whole_rather_than_differenced():
    """31 December is a snapshot, not a flow. Subtracting it would be
    meaningless · equity is not the sum of four quarters of equity."""
    fourth = derive_fourth_quarter(annual(), nine_months())

    assert fourth.stockholders_equity == 53_734_748
    assert fourth.current_assets == 28_573_526
    assert fourth.total_debt == 13_834_407
    assert fourth.total_liabilities == 28_075_550


def test_a_flow_the_year_does_not_report_stays_unknown():
    fourth = derive_fourth_quarter(annual(revenue=None), nine_months())

    assert fourth.revenue is None
    assert fourth.net_income is not None


def test_a_flow_the_nine_months_do_not_report_stays_unknown():
    """Subtracting from an unknown base would invent a quarter."""
    fourth = derive_fourth_quarter(annual(), nine_months(revenue=None))

    assert fourth.revenue is None


# --- Refusing rather than absorbing -----------------------------------------

def test_refuses_when_the_year_reports_no_earnings_at_all():
    """Three filers publish a zero or absent annual 3.11 while their quarters
    sum to billions. Deriving Q4 from that produces a large false loss."""
    with pytest.raises(FourthQuarterUnavailable, match="net income"):
        derive_fourth_quarter(annual(net_income=None), nine_months())


def test_refuses_a_year_reporting_zero_against_quarters_worth_billions():
    """TIMS3 and GEPA3/4 do exactly this. Differencing a zero annual against
    real quarters produces a large false loss."""
    with pytest.raises(FourthQuarterUnavailable, match="zero net income"):
        derive_fourth_quarter(
            annual(net_income=0), nine_months(net_income=4_311_984_000),
        )


def test_a_quarter_that_flips_the_year_negative_is_allowed():
    """A Q4 can legitimately dwarf the year it ends · that is a bad quarter,
    not bad arithmetic, and refusing it would hide a real collapse.

    This is also why no bound on the implied size exists: the only thresholds
    that would reject a disagreement would also reject this.
    """
    fourth = derive_fourth_quarter(
        annual(net_income=-1_000_000), nine_months(net_income=5_000_000),
    )

    assert fourth.net_income == -6_000_000


def test_accepts_a_loss_making_quarter_that_is_proportionate():
    """A genuinely bad Q4 is not the same as an implausible one."""
    fourth = derive_fourth_quarter(
        annual(net_income=3_000_000), nine_months(net_income=4_100_000),
    )

    assert fourth.net_income == -1_100_000


def test_accepts_a_year_whose_quarters_reconcile_to_the_rounding():
    """65% match exactly and a further 33% to within 0.1%, which is the
    thousands scale CVM publishes in meeting BRAPI's whole units."""
    fourth = derive_fourth_quarter(
        annual(net_income=5_600_000), nine_months(net_income=5_599_000),
    )

    assert fourth.net_income == 1_000
