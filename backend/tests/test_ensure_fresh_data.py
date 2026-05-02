"""Tests for _ensure_fresh_data and the reported_currency backfill nudge.

The cross-currency rollout introduced `Ticker.reported_currency`, which
gets stamped as a side-effect of `fmp.sync_earnings`. The standard
freshness gate skips `sync_earnings` whenever quarterly data is younger
than 24h, so foreign ADRs whose earnings were cached *before* the
rollout never get their currency stamped via the natural flow until the
weekly fundamentals cron runs. The backfill nudge re-runs `sync_earnings`
exactly once per such ticker to close that gap on first page visit.
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from quotes.models import QuarterlyEarnings, Ticker
from quotes.views import _ensure_fresh_data


@pytest.fixture
def fresh_earnings_for(db):
    """Helper: pre-create a fresh-cached QuarterlyEarnings row for `ticker`
    so the standard freshness gate would normally skip sync_earnings."""
    def _make(ticker: str):
        record = QuarterlyEarnings.objects.create(
            ticker=ticker, end_date=date(2025, 12, 31),
            net_income=10_000_000_000,
        )
        # bulk_create-style fresh write happens at fetched_at=now via auto_now
        return record
    return _make


class TestReportedCurrencyBackfillNudge:
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_forces_sync_when_reported_currency_empty(
        self, mock_sync_earnings, mock_sync_cf, mock_sync_bs, fresh_earnings_for, db,
    ):
        """Foreign ADR with cached fresh earnings but empty reported_currency:
        force sync_earnings so the writeback can stamp the field."""
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk", reported_currency="")
        fresh_earnings_for("NVO")

        _ensure_fresh_data("NVO")

        mock_sync_earnings.assert_called_once_with("NVO")

    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_does_not_force_when_reported_currency_already_set(
        self, mock_sync_earnings, mock_sync_cf, mock_sync_bs, fresh_earnings_for, db,
    ):
        """Once reported_currency is stamped, the freshness gate behaves as
        before — no extra sync calls per page view."""
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk", reported_currency="DKK")
        fresh_earnings_for("NVO")

        _ensure_fresh_data("NVO")

        mock_sync_earnings.assert_not_called()

    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_does_not_force_when_no_ticker_row(
        self, mock_sync_earnings, mock_sync_cf, mock_sync_bs, fresh_earnings_for, db,
    ):
        """No Ticker row at all → fall through to the legacy freshness path
        (which already calls sync_earnings only when stale)."""
        fresh_earnings_for("NEWCO")  # earnings exist, Ticker doesn't
        _ensure_fresh_data("NEWCO")
        mock_sync_earnings.assert_not_called()

    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_does_not_force_for_brazilian_tickers(
        self, mock_sync_earnings, mock_sync_cf, mock_sync_bs, fresh_earnings_for, db,
    ):
        """Brazilian tickers get reported_currency='BRL' eagerly via
        sync_tickers and BRAPI's incomeStatementHistory does not expose a
        reportedCurrency field anyway. Empty reported_currency on a BR row
        is unexpected; we should not pile on FMP-style sync attempts."""
        Ticker.objects.create(symbol="PETR4", name="Petrobras", reported_currency="")
        fresh_earnings_for("PETR4")

        _ensure_fresh_data("PETR4")

        mock_sync_earnings.assert_not_called()
