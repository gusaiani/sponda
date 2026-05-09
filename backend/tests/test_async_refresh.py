"""Tests for the stale-while-revalidate refresh path.

Behaviour:

- Cold ticker (no data at all) → run sync_* synchronously inside the
  request, since we have nothing to render otherwise.
- Stale ticker (data exists but older than 24h) → enqueue a Celery task
  to refresh in the background, return immediately. The user reads
  yesterday's data this request and tomorrow's data on the next.
- Fresh ticker (data younger than 24h) → no-op.

The reported_currency backfill nudge stays synchronous, since the field
is needed by the very next computation in the same request.
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from quotes.models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings, Ticker
from quotes.views import _ensure_fresh_data


def _make_stale(model, ticker: str) -> None:
    """Insert a row for `ticker` with fetched_at backdated 48h."""
    record = model.objects.create(ticker=ticker, end_date=date(2025, 12, 31))
    backdate = timezone.now() - timedelta(hours=48)
    model.objects.filter(pk=record.pk).update(fetched_at=backdate)


@pytest.mark.django_db
class TestStaleWhileRevalidate:
    @patch("quotes.views.refresh_provider_data")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_cold_ticker_runs_synchronously(
        self, mock_e, mock_cf, mock_bs, mock_task,
    ):
        # No rows at all → sync each provider, do not enqueue.
        _ensure_fresh_data("NEWCO")
        mock_e.assert_called_once_with("NEWCO")
        mock_cf.assert_called_once_with("NEWCO")
        mock_bs.assert_called_once_with("NEWCO")
        mock_task.delay.assert_not_called()

    @patch("quotes.views.refresh_provider_data")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_stale_ticker_enqueues_and_returns(
        self, mock_e, mock_cf, mock_bs, mock_task,
    ):
        _make_stale(QuarterlyEarnings, "PETR4")
        _make_stale(QuarterlyCashFlow, "PETR4")
        _make_stale(BalanceSheet, "PETR4")

        _ensure_fresh_data("PETR4")

        mock_e.assert_not_called()
        mock_cf.assert_not_called()
        mock_bs.assert_not_called()
        mock_task.delay.assert_called_once_with("PETR4")

    @patch("quotes.views.refresh_provider_data")
    @patch("quotes.views.sync_balance_sheets")
    @patch("quotes.views.sync_cash_flows")
    @patch("quotes.views.sync_earnings")
    def test_fresh_ticker_is_noop(
        self, mock_e, mock_cf, mock_bs, mock_task,
    ):
        QuarterlyEarnings.objects.create(ticker="PETR4", end_date=date(2025, 12, 31))
        QuarterlyCashFlow.objects.create(ticker="PETR4", end_date=date(2025, 12, 31))
        BalanceSheet.objects.create(ticker="PETR4", end_date=date(2025, 9, 30))

        _ensure_fresh_data("PETR4")

        mock_e.assert_not_called()
        mock_cf.assert_not_called()
        mock_bs.assert_not_called()
        mock_task.delay.assert_not_called()
