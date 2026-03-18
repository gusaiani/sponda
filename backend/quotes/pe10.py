"""PE10 (Shiller P/E) calculation logic — pure functions."""
from collections import defaultdict
from decimal import Decimal

from .models import IPCAIndex, QuarterlyEarnings


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


def get_ipca_adjustment_factors(years: list[int]) -> dict[int, Decimal]:
    """
    Build IPCA adjustment factors for each year.

    Uses the December reading for each year (12-month accumulated rate).
    Compounds rates from each year forward to bring historical earnings
    to current purchasing power.

    Returns {year: adjustment_factor} where factor >= 1 for past years.
    """
    if not years:
        return {}

    # Get all IPCA entries we need (December of each year + most recent)
    all_entries = list(IPCAIndex.objects.order_by("date"))
    if not all_entries:
        return {}

    # Build a map: year -> December annual rate (or closest available)
    year_rates: dict[int, Decimal] = {}
    for entry in all_entries:
        y = entry.date.year
        m = entry.date.month
        # Prefer December; overwrite earlier months of same year
        if y not in year_rates or m >= 12:
            year_rates[y] = entry.annual_rate

    # The most recent year's rate represents "current" inflation
    most_recent_year = max(year_rates.keys())

    # Compound adjustment: for year Y, multiply earnings by product of
    # (1 + rate/100) for each year from Y+1 to most_recent_year
    factors = {}
    for year in years:
        factor = Decimal("1")
        for y in range(year + 1, most_recent_year + 1):
            rate = year_rates.get(y, Decimal("0"))
            factor *= (1 + rate / 100)
        factors[year] = factor

    return factors


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
    ipca_factors = get_ipca_adjustment_factors(years)

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
            "error": "N/A — lucro médio negativo no período",
        }

    pe10 = market_cap / avg_adjusted

    return {
        **base_result,
        "pe10": round(float(pe10), 2),
        "avg_adjusted_net_income": float(avg_adjusted),
        "error": None,
    }
