"""Tests for refresh_snapshot_prices — daily quote-only snapshot refresh."""
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
    # PETR4 — full earnings history so PE10 can be recomputed
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

    # Pre-existing snapshot with leverage fields populated — price refresh
    # must leave leverage untouched (it only touches price-dependent fields).
    IndicatorSnapshot.objects.create(
        ticker="PETR4",
        market_cap=400_000_000_000,
        pe10=Decimal("40"),
        debt_to_equity=Decimal("1.5"),
        liabilities_to_equity=Decimal("2.5"),
        current_ratio=Decimal("1.2"),
    )

    # SKIP3 — no market cap → skipped
    Ticker.objects.create(symbol="SKIP3", name="Skip", type="stock", market_cap=None)


@pytest.mark.django_db
class TestRefreshSnapshotPrices:
    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quote")
    def test_updates_market_cap_and_current_price(self, mock_fetch_quote, seeded_universe):
        mock_fetch_quote.return_value = {
            "marketCap": 500_000_000_000,
            "regularMarketPrice": 50.0,
        }

        call_command("refresh_snapshot_prices", stdout=StringIO(), stderr=StringIO())

        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        assert snapshot.market_cap == 500_000_000_000
        assert snapshot.current_price == Decimal("50.0")

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quote")
    def test_recomputes_pe10_from_fresh_market_cap(self, mock_fetch_quote, seeded_universe):
        # Double the market cap → PE10 should roughly double (avg earnings unchanged)
        mock_fetch_quote.return_value = {
            "marketCap": 800_000_000_000,
            "regularMarketPrice": 80.0,
        }

        call_command("refresh_snapshot_prices", stdout=StringIO(), stderr=StringIO())

        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        # avg earnings 10B, market cap 800B → PE10 = 80
        assert snapshot.pe10 == Decimal("80")

    @patch("quotes.management.commands.refresh_snapshot_prices.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_prices.sync_cash_flows")
    @patch("quotes.management.commands.refresh_snapshot_prices.sync_balance_sheets")
    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quote")
    def test_does_not_call_any_sync_functions(
        self, mock_fetch_quote, mock_sync_bs, mock_sync_cf, mock_sync_e, seeded_universe
    ):
        mock_fetch_quote.return_value = {
            "marketCap": 500_000_000_000,
            "regularMarketPrice": 50.0,
        }

        call_command("refresh_snapshot_prices", stdout=StringIO(), stderr=StringIO())

        assert mock_sync_e.call_count == 0
        assert mock_sync_cf.call_count == 0
        assert mock_sync_bs.call_count == 0

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quote")
    def test_leaves_leverage_fields_untouched(self, mock_fetch_quote, seeded_universe):
        """Price refresh must NOT overwrite leverage fields — leverage depends on
        fundamentals, not price, and is refreshed by the weekly job only."""
        mock_fetch_quote.return_value = {
            "marketCap": 500_000_000_000,
            "regularMarketPrice": 50.0,
        }

        call_command("refresh_snapshot_prices", stdout=StringIO(), stderr=StringIO())

        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        # Leverage fields preserved from seed, not overwritten with None
        assert snapshot.debt_to_equity == Decimal("1.5")
        assert snapshot.liabilities_to_equity == Decimal("2.5")
        assert snapshot.current_ratio == Decimal("1.2")

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quote")
    def test_updates_ticker_market_cap(self, mock_fetch_quote, seeded_universe):
        mock_fetch_quote.return_value = {
            "marketCap": 500_000_000_000,
            "regularMarketPrice": 50.0,
        }

        call_command("refresh_snapshot_prices", stdout=StringIO(), stderr=StringIO())

        ticker_row = Ticker.objects.get(symbol="PETR4")
        assert ticker_row.market_cap == 500_000_000_000

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quote")
    def test_skips_tickers_without_market_cap(self, mock_fetch_quote, seeded_universe):
        mock_fetch_quote.return_value = {
            "marketCap": 500_000_000_000,
            "regularMarketPrice": 50.0,
        }

        call_command("refresh_snapshot_prices", stdout=StringIO(), stderr=StringIO())

        # SKIP3 has no market cap → was not fetched
        fetched_symbols = [c.args[0] for c in mock_fetch_quote.call_args_list]
        assert "SKIP3" not in fetched_symbols

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quote")
    def test_continues_after_provider_error(self, mock_fetch_quote, seeded_universe):
        Ticker.objects.create(symbol="VALE3", name="Vale", type="stock", market_cap=300_000_000_000)
        IndicatorSnapshot.objects.create(ticker="VALE3", market_cap=300_000_000_000)

        from quotes.providers import ProviderError
        def flaky(symbol):
            if symbol == "VALE3":
                raise ProviderError("upstream down")
            return {"marketCap": 500_000_000_000, "regularMarketPrice": 50.0}

        mock_fetch_quote.side_effect = flaky

        call_command("refresh_snapshot_prices", stdout=StringIO(), stderr=StringIO())

        # PETR4 still updated; VALE3 unchanged
        assert IndicatorSnapshot.objects.get(ticker="PETR4").market_cap == 500_000_000_000
        assert IndicatorSnapshot.objects.get(ticker="VALE3").market_cap == 300_000_000_000
