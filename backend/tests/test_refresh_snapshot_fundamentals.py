"""Tests for refresh_snapshot_fundamentals — weekly full statement refresh."""
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
def seeded_universe(db, ipca_zero):
    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", type="stock", market_cap=400_000_000_000,
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
    Ticker.objects.create(symbol="SKIP3", name="Skip", type="stock", market_cap=None)


@pytest.mark.django_db
class TestRefreshSnapshotFundamentals:
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_balance_sheets")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_cash_flows")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.fetch_quote")
    def test_calls_all_three_sync_functions_per_ticker(
        self, mock_fetch_quote, mock_sync_e, mock_sync_cf, mock_sync_bs, seeded_universe
    ):
        mock_fetch_quote.return_value = {
            "marketCap": 500_000_000_000, "regularMarketPrice": 50.0,
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        mock_sync_e.assert_called_with("PETR4")
        mock_sync_cf.assert_called_with("PETR4")
        mock_sync_bs.assert_called_with("PETR4")

    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_balance_sheets")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_cash_flows")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.fetch_quote")
    def test_stores_full_indicator_snapshot(
        self, mock_fetch_quote, mock_sync_e, mock_sync_cf, mock_sync_bs, seeded_universe
    ):
        mock_fetch_quote.return_value = {
            "marketCap": 400_000_000_000, "regularMarketPrice": 40.0,
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        # avg earnings 10B, market cap 400B → PE10 = 40
        assert snapshot.pe10 == Decimal("40")
        # debt 300B / equity 200B = 1.5
        assert snapshot.debt_to_equity == Decimal("1.5")
        assert snapshot.market_cap == 400_000_000_000

    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_balance_sheets")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_cash_flows")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.fetch_quote")
    def test_skips_tickers_without_market_cap(
        self, mock_fetch_quote, mock_sync_e, mock_sync_cf, mock_sync_bs, seeded_universe
    ):
        mock_fetch_quote.return_value = {
            "marketCap": 400_000_000_000, "regularMarketPrice": 40.0,
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        fetched_symbols = [c.args[0] for c in mock_fetch_quote.call_args_list]
        assert "SKIP3" not in fetched_symbols

    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_balance_sheets")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_cash_flows")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.fetch_quote")
    def test_continues_after_sync_error(
        self, mock_fetch_quote, mock_sync_e, mock_sync_cf, mock_sync_bs, seeded_universe
    ):
        # Add a second ticker so we can prove the loop continues
        Ticker.objects.create(
            symbol="VALE3", name="Vale", type="stock", market_cap=300_000_000_000,
        )

        from quotes.providers import ProviderError
        def flaky(symbol):
            if symbol == "PETR4":
                raise ProviderError("BRAPI down")

        mock_sync_e.side_effect = flaky
        mock_fetch_quote.return_value = {
            "marketCap": 400_000_000_000, "regularMarketPrice": 40.0,
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        # VALE3 should still get a snapshot even though PETR4's sync errored
        assert IndicatorSnapshot.objects.filter(ticker="VALE3").exists()

    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_balance_sheets")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_cash_flows")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_fundamentals.fetch_quote")
    def test_updates_ticker_market_cap(
        self, mock_fetch_quote, mock_sync_e, mock_sync_cf, mock_sync_bs, seeded_universe
    ):
        mock_fetch_quote.return_value = {
            "marketCap": 700_000_000_000, "regularMarketPrice": 70.0,
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        assert Ticker.objects.get(symbol="PETR4").market_cap == 700_000_000_000
