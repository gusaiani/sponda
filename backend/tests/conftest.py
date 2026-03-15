from datetime import date
from decimal import Decimal

import pytest

from quotes.models import IPCAIndex, QuarterlyEarnings


@pytest.fixture
def sample_earnings(db):
    """Create 10 years of quarterly earnings for PETR4 (2016–2025)."""
    records = []
    # Annual net incomes (in billions) — loosely based on real Petrobras data
    annual_net_incomes = {
        2025: [35_000_000_000, 27_000_000_000, 33_000_000_000, 16_000_000_000],
        2024: [25_000_000_000, 20_000_000_000, 28_000_000_000, 24_000_000_000],
        2023: [39_000_000_000, 29_000_000_000, 27_000_000_000, 31_000_000_000],
        2022: [45_000_000_000, 54_000_000_000, 46_000_000_000, 30_000_000_000],
        2021: [1_000_000_000, 42_000_000_000, 31_000_000_000, 16_000_000_000],
        2020: [-48_000_000_000, -3_000_000_000, 4_000_000_000, 60_000_000],
        2019: [7_000_000_000, 18_000_000_000, 9_000_000_000, 8_000_000_000],
        2018: [7_000_000_000, 10_000_000_000, 6_000_000_000, 2_000_000_000],
        2017: [3_000_000_000, -500_000_000, 2_000_000_000, 1_000_000_000],
        2016: [-5_000_000_000, 2_000_000_000, -8_000_000_000, -3_000_000_000],
    }
    quarter_ends = [
        (3, 31),   # Q1
        (6, 30),   # Q2
        (9, 30),   # Q3
        (12, 31),  # Q4
    ]
    for year, incomes in annual_net_incomes.items():
        for i, net_income in enumerate(incomes):
            month, day = quarter_ends[i]
            records.append(
                QuarterlyEarnings(
                    ticker="PETR4",
                    end_date=date(year, month, day),
                    net_income=net_income,
                    eps=None,
                )
            )
    QuarterlyEarnings.objects.bulk_create(records)
    return records


@pytest.fixture
def sample_ipca(db):
    """Create IPCA annual rate entries (December reading for each year)."""
    rates = {
        2016: Decimal("6.29"),
        2017: Decimal("2.95"),
        2018: Decimal("3.75"),
        2019: Decimal("4.31"),
        2020: Decimal("4.52"),
        2021: Decimal("10.06"),
        2022: Decimal("5.79"),
        2023: Decimal("4.62"),
        2024: Decimal("4.83"),
        2025: Decimal("4.26"),
    }
    entries = []
    for year, rate in rates.items():
        entries.append(IPCAIndex(date=date(year, 12, 1), annual_rate=rate))
    IPCAIndex.objects.bulk_create(entries)
    return entries


