"""PE10 (Shiller P/E) calculation logic — pure functions."""
from collections import defaultdict
from decimal import Decimal

from .models import IPCAIndex, QuarterlyEarnings


def get_annual_eps(
    ticker: str, shares_outstanding: Decimal | None = None, max_years: int = 10
) -> list[dict]:
    """
    Get annual EPS by summing quarterly EPS for each calendar year.
    Falls back to netIncome / shares_outstanding when EPS is null.
    Returns list of {"year": int, "eps": Decimal, "quarters": int,
                     "quarterly_detail": list} sorted by year desc.
    """
    quarters = QuarterlyEarnings.objects.filter(
        ticker=ticker.upper(),
    ).order_by("-end_date")[: max_years * 4]

    yearly = defaultdict(lambda: {"eps": Decimal("0"), "quarters": 0, "quarterly_detail": []})
    for q in quarters:
        # Always derive EPS from netIncome / shares_outstanding.
        # BRAPI's basicEarningsPerCommonShare is unreliable (wrong scale).
        if q.net_income is not None and shares_outstanding:
            eps = Decimal(str(q.net_income)) / shares_outstanding
        else:
            continue
        year = q.end_date.year
        yearly[year]["eps"] += eps
        yearly[year]["quarters"] += 1
        yearly[year]["quarterly_detail"].append({
            "end_date": q.end_date.isoformat(),
            "net_income": q.net_income,
            "eps": round(float(eps), 6),
        })

    result = [
        {
            "year": year,
            "eps": data["eps"],
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

    # Compound adjustment: for year Y, multiply EPS by product of
    # (1 + rate/100) for each year from Y+1 to most_recent_year
    factors = {}
    for year in years:
        factor = Decimal("1")
        for y in range(year + 1, most_recent_year + 1):
            rate = year_rates.get(y, Decimal("0"))
            factor *= (1 + rate / 100)
        factors[year] = factor

    return factors


def calculate_pe10(
    ticker: str, current_price: Decimal, shares_outstanding: Decimal | None = None
) -> dict:
    """
    Calculate PE10 for a given ticker.

    Returns dict with:
        pe10: Decimal or None
        avg_adjusted_eps: Decimal or None
        years_of_data: int
        label: str (e.g., "PE10" or "PE7")
        error: str or None
    """
    annual_eps_data = get_annual_eps(ticker, shares_outstanding=shares_outstanding)

    if not annual_eps_data:
        return {
            "pe10": None,
            "avg_adjusted_eps": None,
            "years_of_data": 0,
            "label": "PE0",
            "error": "No earnings data available",
            "annual_data": False,
            "calculation_details": [],
        }

    years = [d["year"] for d in annual_eps_data]
    ipca_factors = get_ipca_adjustment_factors(years)

    adjusted_eps_values = []
    yearly_breakdown = []
    for year_data in annual_eps_data:
        eps = year_data["eps"]
        year = year_data["year"]
        factor = ipca_factors.get(year, Decimal("1"))
        adjusted_eps = eps * factor
        adjusted_eps_values.append(adjusted_eps)
        yearly_breakdown.append({
            "year": year,
            "nominalEPS": round(float(eps), 6),
            "ipcaFactor": round(float(factor), 6),
            "adjustedEPS": round(float(adjusted_eps), 6),
            "quarters": year_data["quarters"],
            "quarterlyDetail": year_data["quarterly_detail"],
        })

    years_of_data = len(adjusted_eps_values)
    label = f"PE{years_of_data}"

    # Detect if using annual (1 record/year) vs quarterly (4 records/year)
    avg_quarters = sum(d["quarters"] for d in annual_eps_data) / len(annual_eps_data)
    annual_data = avg_quarters < 2

    avg_adjusted_eps = sum(adjusted_eps_values) / len(adjusted_eps_values)

    base_result = {
        "years_of_data": years_of_data,
        "label": label,
        "annual_data": annual_data,
        "calculation_details": yearly_breakdown,
    }

    if avg_adjusted_eps <= 0:
        return {
            **base_result,
            "pe10": None,
            "avg_adjusted_eps": float(avg_adjusted_eps),
            "error": "N/A — negative average earnings over the period",
        }

    pe10 = current_price / avg_adjusted_eps

    return {
        **base_result,
        "pe10": round(float(pe10), 2),
        "avg_adjusted_eps": round(float(avg_adjusted_eps), 2),
        "error": None,
    }
