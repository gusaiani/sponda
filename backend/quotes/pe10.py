"""PE10 (Shiller P/E) calculation logic — pure functions."""
from collections import defaultdict
from decimal import Decimal

from .inflation import get_inflation_adjustment_factors
from .models import QuarterlyEarnings


def get_annual_earnings(ticker: str, max_years: int = 10) -> list[dict]:
    """
    Get annual net income by summing quarterly net income for each calendar year.
    Returns list of {"year": int, "net_income": Decimal, "quarters": int,
                     "quarterly_detail": list} sorted by year desc.
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

    result = [
        {
            "year": year,
            "net_income": data["net_income"],
            "quarters": data["quarters"],
            "quarterly_detail": sorted(data["quarterly_detail"], key=lambda x: x["end_date"]),
        }
        for year, data in sorted(yearly.items(), reverse=True)
    ]
    return result[:max_years]


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

    years = [d["year"] for d in annual_data]
    ipca_factors = get_inflation_adjustment_factors(ticker, years)

    adjusted_values = []
    yearly_breakdown = []
    for year_data in annual_data:
        net_income = year_data["net_income"]
        year = year_data["year"]
        factor = ipca_factors.get(year, Decimal("1"))
        adjusted = net_income * factor
        adjusted_values.append(adjusted)
        yearly_breakdown.append({
            "year": year,
            "nominalNetIncome": float(net_income),
            "ipcaFactor": round(float(factor), 6),
            "adjustedNetIncome": float(adjusted),
            "quarters": year_data["quarters"],
            "quarterlyDetail": year_data["quarterly_detail"],
        })

    years_of_data = len(adjusted_values)
    label = f"PE{years_of_data}"

    # Detect if using annual (1 record/year) vs quarterly (4 records/year)
    avg_quarters = sum(d["quarters"] for d in annual_data) / len(annual_data)
    annual_data_flag = avg_quarters < 2

    avg_adjusted = sum(adjusted_values) / len(adjusted_values)

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

    pe10 = market_cap / avg_adjusted

    return {
        **base_result,
        "pe10": round(float(pe10), 2),
        "avg_adjusted_net_income": float(avg_adjusted),
        "error": None,
    }
