"""Tests for refresh_snapshot_prices — 15-min quote-only snapshot refresh."""
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
    IndicatorSnapshot.objects.create(
        ticker="PETR4",
        market_cap=400_000_000_000,
        pe10=Decimal("40"),
        debt_to_equity=Decimal("1.5"),
        liabilities_to_equity=Decimal("2.5"),
        current_ratio=Decimal("1.2"),
    )
    # SKIP3 — no market cap → never included
    Ticker.objects.create(symbol="SKIP3", name="Skip", type="stock", market_cap=None)


PETR4_QUOTE = {"marketCap": 500_000_000_000, "regularMarketPrice": 50.0}


def _run(*args, **kwargs):
    call_command("refresh_snapshot_prices", *args, stdout=StringIO(), stderr=StringIO(), **kwargs)


@pytest.mark.django_db
class TestRefreshSnapshotPricesMarketHours:
    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=False,
    )
    def test_skips_when_no_exchange_open(self, _mock_hours, mock_batch, seeded_universe):
        out = StringIO()
        call_command("refresh_snapshot_prices", stdout=out, stderr=StringIO())
        mock_batch.assert_not_called()
        assert "No exchange open" in out.getvalue()

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=False,
    )
    def test_force_flag_bypasses_market_hours(self, _mock_hours, mock_batch, seeded_universe):
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        call_command(
            "refresh_snapshot_prices", force=True, stdout=StringIO(), stderr=StringIO(),
        )
        mock_batch.assert_called_once()

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_calls_batch_fetch_when_exchange_open(self, _mock_hours, mock_batch, seeded_universe):
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        _run()
        mock_batch.assert_called_once_with(["PETR4"])


@pytest.mark.django_db
class TestRefreshSnapshotPrices:
    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_updates_market_cap_and_current_price(
        self, _mock_hours, mock_batch, seeded_universe,
    ):
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        _run()
        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        assert snapshot.market_cap == 500_000_000_000
        assert snapshot.current_price == Decimal("50.0")

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_recomputes_pe10_from_fresh_market_cap(
        self, _mock_hours, mock_batch, seeded_universe,
    ):
        mock_batch.return_value = {"PETR4": {"marketCap": 800_000_000_000, "regularMarketPrice": 80.0}}
        _run()
        # avg earnings 10B, market cap 800B → PE10 = 80
        assert IndicatorSnapshot.objects.get(ticker="PETR4").pe10 == Decimal("80")

    @patch("quotes.management.commands.refresh_snapshot_prices.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_prices.sync_cash_flows")
    @patch("quotes.management.commands.refresh_snapshot_prices.sync_balance_sheets")
    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_does_not_call_any_sync_functions_for_brazilian_tickers(
        self, _mock_hours, mock_batch, mock_sync_bs, mock_sync_cf, mock_sync_e, seeded_universe,
    ):
        """BR tickers have BRL hardcoded by sync_tickers; the snapshot
        cron never needs to re-sync earnings just to learn the currency."""
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        _run()
        assert mock_sync_e.call_count == 0
        assert mock_sync_cf.call_count == 0
        assert mock_sync_bs.call_count == 0

    @patch("quotes.management.commands.refresh_snapshot_prices.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_backfills_reported_currency_for_foreign_tickers(
        self, _mock_hours, mock_batch, mock_sync_e, db, ipca_zero,
    ):
        """Snapshot cron must trigger sync_earnings for FMP tickers whose
        reported_currency is still empty (a holdover from pre-rollout
        cached data). Otherwise calculate_pe10 silently falls back to
        listing-currency assumption and the screener stores broken values."""
        Ticker.objects.create(
            symbol="NVO", name="Novo Nordisk", type="stock",
            market_cap=195_000_000_000, reported_currency="",
        )
        for year in range(2016, 2026):
            for month_day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="NVO", end_date=date(year, *month_day),
                    net_income=25_000_000_000,
                )
        mock_batch.return_value = {"NVO": {"marketCap": 195_000_000_000, "regularMarketPrice": 43.88}}
        _run()
        mock_sync_e.assert_called_once_with("NVO")

    @patch("quotes.management.commands.refresh_snapshot_prices.sync_earnings")
    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_does_not_backfill_when_reported_currency_already_set(
        self, _mock_hours, mock_batch, mock_sync_e, db, ipca_zero,
    ):
        Ticker.objects.create(
            symbol="NVO", name="Novo Nordisk", type="stock",
            market_cap=195_000_000_000, reported_currency="DKK",
        )
        for year in range(2016, 2026):
            for month_day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="NVO", end_date=date(year, *month_day),
                    net_income=25_000_000_000,
                )
        mock_batch.return_value = {"NVO": {"marketCap": 195_000_000_000, "regularMarketPrice": 43.88}}
        _run()
        mock_sync_e.assert_not_called()

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_leaves_leverage_fields_untouched(
        self, _mock_hours, mock_batch, seeded_universe,
    ):
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        _run()
        snapshot = IndicatorSnapshot.objects.get(ticker="PETR4")
        assert snapshot.debt_to_equity == Decimal("1.5")
        assert snapshot.liabilities_to_equity == Decimal("2.5")
        assert snapshot.current_ratio == Decimal("1.2")

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_updates_ticker_market_cap(self, _mock_hours, mock_batch, seeded_universe):
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        _run()
        assert Ticker.objects.get(symbol="PETR4").market_cap == 500_000_000_000

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_skips_tickers_without_market_cap(self, _mock_hours, mock_batch, seeded_universe):
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        _run()
        # SKIP3 has no market cap — must not appear in batch call
        symbols_passed = mock_batch.call_args[0][0]
        assert "SKIP3" not in symbols_passed

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_counts_missing_ticker_as_failure(self, _mock_hours, mock_batch, seeded_universe):
        Ticker.objects.create(symbol="VALE3", name="Vale", type="stock", market_cap=300_000_000_000)
        IndicatorSnapshot.objects.create(ticker="VALE3", market_cap=300_000_000_000)
        # VALE3 absent from batch response — counted as failure
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        out = StringIO()
        call_command("refresh_snapshot_prices", stdout=out, stderr=StringIO())
        assert IndicatorSnapshot.objects.get(ticker="PETR4").market_cap == 500_000_000_000
        assert IndicatorSnapshot.objects.get(ticker="VALE3").market_cap == 300_000_000_000

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_aborts_on_batch_provider_error(self, _mock_hours, mock_batch, seeded_universe):
        from quotes.providers import ProviderError
        mock_batch.side_effect = ProviderError("upstream down")
        err = StringIO()
        call_command("refresh_snapshot_prices", stdout=StringIO(), stderr=err)
        assert "upstream down" in err.getvalue()
        # Snapshot unchanged
        assert IndicatorSnapshot.objects.get(ticker="PETR4").market_cap == 400_000_000_000

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_invalidates_pe10_view_cache_after_update(
        self, _mock_hours, mock_batch, seeded_universe,
    ):
        from django.core.cache import cache
        cache.set("pe10:PETR4", {"stale": True}, 3600)
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        _run()
        assert cache.get("pe10:PETR4") is None

    @patch("quotes.management.commands.refresh_snapshot_prices.fetch_quotes_batch")
    @patch(
        "quotes.management.commands.refresh_snapshot_prices.any_exchange_open",
        return_value=True,
    )
    def test_warms_provider_quote_cache_after_update(
        self, _mock_hours, mock_batch, seeded_universe,
    ):
        from django.core.cache import cache
        mock_batch.return_value = {"PETR4": PETR4_QUOTE}
        _run()
        assert cache.get("provider:quote:PETR4") == PETR4_QUOTE
