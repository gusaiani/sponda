"""Tests for the bulk reported_currency backfill command."""
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.models import Ticker


def _run(*args):
    call_command("backfill_reported_currency", *args, stdout=StringIO(), stderr=StringIO())


@pytest.mark.django_db
class TestBackfillReportedCurrency:
    @patch("quotes.management.commands.backfill_reported_currency.fetch_currency_map")
    def test_stamps_reporting_currency_from_fmp(self, mock_fetch):
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk", reported_currency="")
        Ticker.objects.create(symbol="AAPL", name="Apple", reported_currency="")
        mock_fetch.return_value = {
            "NVO": {"trading": "USD", "reporting": "DKK"},
            "AAPL": {"trading": "USD", "reporting": "USD"},
        }
        _run()
        assert Ticker.objects.get(symbol="NVO").reported_currency == "DKK"
        assert Ticker.objects.get(symbol="AAPL").reported_currency == "USD"

    @patch("quotes.management.commands.backfill_reported_currency.fetch_currency_map")
    def test_skips_brazilian_tickers(self, mock_fetch):
        """BR tickers get BRL eagerly via brapi.sync_tickers; the bulk
        backfill must not clobber that with FMP data (FMP doesn't carry
        B3 listings)."""
        Ticker.objects.create(symbol="PETR4", name="Petrobras", reported_currency="BRL")
        mock_fetch.return_value = {"PETR4": {"trading": "USD", "reporting": "USD"}}  # nonsense, ignored
        _run()
        assert Ticker.objects.get(symbol="PETR4").reported_currency == "BRL"

    @patch("quotes.management.commands.backfill_reported_currency.fetch_currency_map")
    def test_leaves_empty_when_fmp_has_no_data(self, mock_fetch):
        Ticker.objects.create(symbol="DELISTED", name="Some Delisted Co", reported_currency="")
        mock_fetch.return_value = {}  # FMP doesn't know this ticker
        _run()
        assert Ticker.objects.get(symbol="DELISTED").reported_currency == ""

    @patch("quotes.management.commands.backfill_reported_currency.fetch_currency_map")
    def test_dry_run_does_not_write(self, mock_fetch):
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk", reported_currency="")
        mock_fetch.return_value = {"NVO": {"trading": "USD", "reporting": "DKK"}}
        _run("--dry-run")
        assert Ticker.objects.get(symbol="NVO").reported_currency == ""
