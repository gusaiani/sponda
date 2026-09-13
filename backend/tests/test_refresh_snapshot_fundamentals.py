"""Tests for refresh_snapshot_fundamentals — the weekly statement refresh.

The command used to refetch three statements for every one of the 18,158
companies in the universe, 7.3 GB a run, and lost half of each run to the
provider's rate limit. It now refetches the companies that actually
reported, reads quotes in batches of a hundred, and recomputes every
snapshot from the database as before.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from quotes.models import (
    BalanceSheet,
    IndicatorSnapshot,
    IPCAIndex,
    QuarterlyEarnings,
    Ticker,
)

COMMAND_MODULE = "quotes.management.commands.refresh_snapshot_fundamentals"


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


def batch_quote(market_cap: int, price: float) -> dict:
    return {"marketCap": market_cap, "regularMarketPrice": price}


@pytest.mark.django_db
class TestRefreshSnapshotFundamentals:
    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_calls_all_three_sync_functions_per_ticker(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        seeded_universe,
    ):
        mock_reporters.return_value = set()
        mock_batch.return_value = {"PETR4": batch_quote(500_000_000_000, 50.0)}

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        mock_sync_e.assert_called_with("PETR4")
        mock_sync_cf.assert_called_with("PETR4")
        mock_sync_bs.assert_called_with("PETR4")

    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_stores_full_indicator_snapshot(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        seeded_universe,
    ):
        mock_reporters.return_value = set()
        mock_batch.return_value = {"PETR4": batch_quote(400_000_000_000, 40.0)}

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        # avg earnings 10B, market cap 400B → PE10 = 40
        assert snapshot.pe10 == Decimal("40")
        # debt 300B / equity 200B = 1.5
        assert snapshot.debt_to_equity == Decimal("1.5")
        assert snapshot.market_cap == 400_000_000_000

    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_skips_tickers_without_market_cap(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        seeded_universe,
    ):
        mock_reporters.return_value = set()
        mock_batch.return_value = {"PETR4": batch_quote(400_000_000_000, 40.0)}

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        requested_symbols = mock_batch.call_args.args[0]
        assert "SKIP3" not in requested_symbols

    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_continues_after_sync_error(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        seeded_universe,
    ):
        Ticker.objects.create(
            symbol="VALE3", name="Vale", type="stock", market_cap=300_000_000_000,
        )
        mock_reporters.return_value = set()

        from quotes.providers import ProviderError

        def flaky(symbol):
            if symbol == "PETR4":
                raise ProviderError("BRAPI down")

        mock_sync_e.side_effect = flaky
        mock_batch.return_value = {
            "PETR4": batch_quote(400_000_000_000, 40.0),
            "VALE3": batch_quote(300_000_000_000, 30.0),
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        # VALE3 should still get a snapshot even though PETR4's sync errored
        assert IndicatorSnapshot.objects.filter(ticker="VALE3").exists()

    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_updates_ticker_market_cap(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        seeded_universe,
    ):
        mock_reporters.return_value = set()
        mock_batch.return_value = {"PETR4": batch_quote(700_000_000_000, 70.0)}

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        assert Ticker.objects.get(symbol="PETR4").market_cap == 700_000_000_000


@pytest.fixture
def us_universe(db, ipca_zero):
    """Two US companies, both fully up to date on their filings."""
    for symbol in ("AAPL", "MSFT"):
        Ticker.objects.create(
            symbol=symbol, name=symbol, type="stock", market_cap=100_000_000_000,
        )
        for year in range(2016, 2026):
            for month_day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker=symbol, end_date=date(year, *month_day), net_income=1_000_000_000,
                )
        QuarterlyEarnings.objects.create(
            ticker=symbol,
            end_date=timezone.localdate() - timedelta(days=30),
            net_income=1_000_000_000,
        )


@pytest.mark.django_db
class TestStatementRefreshIsSelective:
    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_only_companies_that_reported_are_refetched(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        us_universe,
    ):
        mock_reporters.return_value = {"AAPL"}
        mock_batch.return_value = {
            "AAPL": batch_quote(100_000_000_000, 10.0),
            "MSFT": batch_quote(100_000_000_000, 10.0),
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        assert [call.args[0] for call in mock_sync_e.call_args_list] == ["AAPL"]

    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_every_company_still_gets_its_snapshot_recomputed(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        us_universe,
    ):
        mock_reporters.return_value = {"AAPL"}
        mock_batch.return_value = {
            "AAPL": batch_quote(100_000_000_000, 10.0),
            "MSFT": batch_quote(100_000_000_000, 10.0),
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        assert IndicatorSnapshot.objects.filter(ticker__in=["AAPL", "MSFT"]).count() == 2

    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_all_forces_a_full_resync(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        us_universe,
    ):
        mock_reporters.return_value = set()
        mock_batch.return_value = {
            "AAPL": batch_quote(100_000_000_000, 10.0),
            "MSFT": batch_quote(100_000_000_000, 10.0),
        }

        call_command(
            "refresh_snapshot_fundamentals", "--all", stdout=StringIO(), stderr=StringIO()
        )

        assert sorted(call.args[0] for call in mock_sync_e.call_args_list) == [
            "AAPL",
            "MSFT",
        ]

    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_an_unavailable_calendar_falls_back_to_a_full_resync(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        us_universe,
    ):
        """Without the calendar there is no way to tell who reported, and
        skipping everyone would quietly stop updating the data."""
        from quotes.fmp import FMPError

        mock_reporters.side_effect = FMPError("FMP returned 429")
        mock_batch.return_value = {
            "AAPL": batch_quote(100_000_000_000, 10.0),
            "MSFT": batch_quote(100_000_000_000, 10.0),
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        assert sorted(call.args[0] for call in mock_sync_e.call_args_list) == [
            "AAPL",
            "MSFT",
        ]

    @patch(f"{COMMAND_MODULE}.fetch_recent_reporters")
    @patch(f"{COMMAND_MODULE}.sync_balance_sheets")
    @patch(f"{COMMAND_MODULE}.sync_cash_flows")
    @patch(f"{COMMAND_MODULE}.sync_earnings")
    @patch(f"{COMMAND_MODULE}.fetch_quotes_batch")
    def test_quotes_are_read_in_one_batch_not_one_call_per_company(
        self, mock_batch, mock_sync_e, mock_sync_cf, mock_sync_bs, mock_reporters,
        us_universe,
    ):
        mock_reporters.return_value = set()
        mock_batch.return_value = {
            "AAPL": batch_quote(100_000_000_000, 10.0),
            "MSFT": batch_quote(100_000_000_000, 10.0),
        }

        call_command("refresh_snapshot_fundamentals", stdout=StringIO(), stderr=StringIO())

        mock_batch.assert_called_once()
        assert sorted(mock_batch.call_args.args[0]) == ["AAPL", "MSFT"]
