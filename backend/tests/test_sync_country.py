"""Tests for the sync_country management command — backfill ISO country
codes from FMP profiles for tickers missing them.
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from quotes.models import Ticker


class TestSyncCountry:
    @patch("quotes.management.commands.sync_country.fetch_profile")
    def test_populates_country_for_us_tickers(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", country="")
        Ticker.objects.create(symbol="TSM", name="TSMC", type="stock", country="")

        mock_fetch_profile.side_effect = [
            {"country": "US"},
            {"country": "TW"},
        ]

        call_command("sync_country", stdout=StringIO(), stderr=StringIO())

        assert Ticker.objects.get(symbol="AAPL").country == "US"
        assert Ticker.objects.get(symbol="TSM").country == "TW"

    @patch("quotes.management.commands.sync_country.fetch_profile")
    def test_uppercases_and_strips_iso_codes(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", country="")

        mock_fetch_profile.return_value = {"country": "  us "}

        call_command("sync_country", stdout=StringIO(), stderr=StringIO())

        assert Ticker.objects.get(symbol="AAPL").country == "US"

    @patch("quotes.management.commands.sync_country.fetch_profile")
    def test_skips_tickers_with_existing_country(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", country="US")
        Ticker.objects.create(symbol="TSM", name="TSMC", type="stock", country="")

        mock_fetch_profile.return_value = {"country": "TW"}

        call_command("sync_country", stdout=StringIO(), stderr=StringIO())

        mock_fetch_profile.assert_called_once_with("TSM")

    @patch("quotes.management.commands.sync_country.fetch_profile")
    def test_skips_brazilian_pattern_tickers(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock", country="")
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", country="")

        mock_fetch_profile.return_value = {"country": "US"}

        call_command("sync_country", stdout=StringIO(), stderr=StringIO())

        # PETR4 is Brazilian-pattern; the data migration handles those, so
        # the FMP backfill must skip them to avoid wasting API calls.
        mock_fetch_profile.assert_called_once_with("AAPL")

    @patch("quotes.management.commands.sync_country.fetch_profile")
    def test_respects_batch_size(self, mock_fetch_profile, db):
        for symbol in ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]:
            Ticker.objects.create(symbol=symbol, name=symbol, type="stock", country="")

        mock_fetch_profile.return_value = {"country": "US"}

        call_command(
            "sync_country", "--batch-size", "3",
            stdout=StringIO(), stderr=StringIO(),
        )

        assert mock_fetch_profile.call_count == 3

    @patch("quotes.management.commands.sync_country.fetch_profile")
    def test_skips_tickers_with_no_country_in_profile(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", country="")

        mock_fetch_profile.return_value = {"country": ""}

        call_command("sync_country", stdout=StringIO(), stderr=StringIO())

        assert Ticker.objects.get(symbol="AAPL").country == ""

    @patch("quotes.management.commands.sync_country.fetch_profile")
    def test_prioritizes_tickers_with_market_cap(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="SMALL", name="Small", type="stock", country="", market_cap=None)
        Ticker.objects.create(symbol="BIG", name="Big", type="stock", country="", market_cap=1_000_000_000)

        mock_fetch_profile.return_value = {"country": "US"}

        call_command(
            "sync_country", "--batch-size", "1",
            stdout=StringIO(), stderr=StringIO(),
        )

        mock_fetch_profile.assert_called_once_with("BIG")
