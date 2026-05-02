"""Tests for inflation adjustment routing (IPCA for BR, CPI for US, FRED per-country for everything else)."""
from datetime import date
from decimal import Decimal

import pytest

from quotes.models import CountryCPIIndex, IPCAIndex, Ticker, USCPIIndex
from quotes.inflation import get_inflation_adjustment_factors


@pytest.fixture
def sample_ipca(db):
    """Create IPCA entries for 2020-2025."""
    entries = []
    for year in range(2020, 2026):
        entries.append(IPCAIndex(date=date(year, 12, 1), annual_rate=Decimal("5.0")))
    IPCAIndex.objects.bulk_create(entries)


@pytest.fixture
def sample_us_cpi(db):
    """Create US CPI entries for 2020-2025."""
    entries = []
    for year in range(2020, 2026):
        entries.append(USCPIIndex(date=date(year, 1, 1), annual_rate=Decimal("3.0")))
    USCPIIndex.objects.bulk_create(entries)


class TestGetInflationAdjustmentFactors:
    def test_brazilian_ticker_uses_ipca(self, sample_ipca):
        factors = get_inflation_adjustment_factors("PETR4", [2023, 2024, 2025])
        # IPCA rate is 5% per year. Most recent year is 2025.
        # 2025: factor = 1 (current year)
        # 2024: factor = 1.05 (one year of 5%)
        # 2023: factor = 1.05 * 1.05 = 1.1025
        assert factors[2025] == Decimal("1")
        assert abs(float(factors[2024]) - 1.05) < 0.001
        assert abs(float(factors[2023]) - 1.1025) < 0.001

    def test_us_ticker_uses_cpi(self, sample_us_cpi):
        factors = get_inflation_adjustment_factors("AAPL", [2023, 2024, 2025])
        # CPI rate is 3% per year. Most recent year is 2025.
        # 2025: factor = 1 (current year)
        # 2024: factor = 1.03
        # 2023: factor = 1.03 * 1.03 = 1.0609
        assert factors[2025] == Decimal("1")
        assert abs(float(factors[2024]) - 1.03) < 0.001
        assert abs(float(factors[2023]) - 1.0609) < 0.001

    def test_empty_years_returns_empty(self, db):
        factors = get_inflation_adjustment_factors("AAPL", [])
        assert factors == {}

    def test_no_inflation_data_returns_empty(self, db):
        factors = get_inflation_adjustment_factors("AAPL", [2023, 2024])
        assert factors == {}

    def test_missing_year_defaults_to_zero_rate(self, sample_us_cpi):
        """If a specific year has no CPI entry, assume 0% inflation for that year."""
        factors = get_inflation_adjustment_factors("AAPL", [2018])
        # 2018 has no CPI data. Years 2019 also missing. 2020-2025 have 3%.
        # Factor compounds from 2019 to 2025 (7 years), but only 2020-2025 have data.
        # Years without data use rate=0, so factor = 1.03^6
        assert 2018 in factors
        assert float(factors[2018]) > 1.0


@pytest.fixture
def sample_dkk_cpi(db):
    """Create Denmark CPI entries (DKK currency code) for 2020-2025."""
    entries = []
    for year in range(2020, 2026):
        entries.append(CountryCPIIndex(
            currency="DKK", date=date(year, 12, 1), annual_rate=Decimal("2.5"),
        ))
    CountryCPIIndex.objects.bulk_create(entries)


class TestPerCountryCpiDispatch:
    def test_foreign_reporter_uses_fred_country_cpi(self, db, sample_dkk_cpi):
        """When the ticker reports in DKK, inflation factors should come
        from the Denmark CPI series, not the US CPI series."""
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk A/S", reported_currency="DKK")
        factors = get_inflation_adjustment_factors("NVO", [2023, 2024, 2025])
        # DKK CPI rate is 2.5% per year. Most recent year is 2025.
        assert factors[2025] == Decimal("1")
        assert abs(float(factors[2024]) - 1.025) < 0.001
        assert abs(float(factors[2023]) - 1.025 * 1.025) < 0.001

    def test_falls_back_to_no_adjustment_when_country_cpi_missing(self, db):
        """If a foreign reporter has no CPI series populated yet (FRED sync
        hasn't run for that currency), the helper returns {} so the calculator
        defaults to factor=1 for every year — same behavior as the legacy path
        when IPCA/USCPI is empty."""
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk A/S", reported_currency="DKK")
        factors = get_inflation_adjustment_factors("NVO", [2023, 2024, 2025])
        assert factors == {}

    def test_us_reporter_with_explicit_currency_uses_uscpi(self, db, sample_us_cpi):
        """A non-Brazilian ticker with reported_currency='USD' explicitly set
        should still use US CPI (the USD-statement path)."""
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", reported_currency="USD")
        factors = get_inflation_adjustment_factors("AAPL", [2023, 2024, 2025])
        assert abs(float(factors[2024]) - 1.03) < 0.001

    def test_brazilian_reporter_with_explicit_currency_uses_ipca(self, db, sample_ipca):
        """BR tickers default reported_currency='BRL' via brapi.sync_tickers;
        the explicit field should still route to IPCA."""
        Ticker.objects.create(symbol="PETR4", name="Petrobras", reported_currency="BRL")
        factors = get_inflation_adjustment_factors("PETR4", [2023, 2024, 2025])
        assert abs(float(factors[2024]) - 1.05) < 0.001

    def test_legacy_path_when_ticker_row_missing(self, db, sample_us_cpi):
        """For tests/fixtures where the Ticker row doesn't exist, we fall
        back to the symbol-pattern heuristic to remain backwards-compatible."""
        factors = get_inflation_adjustment_factors("AAPL", [2024])
        assert abs(float(factors[2024]) - 1.0) < 0.05  # AAPL → USCPI path
