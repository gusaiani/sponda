"""Strict trailing-window averages over a company's filed periods.

Shared by the P/E windows (``pe10.calculate_pe_windows``) and the
free-cash-flow windows (``pfcf10.calculate_fcf_windows``) so both families
count years the same way: a window of N years covers exactly
``N × periods_per_year`` trailing filings, and a window the company cannot
fill is ``None`` rather than a quietly shorter average.
"""
from decimal import Decimal
from typing import Optional, Sequence


def strict_window_averages(
    adjusted_period_values: Sequence[Decimal],
    periods_per_year: int,
    max_years: int,
) -> dict:
    """Average ``adjusted_period_values`` (newest first) over 1..max_years years.

    Returns dict with:
        average_by_years: {1: Decimal|None, ..., max_years: Decimal|None},
            the annual average over exactly that many years, ``None`` when
            the company has not filed that many years of periods.
        years_available: int, the widest window the values can fill,
            capped at ``max_years``.
    """
    years_available = min(max_years, len(adjusted_period_values) // periods_per_year)

    cumulative_by_period_count = [Decimal("0")]
    for value in adjusted_period_values:
        cumulative_by_period_count.append(cumulative_by_period_count[-1] + value)

    average_by_years: dict[int, Optional[Decimal]] = {}
    for years in range(1, max_years + 1):
        if years > years_available:
            average_by_years[years] = None
            continue
        window_total = cumulative_by_period_count[years * periods_per_year]
        average_by_years[years] = window_total / Decimal(years)

    return {
        "average_by_years": average_by_years,
        "years_available": years_available,
    }
