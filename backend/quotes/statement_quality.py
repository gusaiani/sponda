"""Normalisation of provider figures that are wrong in a recognisable way.

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
"""
from __future__ import annotations


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
