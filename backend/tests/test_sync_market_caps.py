"""Tests for market-cap sync command — routes BR tickers to BRAPI, US to FMP."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from quotes.models import Ticker


class TestSyncMarketCapsRouting:
    """The command must route each ticker to the right provider based on pattern."""

    @patch("quotes.management.commands.sync_market_caps.fetch_quote")
    def test_populates_market_cap_for_us_ticker(self, mock_fetch_quote, db):
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", type="stock", market_cap=None)
        mock_fetch_quote.return_value = {"marketCap": 3_500_000_000_000}

        call_command("sync_market_caps", stdout=StringIO(), stderr=StringIO())

        aapl = Ticker.objects.get(symbol="AAPL")
        assert aapl.market_cap == 3_500_000_000_000

    @patch("quotes.management.commands.sync_market_caps.fetch_quote")
    def test_populates_market_cap_for_brazilian_ticker(self, mock_fetch_quote, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras PN", type="stock", market_cap=None)
        mock_fetch_quote.return_value = {"marketCap": 602_167_750_093}

        call_command("sync_market_caps", stdout=StringIO(), stderr=StringIO())

        petr4 = Ticker.objects.get(symbol="PETR4")
        assert petr4.market_cap == 602_167_750_093

    @patch("quotes.management.commands.sync_market_caps.fetch_quote")
    def test_processes_both_br_and_us_tickers_in_same_run(self, mock_fetch_quote, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock", market_cap=None)
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", market_cap=None)

        def quote_by_symbol(symbol):
            return {
                "PETR4": {"marketCap": 602_000_000_000},
                "AAPL": {"marketCap": 3_500_000_000_000},
            }[symbol]

        mock_fetch_quote.side_effect = quote_by_symbol

        call_command("sync_market_caps", stdout=StringIO(), stderr=StringIO())

        assert Ticker.objects.get(symbol="PETR4").market_cap == 602_000_000_000
        assert Ticker.objects.get(symbol="AAPL").market_cap == 3_500_000_000_000

    @patch("quotes.management.commands.sync_market_caps.fetch_quote")
    def test_skips_tickers_that_already_have_market_cap(self, mock_fetch_quote, db):
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", market_cap=1_000_000_000)
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock", market_cap=None)

        mock_fetch_quote.return_value = {"marketCap": 602_000_000_000}

        call_command("sync_market_caps", stdout=StringIO(), stderr=StringIO())

        # Only PETR4 should be fetched — AAPL already has market cap
        mock_fetch_quote.assert_called_once_with("PETR4")

    @patch("quotes.management.commands.sync_market_caps.fetch_quote")
    def test_marks_missing_market_cap_as_zero_to_avoid_refetch(self, mock_fetch_quote, db):
        Ticker.objects.create(symbol="OBSCURE1", name="Obscure", type="stock", market_cap=None)
        mock_fetch_quote.return_value = {}  # no marketCap field

        call_command("sync_market_caps", stdout=StringIO(), stderr=StringIO())

        assert Ticker.objects.get(symbol="OBSCURE1").market_cap == 0

    @patch("quotes.management.commands.sync_market_caps.fetch_quote")
    def test_continues_after_provider_error(self, mock_fetch_quote, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock", market_cap=None)
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", market_cap=None)

        from quotes.providers import ProviderError
        # Command processes alphabetically: AAPL first (fails), then PETR4 (succeeds)
        mock_fetch_quote.side_effect = [
            ProviderError("FMP down"),
            {"marketCap": 602_000_000_000},
        ]

        out = StringIO()
        call_command("sync_market_caps", stdout=out, stderr=StringIO())

        assert Ticker.objects.get(symbol="AAPL").market_cap is None
        assert Ticker.objects.get(symbol="PETR4").market_cap == 602_000_000_000

    @patch("quotes.management.commands.sync_market_caps.fetch_quote")
    def test_respects_limit_argument(self, mock_fetch_quote, db):
        for symbol in ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3"]:
            Ticker.objects.create(symbol=symbol, name=symbol, type="stock", market_cap=None)

        mock_fetch_quote.return_value = {"marketCap": 100_000_000_000}

        call_command("sync_market_caps", "--limit", "2", stdout=StringIO(), stderr=StringIO())

        assert mock_fetch_quote.call_count == 2
