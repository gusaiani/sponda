"""PE10 (Shiller P/E) calculation logic — pure functions.

The N-year window covers exactly N×4 trailing quarters. When the most
recent fiscal year only has a partial set of quarters reported (e.g.
mid-year, with only Q1 in), we backfill from older years so the
denominator divides an honest N years of earnings — instead of
treating the partial-current year as if it were a full year and
under-weighting the average.
"""
from collections import defaultdict
from decimal import Decimal

from .fx import market_cap_in_reported_currency
from .inflation import get_inflation_adjustment_factors
from .models import QuarterlyEarnings


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

    yearly = defaultdict(lambda: {"net_income": Decimal("0"), "quarters": 0, "quarterly_detail": []})
    for q in quarters:
        if q.net_income is None:
            continue
        year = q.end_date.year
        yearly[year]["net_income"] += q.net_income
        yearly[year]["quarters"] += 1
        yearly[year]["quarterly_detail"].append({
            "end_date": q.end_date.isoformat(),
            "net_income": q.net_income,
        })

    return [
        {
            "year": year,
            "net_income": data["net_income"],
            "quarters": data["quarters"],
            "quarterly_detail": sorted(data["quarterly_detail"], key=lambda x: x["end_date"]),
        }
        for year, data in sorted(yearly.items(), reverse=True)
    ]


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
            "calculation_details": [],
        }

    # Cap the window to the largest whole-year count this ticker can
    # actually fill. A 13-quarter company with max_years=10 yields a
    # PE3 (12 trailing quarters / 3 years), not PE10 averaged over a
    # short partial sample.
    total_quarters = sum(d["quarters"] for d in annual_data)
    effective_years = min(max_years, total_quarters // 4)
    if effective_years == 0:
        return {
            "pe10": None,
            "avg_adjusted_net_income": None,
            "years_of_data": 0,
            "label": "PE0",
            "error": "Sem dados de lucro disponíveis",
            "annual_data_flag": False,
            "calculation_details": [],
        }
    target_quarters = effective_years * 4

    years = [d["year"] for d in annual_data]
    ipca_factors = get_inflation_adjustment_factors(ticker, years)

    adjusted_values: list[Decimal] = []
    yearly_breakdown = []
    collected = 0

    for year_data in annual_data:
        if collected >= target_quarters:
            break
        remaining = target_quarters - collected
        year = year_data["year"]
        factor = ipca_factors.get(year, Decimal("1"))

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
            # Partial tail: most recent `remaining` quarters of this year
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
            collected = target_quarters

    years_of_data = effective_years
    label = f"PE{years_of_data}"

    # Detect annual (1 record/year) vs quarterly (4 records/year) reporters
    # using the slice that actually fed the average, not the full annual_data.
    avg_quarters = sum(b["quarters"] for b in yearly_breakdown) / len(yearly_breakdown)
    annual_data_flag = avg_quarters < 2

    avg_adjusted = sum(adjusted_values) / Decimal(str(years_of_data))

    base_result = {
        "years_of_data": years_of_data,
        "label": label,
        "annual_data_flag": annual_data_flag,
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
