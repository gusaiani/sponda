"""Tests for the refresh_indicator_snapshots management command."""
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.models import (
    BalanceSheet,
    IndicatorSnapshot,
    IPCAIndex,
    QuarterlyEarnings,
    Ticker,
)


@pytest.fixture
def ipca_zero(db):
    for year in range(2010, 2027):
        IPCAIndex.objects.update_or_create(
            date=date(year, 12, 31), defaults={"annual_rate": Decimal("0")},
        )


@pytest.fixture
def tickers(db, ipca_zero):
    # PETR4: has market cap + earnings + balance sheet → full indicators
    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", sector="Oil", market_cap=400_000_000_000,
    )
    for year in range(2016, 2026):
        for month_day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="PETR4",
                end_date=date(year, *month_day),
                net_income=2_500_000_000,
            )
    BalanceSheet.objects.create(
        ticker="PETR4",
        end_date=date(2025, 9, 30),
        total_debt=300_000_000_000,
        total_liabilities=500_000_000_000,
        stockholders_equity=200_000_000_000,
    )

    # VALE3: has market cap but no financial history → leverage-only
    Ticker.objects.create(
        symbol="VALE3", name="Vale", sector="Mining", market_cap=300_000_000_000,
    )

    # SKIP3: no market cap → skipped entirely
    Ticker.objects.create(
        symbol="SKIP3", name="No Data", sector="Unknown", market_cap=None,
    )


@pytest.mark.django_db
class TestRefreshIndicatorSnapshots:
    def test_creates_snapshot_for_each_ticker_with_market_cap(self, tickers):
        call_command("refresh_indicator_snapshots", stdout=StringIO())
        symbols = set(IndicatorSnapshot.objects.values_list("ticker", flat=True))
        assert "PETR4" in symbols
        assert "VALE3" in symbols
        assert "SKIP3" not in symbols  # no market cap → skipped

    def test_stores_computed_indicators(self, tickers):
        call_command("refresh_indicator_snapshots", stdout=StringIO())
        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        # avg earnings = 10B, market cap = 400B → PE10 = 40
        assert snapshot.pe10 == Decimal("40")
        assert snapshot.debt_to_equity == Decimal("1.5")  # 300B / 200B
        assert snapshot.market_cap == 400_000_000_000

    def test_upserts_existing_snapshot(self, tickers):
        # Pre-seed a stale snapshot; refresh should overwrite it.
        IndicatorSnapshot.objects.create(
            ticker="PETR4", pe10=Decimal("999.99"), market_cap=1,
        )
        call_command("refresh_indicator_snapshots", stdout=StringIO())
        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        assert snapshot.pe10 == Decimal("40")
        # Only one row per ticker
        assert IndicatorSnapshot.objects.filter(ticker="PETR4").count() == 1

    def test_ticker_flag_limits_run_to_one_symbol(self, tickers):
        call_command(
            "refresh_indicator_snapshots", "--ticker", "PETR4", stdout=StringIO(),
        )
        assert IndicatorSnapshot.objects.count() == 1
        assert IndicatorSnapshot.objects.first().ticker == "PETR4"

    def test_continues_on_individual_ticker_errors(self, tickers):
        # Make compute_company_indicators explode on VALE3 only.
        def flaky(ticker, **kwargs):
            if ticker == "VALE3":
                raise RuntimeError("simulated failure")
            from quotes.indicators import compute_company_indicators as real
            return real(ticker, **kwargs)

        with patch(
            "quotes.management.commands.refresh_indicator_snapshots.compute_company_indicators",
            side_effect=flaky,
        ):
            call_command("refresh_indicator_snapshots", stdout=StringIO())

        # PETR4 was still processed despite VALE3 failing.
        assert IndicatorSnapshot.objects.filter(ticker="PETR4").exists()
        assert not IndicatorSnapshot.objects.filter(ticker="VALE3").exists()

    def test_reports_counts_in_stdout(self, tickers):
        out = StringIO()
        call_command("refresh_indicator_snapshots", stdout=out)
        output = out.getvalue()
        assert "PETR4" in output or "2" in output  # emitted some summary
