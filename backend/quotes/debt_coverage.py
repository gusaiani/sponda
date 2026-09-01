"""Debt coverage: years of average earnings or free cash flow needed to repay debt.

Two flavours share one formula, total debt over a positive average:

* the loose pair, ``debt_to_avg_earnings`` / ``debt_to_avg_fcf``, divides by
  the average over up to 10 years of history (a company with six years is
  averaged over six);
* the strict windows, ``debt_to_avg_earnings_N`` / ``debt_to_avg_fcf_N``,
  divide by the average over exactly N years and are ``None`` when the
  company has not filed N years, the same contract as ``pe1``..``pe15``.
"""
from decimal import Decimal
from typing import Mapping, Optional

from .models import (
    DEBT_COVERAGE_WINDOW_YEARS,
    debt_coverage_window_field,
)

# The widest ratio IndicatorSnapshot's DecimalField(max_digits=12,
# decimal_places=4) can hold. Anything beyond it (debt against near-zero
# average earnings) is reported as None rather than failing the row write.
DEBT_COVERAGE_MAX_RATIO = Decimal("99999999.9999")


def debt_coverage_ratio(
    total_debt: Optional[Decimal | int | float],
    average_cash_generation: Optional[Decimal | int | float],
) -> Optional[Decimal]:
    """Total debt divided by a positive average; ``None`` otherwise.

    ``None`` when either input is missing, when the average is zero or
    negative (a loss-making window cannot repay anything), and when the
    ratio would not fit the snapshot column.
    """
    if total_debt is None or average_cash_generation is None:
        return None
    average = Decimal(str(average_cash_generation))
    if average <= 0:
        return None
    ratio = Decimal(str(total_debt)) / average
    if ratio > DEBT_COVERAGE_MAX_RATIO:
        return None
    return ratio


def debt_coverage_windows(
    total_debt: Optional[Decimal | int | float],
    average_earnings_by_years: Mapping[int, Optional[Decimal]],
    average_fcf_by_years: Mapping[int, Optional[Decimal]],
) -> dict[str, Optional[Decimal]]:
    """Every strict debt-coverage window, keyed by snapshot field name."""
    windows: dict[str, Optional[Decimal]] = {}
    for years in DEBT_COVERAGE_WINDOW_YEARS:
        windows[debt_coverage_window_field("debt_to_avg_earnings", years)] = (
            debt_coverage_ratio(total_debt, average_earnings_by_years.get(years))
        )
        windows[debt_coverage_window_field("debt_to_avg_fcf", years)] = (
            debt_coverage_ratio(total_debt, average_fcf_by_years.get(years))
        )
    return windows
