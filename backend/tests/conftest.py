from datetime import date
from decimal import Decimal

import pytest

from quotes.models import BalanceSheet, IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Force browser locale to Portuguese so E2E tests match the default UI language."""
    return {**browser_context_args, "locale": "pt-BR"}


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


@pytest.fixture
def sample_cash_flows(db):
    """Create 10 years of quarterly cash flows for PETR4 (2016–2025)."""
    records = []
    # (operating_cf, investment_cf) per quarter — loosely based on Petrobras
    annual_cash_flows = {
        2025: [(45_000_000_000, -15_000_000_000), (38_000_000_000, -12_000_000_000),
               (42_000_000_000, -14_000_000_000), (30_000_000_000, -10_000_000_000)],
        2024: [(35_000_000_000, -13_000_000_000), (30_000_000_000, -11_000_000_000),
               (40_000_000_000, -15_000_000_000), (33_000_000_000, -12_000_000_000)],
        2023: [(50_000_000_000, -16_000_000_000), (40_000_000_000, -14_000_000_000),
               (38_000_000_000, -13_000_000_000), (42_000_000_000, -15_000_000_000)],
        2022: [(55_000_000_000, -18_000_000_000), (65_000_000_000, -20_000_000_000),
               (58_000_000_000, -17_000_000_000), (40_000_000_000, -14_000_000_000)],
        2021: [(10_000_000_000, -8_000_000_000), (50_000_000_000, -16_000_000_000),
               (40_000_000_000, -13_000_000_000), (25_000_000_000, -10_000_000_000)],
        2020: [(-30_000_000_000, -5_000_000_000), (5_000_000_000, -6_000_000_000),
               (15_000_000_000, -7_000_000_000), (8_000_000_000, -4_000_000_000)],
        2019: [(15_000_000_000, -9_000_000_000), (25_000_000_000, -10_000_000_000),
               (18_000_000_000, -8_000_000_000), (14_000_000_000, -7_000_000_000)],
        2018: [(12_000_000_000, -8_000_000_000), (18_000_000_000, -9_000_000_000),
               (14_000_000_000, -7_000_000_000), (8_000_000_000, -5_000_000_000)],
        2017: [(8_000_000_000, -6_000_000_000), (5_000_000_000, -4_000_000_000),
               (10_000_000_000, -5_000_000_000), (6_000_000_000, -3_000_000_000)],
        2016: [(-2_000_000_000, -4_000_000_000), (8_000_000_000, -5_000_000_000),
               (-4_000_000_000, -3_000_000_000), (3_000_000_000, -2_000_000_000)],
    }
    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    for year, flows in annual_cash_flows.items():
        for i, (ocf, icf) in enumerate(flows):
            month, day = quarter_ends[i]
            records.append(
                QuarterlyCashFlow(
                    ticker="PETR4",
                    end_date=date(year, month, day),
                    operating_cash_flow=ocf,
                    investment_cash_flow=icf,
                )
            )
    QuarterlyCashFlow.objects.bulk_create(records)
    return records


@pytest.fixture
def sample_balance_sheet(db):
    """Create a recent balance sheet for PETR4."""
    return BalanceSheet.objects.create(
        ticker="PETR4",
        end_date=date(2025, 9, 30),
        total_debt=300_000_000_000,
        total_liabilities=500_000_000_000,
        stockholders_equity=200_000_000_000,
    )


