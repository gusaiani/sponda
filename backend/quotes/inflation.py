"""Inflation adjustment factors for PE10/PFCF10 calculations.

Dispatches to one of three CPI sources depending on the ticker's
``Ticker.reported_currency``:

* ``BRL`` → IPCA (Brazilian inflation index, ``IPCAIndex``)
* ``USD`` → US CPI (``USCPIIndex``)
* anything else → per-country CPI from FRED (``CountryCPIIndex``),
  with a graceful "no adjustment" fallback when the FRED sync has not
  yet populated that currency's series.

Backwards compatibility: when a ``Ticker`` row does not exist (test
fixtures, brand-new symbols), the symbol-pattern heuristic
(``is_brazilian_ticker``) is used to pick between IPCA and USCPI, so
existing behavior is preserved.
"""
from decimal import Decimal

from .models import CountryCPIIndex, IPCAIndex, Ticker, USCPIIndex
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


def _get_country_cpi_year_rates(currency: str) -> dict[int, Decimal]:
    """Build year -> annual rate map from FRED country CPI data."""
    entries = list(CountryCPIIndex.objects.filter(currency=currency).order_by("date"))
    year_rates: dict[int, Decimal] = {}
    for entry in entries:
        year = entry.date.year
        month = entry.date.month
        if year not in year_rates or month >= 12:
            year_rates[year] = entry.annual_rate
    return year_rates


def _resolve_currency(ticker: str) -> str:
    """Look up ``Ticker.reported_currency``; fall back to the symbol-pattern
    heuristic when the row does not exist (test fixtures, brand-new symbols)."""
    row = Ticker.objects.filter(symbol=ticker.upper()).only("reported_currency").first()
    if row and row.reported_currency:
        return row.reported_currency
    return "BRL" if is_brazilian_ticker(ticker) else "USD"


def get_inflation_adjustment_factors(ticker: str, years: list[int]) -> dict[int, Decimal]:
    """Get inflation adjustment factors for the appropriate CPI series."""
    if not years:
        return {}

    currency = _resolve_currency(ticker)
    if currency == "BRL":
        year_rates = _get_ipca_year_rates()
    elif currency == "USD":
        year_rates = _get_cpi_year_rates()
    else:
        year_rates = _get_country_cpi_year_rates(currency)

    return _build_adjustment_factors(year_rates, years)
