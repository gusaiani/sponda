"""Normalisation of provider figures that are wrong in a recognisable way.

Two rules live here. Both describe a figure a provider reports confidently
and that the surrounding statement contradicts, and both discard it rather
than store something that reads as fact.

Missing net income, encoded as zero
-----------------------------------
Both BRAPI and FMP encode a missing net income as a literal ``0`` on some
filings rather than omitting the field. Stored as-is, that zero is
indistinguishable from a real result, and it flows straight into the
inflation-adjusted earnings average behind P/E10, dragging the average down
and inflating the multiple for every window that contains it.

The tell is revenue. A company that booked real revenue and *exactly* zero
profit, to the cent, is a provider artifact. BBAS3 reported around R$31bn of
revenue per quarter and precisely R$0 of profit for every quarter from 2013
to 2019. A company with no revenue can genuinely earn nothing, so that case
is left alone.

Debt that vanishes without the liabilities to match
---------------------------------------------------
See ``is_implausible_debt_collapse``.
"""
from __future__ import annotations

from decimal import Decimal


def normalize_net_income(net_income, revenue):
    """Return net income, or None when the provider's zero cannot be real.

    Applied at ingestion by both provider modules so the rule has one
    definition. ``repair_zero_net_income`` applies the same rule to rows
    already in the database.
    """
    if net_income is None or net_income != 0:
        return net_income
    if revenue is not None and revenue > 0:
        return None
    return net_income


# A quarter's debt may fall by any amount for real reasons, but the cash that
# retired it has to show up somewhere: total liabilities fall with it. FMP
# publishes a fresh 10-Q within hours of filing and sometimes mis-tags the
# debt lines on that first pass, dropping billions into
# `otherNonCurrentLiabilities` while `totalDebt` collapses and the totals
# stay correct. Salesforce's Q2 FY2027, filed 2026-08-26, reported $2.46bn of
# debt against $71.2bn of liabilities the quarter after $41.9bn against
# $72.4bn. The company had just issued $25bn of notes and drawn a $6bn term
# loan to fund a buyback, so a screener sorting on debt/equity ranked it as
# pristine at the exact moment it levered up. The figure is not merely wrong,
# it is wrong in the direction that hides risk, which is why it is discarded
# rather than kept.
#
# Three conditions have to hold together, each guarding against a different
# way a real quarter could look like this one:
#
#   1. The debt nearly vanished. Partial paydowns and refinancings are
#      routine; near-total disappearance inside one quarter is not.
#   2. The amount that vanished was material against the balance sheet. A
#      company can clear a small facility without moving its totals.
#   3. Total liabilities did not absorb it. This is the accounting identity
#      doing the work: if the debt were genuinely retired, the liabilities
#      would have fallen too.

SURVIVING_SHARE_OF_A_COLLAPSE = Decimal("0.25")
MATERIAL_SHARE_OF_LIABILITIES = Decimal("0.25")
ABSORBED_SHARE_OF_A_REPAYMENT = Decimal("0.5")


def is_implausible_debt_collapse(
    previous_debt,
    previous_total_liabilities,
    debt,
    total_liabilities,
) -> bool:
    """Return True when this quarter's debt cannot be reconciled with the last.

    All four figures are required: a missing one leaves nothing to compare,
    and silence is not evidence of a problem.
    """
    if debt is None or previous_debt is None:
        return False
    if total_liabilities is None or previous_total_liabilities is None:
        return False
    if previous_debt <= 0 or previous_total_liabilities <= 0:
        return False

    # Decimal, not float: statement figures run to fifteen digits in
    # rupiah and dong, past the point where a float multiplication is exact.
    if debt > Decimal(previous_debt) * SURVIVING_SHARE_OF_A_COLLAPSE:
        return False

    vanished_debt = Decimal(previous_debt - debt)
    if vanished_debt < Decimal(previous_total_liabilities) * MATERIAL_SHARE_OF_LIABILITIES:
        return False

    shed_liabilities = previous_total_liabilities - total_liabilities
    return shed_liabilities < vanished_debt * ABSORBED_SHARE_OF_A_REPAYMENT


def discard_implausible_debt_collapses(balance_sheets) -> list:
    """Null `total_debt` on every sheet whose debt vanished unaccountably.

    Reads the sheets in date order regardless of the order they arrive in,
    and compares each against the last quarter whose debt it still trusts.
    A discarded quarter must not become the baseline for the next one, or a
    single bad filing would either erase the correction that follows it or
    leave the quarters after it with nothing to be measured against.

    Mutates the sheets in place and returns them, so a caller can pass the
    list straight on to `bulk_create`.
    """
    trusted_debt = None
    trusted_total_liabilities = None

    for sheet in sorted(balance_sheets, key=lambda sheet: sheet.end_date):
        if is_implausible_debt_collapse(
            trusted_debt,
            trusted_total_liabilities,
            sheet.total_debt,
            sheet.total_liabilities,
        ):
            sheet.total_debt = None
            continue

        if sheet.total_debt is not None:
            trusted_debt = sheet.total_debt
            trusted_total_liabilities = sheet.total_liabilities

    return balance_sheets
