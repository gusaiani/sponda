"""PE10 (Shiller P/E) calculation logic — pure functions.

The N-year window covers exactly N × periods_per_year trailing filings
(4 for quarterly reporters, 2 for semi-annual ones like Rio Tinto,
1 for annual-only reporters). When the most recent fiscal year only
has a partial set of periods reported (e.g. mid-year, with only Q1
in), we backfill from older years so the denominator divides an honest
N years of earnings — instead of treating the partial-current year as
if it were a full year and under-weighting the average.
"""
from collections import defaultdict
from decimal import Decimal

from typing import Optional

from .fx import market_cap_in_reported_currency
from .fiscal_year import fiscal_year_of
from .inflation import get_inflation_adjustment_factors
from .models import QuarterlyEarnings
from .reporting_frequency import QUARTERLY_PERIODS_PER_YEAR, infer_periods_per_year
from .trailing_windows import strict_window_averages

# Every P/E window the screener offers: PE1 through PE15.
PE_WINDOW_MAX_YEARS = 15
PE_WINDOW_YEARS = tuple(range(1, PE_WINDOW_MAX_YEARS + 1))

# The debt-coverage ratios average earnings over "up to a decade" — a looser
# notion than the strict windows, kept for continuity with the original PE10.
LOOSE_AVERAGE_MAX_YEARS = 10


def get_annual_earnings(ticker: str, max_years: int = 10) -> list[dict]:
    """
    Return annual net income breakdowns covering the trailing
    ``max_years * 4`` quarters, grouped by calendar year.

    The most-recent entry may be a partial year (current fiscal year
    not yet closed); the oldest entry may also be a partial year, when
    the trailing window does not align with a calendar boundary. The
    caller that wants the annual average MUST sum adjusted values
    across the window and divide by ``max_years`` (not ``len(result)``).
    """
    quarters = QuarterlyEarnings.objects.filter(
        ticker=ticker.upper(),
    ).order_by("-end_date")[: max_years * 4]

    yearly = defaultdict(lambda: {"net_income": Decimal("0"), "quarters": 0,
                                  "quarterly_detail": [], "last_end_date": None})
    for q in quarters:
        if q.net_income is None:
            continue
        year = fiscal_year_of(q)
        yearly[year]["last_end_date"] = q.end_date
        yearly[year]["net_income"] += q.net_income
        yearly[year]["quarters"] += 1
        yearly[year]["quarterly_detail"].append({
            "end_date": q.end_date.isoformat(),
            "net_income": q.net_income,
        })

    return [
        {
            "year": year,
            # When the fiscal year closed in calendar time. The CPI series
            # is calendar time and the fiscal label is not: a filer's 2027
            # can already be open in 2026, and looking that up would find
            # nothing and quietly adjust by 1.
            "inflation_year": data["last_end_date"].year,
            "net_income": data["net_income"],
            "quarters": data["quarters"],
            "quarterly_detail": sorted(data["quarterly_detail"], key=lambda x: x["end_date"]),
        }
        for year, data in sorted(yearly.items(), reverse=True)
    ]


def calculate_pe_windows(
    ticker: str,
    market_cap: Optional[Decimal],
    max_years: int = PE_WINDOW_MAX_YEARS,
) -> dict:
    """Compute the strict P/E window family (PE1..PE{max_years}) in one pass.

    Strict: ``pe_by_years[Y]`` is ``None`` unless the company has the full
    ``Y`` years of earnings history (honouring its filing frequency), so a
    PE15 is never quietly a PE8. ``years_available`` reports the widest
    honest window. ``average_net_income_by_years`` is the strict average
    behind each window, reported even when the P/E itself is ``None``
    (no market cap, or a loss-making window) so the debt-coverage windows
    can divide by exactly ``Y`` years of earnings.
    ``avg_adjusted_net_income`` keeps the historical loose "up to 10 years"
    average that the unwindowed debt-coverage ratios divide by.

    Returns dict with:
        pe_by_years: {1: float|None, ..., max_years: float|None}
        average_net_income_by_years: {1: Decimal|None, ..., max_years: Decimal|None}
        years_available: int
        avg_adjusted_net_income: float or None
    """
    empty_windows = {years: None for years in range(1, max_years + 1)}
    annual_data = get_annual_earnings(ticker, max_years=max_years)
    if not annual_data:
        return {
            "pe_by_years": empty_windows,
            "average_net_income_by_years": dict(empty_windows),
            "years_available": 0,
            "avg_adjusted_net_income": None,
        }

    periods_per_year = infer_periods_per_year(annual_data)
    inflation_factors = get_inflation_adjustment_factors(
        ticker, [year_data["inflation_year"] for year_data in annual_data],
    )

    adjusted_period_incomes: list[Decimal] = []
    for year_data in annual_data:  # newest year first
        factor = inflation_factors.get(year_data["inflation_year"], Decimal("1"))
        for period in reversed(year_data["quarterly_detail"]):  # newest first
            adjusted_period_incomes.append(Decimal(str(period["net_income"])) * factor)

    windows = strict_window_averages(
        adjusted_period_incomes, periods_per_year=periods_per_year, max_years=max_years,
    )
    years_available = windows["years_available"]
    average_net_income_by_years = windows["average_by_years"]

    loose_years = min(LOOSE_AVERAGE_MAX_YEARS, years_available)
    average_net_income = (
        float(average_net_income_by_years[loose_years]) if loose_years else None
    )

    market_cap_reported = (
        market_cap_in_reported_currency(market_cap, ticker)
        if market_cap is not None
        else None
    )
    if market_cap_reported is None or years_available == 0:
        return {
            "pe_by_years": empty_windows,
            "average_net_income_by_years": average_net_income_by_years,
            "years_available": years_available,
            "avg_adjusted_net_income": average_net_income,
        }

    pe_by_years: dict[int, Optional[float]] = {}
    for years, window_average in average_net_income_by_years.items():
        if window_average is None or window_average <= 0:
            pe_by_years[years] = None
            continue
        pe_by_years[years] = round(float(market_cap_reported / window_average), 2)

    return {
        "pe_by_years": pe_by_years,
        "average_net_income_by_years": average_net_income_by_years,
        "years_available": years_available,
        "avg_adjusted_net_income": average_net_income,
    }


def calculate_pe10(ticker: str, market_cap: Decimal, max_years: int = 10) -> dict:
    """
    Calculate PE10 for a given ticker using Market Cap / Avg Adjusted Net Income.

    PE10 = Market Cap / Average Inflation-Adjusted Annual Net Income (10 years)

    Returns dict with:
        pe10: float or None
        avg_adjusted_net_income: float or None
        years_of_data: int
        label: str (e.g., "PE10" or "PE7")
        error: str or None
        calculation_details: list of yearly breakdowns
    """
    annual_data = get_annual_earnings(ticker, max_years=max_years)

    if not annual_data:
        return {
            "pe10": None,
            "avg_adjusted_net_income": None,
            "years_of_data": 0,
            "label": "PE0",
            "error": "Sem dados de lucro disponíveis",
            "annual_data_flag": False,
            "periods_per_year": QUARTERLY_PERIODS_PER_YEAR,
            "calculation_details": [],
        }

    # Cap the window to the largest whole-year count this ticker can
    # actually fill, honouring its filing frequency. A 13-quarter
    # quarterly reporter with max_years=10 yields a PE3 (12 trailing
    # quarters / 3 years); a semi-annual reporter with 26 filings
    # yields a PE13, not a PE6.
    periods_per_year = infer_periods_per_year(annual_data)
    total_periods = sum(d["quarters"] for d in annual_data)
    effective_years = min(max_years, total_periods // periods_per_year)
    if effective_years == 0:
        return {
            "pe10": None,
            "avg_adjusted_net_income": None,
            "years_of_data": 0,
            "label": "PE0",
            "error": "Sem dados de lucro disponíveis",
            "annual_data_flag": False,
            "periods_per_year": periods_per_year,
            "calculation_details": [],
        }
    target_periods = effective_years * periods_per_year

    # Keyed on when each fiscal year closed, not on its label: the CPI
    # series is calendar time and a filer's 2027 can already be open in
    # 2026. See pe10.get_annual_earnings.
    years = [d["inflation_year"] for d in annual_data]
    ipca_factors = get_inflation_adjustment_factors(ticker, years)

    adjusted_values: list[Decimal] = []
    yearly_breakdown = []
    collected = 0

    for year_data in annual_data:
        if collected >= target_periods:
            break
        remaining = target_periods - collected
        year = year_data["year"]
        factor = ipca_factors.get(year_data["inflation_year"], Decimal("1"))

        if year_data["quarters"] <= remaining:
            adjusted = year_data["net_income"] * factor
            adjusted_values.append(adjusted)
            yearly_breakdown.append({
                "year": year,
                "nominalNetIncome": float(year_data["net_income"]),
                "ipcaFactor": round(float(factor), 6),
                "adjustedNetIncome": float(adjusted),
                "quarters": year_data["quarters"],
                "quarterlyDetail": year_data["quarterly_detail"],
            })
            collected += year_data["quarters"]
        else:
            # Partial tail: most recent `remaining` periods of this year
            taken = year_data["quarterly_detail"][-remaining:]
            partial_nominal = sum(
                (Decimal(str(q["net_income"])) for q in taken),
                Decimal("0"),
            )
            partial_adjusted = partial_nominal * factor
            adjusted_values.append(partial_adjusted)
            yearly_breakdown.append({
                "year": year,
                "nominalNetIncome": float(partial_nominal),
                "ipcaFactor": round(float(factor), 6),
                "adjustedNetIncome": float(partial_adjusted),
                "quarters": len(taken),
                "quarterlyDetail": taken,
            })
            collected = target_periods

    years_of_data = effective_years
    label = f"PE{years_of_data}"

    annual_data_flag = periods_per_year == 1

    avg_adjusted = sum(adjusted_values) / Decimal(str(years_of_data))

    base_result = {
        "years_of_data": years_of_data,
        "label": label,
        "annual_data_flag": annual_data_flag,
        "periods_per_year": periods_per_year,
        "calculation_details": yearly_breakdown,
    }

    if avg_adjusted <= 0:
        return {
            **base_result,
            "pe10": None,
            "avg_adjusted_net_income": float(avg_adjusted),
            "error": "lucro médio negativo",
        }

    market_cap_reported = market_cap_in_reported_currency(market_cap, ticker)
    if market_cap_reported is None:
        return {
            **base_result,
            "pe10": None,
            "avg_adjusted_net_income": float(avg_adjusted),
            "error": "Câmbio indisponível para a moeda de relatório",
        }

    pe10 = market_cap_reported / avg_adjusted

    return {
        **base_result,
        "pe10": round(float(pe10), 2),
        "avg_adjusted_net_income": float(avg_adjusted),
        "error": None,
    }
