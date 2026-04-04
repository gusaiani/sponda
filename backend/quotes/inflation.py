"""Inflation adjustment factors for PE10/PFCF10 calculations.

Routes to IPCA (Brazil) or US CPI depending on the ticker.
"""
from decimal import Decimal

from .models import IPCAIndex, USCPIIndex
from .providers import is_brazilian_ticker


def _build_adjustment_factors(year_rates: dict[int, Decimal], years: list[int]) -> dict[int, Decimal]:
    """Compound inflation rates forward to bring historical values to current purchasing power.

    For year Y, multiply by product of (1 + rate/100) for each year from Y+1 to most_recent_year.
    """
    if not year_rates:
        return {}

    most_recent_year = max(year_rates.keys())

    factors = {}
    for year in years:
        factor = Decimal("1")
        for compounding_year in range(year + 1, most_recent_year + 1):
            rate = year_rates.get(compounding_year, Decimal("0"))
            factor *= (1 + rate / 100)
        factors[year] = factor

    return factors


def _get_ipca_year_rates() -> dict[int, Decimal]:
    """Build year -> annual rate map from IPCA data."""
    all_entries = list(IPCAIndex.objects.order_by("date"))
    year_rates: dict[int, Decimal] = {}
    for entry in all_entries:
        year = entry.date.year
        month = entry.date.month
        if year not in year_rates or month >= 12:
            year_rates[year] = entry.annual_rate
    return year_rates


def _get_cpi_year_rates() -> dict[int, Decimal]:
    """Build year -> annual rate map from US CPI data."""
    all_entries = list(USCPIIndex.objects.order_by("date"))
    year_rates: dict[int, Decimal] = {}
    for entry in all_entries:
        year = entry.date.year
        month = entry.date.month
        if year not in year_rates or month >= 12:
            year_rates[year] = entry.annual_rate
    return year_rates


def get_inflation_adjustment_factors(ticker: str, years: list[int]) -> dict[int, Decimal]:
    """Get inflation adjustment factors for the appropriate index (IPCA or US CPI)."""
    if not years:
        return {}

    if is_brazilian_ticker(ticker):
        year_rates = _get_ipca_year_rates()
    else:
        year_rates = _get_cpi_year_rates()

    return _build_adjustment_factors(year_rates, years)
