"""PE10 (Shiller P/E) calculation logic — pure functions."""
from collections import defaultdict
from decimal import Decimal

from .models import IPCAIndex, QuarterlyEarnings


def get_annual_eps(ticker: str, max_years: int = 10) -> list[dict]:
    """
    Get annual EPS by summing quarterly EPS for each calendar year.
    Returns list of {"year": int, "eps": Decimal, "quarters": int} sorted by year desc.
    """
    quarters = QuarterlyEarnings.objects.filter(
        ticker=ticker.upper(),
        eps__isnull=False,
    ).order_by("-end_date")[: max_years * 4]

    yearly = defaultdict(lambda: {"eps": Decimal("0"), "quarters": 0})
    for q in quarters:
        year = q.end_date.year
        yearly[year]["eps"] += q.eps
        yearly[year]["quarters"] += 1

    result = [
        {"year": year, "eps": data["eps"], "quarters": data["quarters"]}
        for year, data in sorted(yearly.items(), reverse=True)
    ]
    return result[:max_years]


def get_ipca_index_for_year(year: int) -> Decimal | None:
    """Get the IPCA accumulated index closest to end of the given year."""
    from datetime import date

    entry = (
        IPCAIndex.objects.filter(date__year__lte=year)
        .order_by("-date")
        .first()
    )
    return entry.accumulated_index if entry else None


def get_current_ipca() -> Decimal | None:
    """Get the most recent IPCA accumulated index."""
    entry = IPCAIndex.objects.order_by("-date").first()
    return entry.accumulated_index if entry else None


def calculate_pe10(ticker: str, current_price: Decimal) -> dict:
    """
    Calculate PE10 for a given ticker.

    Returns dict with:
        pe10: Decimal or None
        avg_adjusted_eps: Decimal or None
        years_of_data: int
        label: str (e.g., "PE10" or "PE7")
        error: str or None
    """
    annual_eps_data = get_annual_eps(ticker)

    if not annual_eps_data:
        return {
            "pe10": None,
            "avg_adjusted_eps": None,
            "years_of_data": 0,
            "label": "PE0",
            "error": "No earnings data available",
        }

    current_ipca = get_current_ipca()
    adjusted_eps_values = []

    for year_data in annual_eps_data:
        eps = year_data["eps"]
        year = year_data["year"]

        if current_ipca is not None:
            year_ipca = get_ipca_index_for_year(year)
            if year_ipca and year_ipca != 0:
                adjusted_eps = eps * (current_ipca / year_ipca)
            else:
                adjusted_eps = eps
        else:
            # No IPCA data available — use nominal values
            adjusted_eps = eps

        adjusted_eps_values.append(adjusted_eps)

    years_of_data = len(adjusted_eps_values)
    label = f"PE{years_of_data}"

    avg_adjusted_eps = sum(adjusted_eps_values) / len(adjusted_eps_values)

    if avg_adjusted_eps <= 0:
        return {
            "pe10": None,
            "avg_adjusted_eps": float(avg_adjusted_eps),
            "years_of_data": years_of_data,
            "label": label,
            "error": "N/A — negative average earnings over the period",
        }

    pe10 = current_price / avg_adjusted_eps

    return {
        "pe10": round(float(pe10), 2),
        "avg_adjusted_eps": round(float(avg_adjusted_eps), 2),
        "years_of_data": years_of_data,
        "label": label,
        "error": None,
    }
