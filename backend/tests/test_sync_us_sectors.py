"""Tests for US ticker sector sync — fetching sectors from FMP profiles."""
from io import StringIO
from unittest.mock import patch

import pytest

from django.core.management import call_command

from quotes.fmp import fetch_profile
from quotes.models import Ticker


MOCK_PROFILE_TEAM = [
    {
        "symbol": "TEAM",
        "companyName": "Atlassian Corporation",
        "sector": "Technology",
        "industry": "Software - Application",
    }
]

MOCK_PROFILE_EMPTY = []


class TestFetchProfile:
    @patch("quotes.fmp._get")
    def test_returns_sector_and_industry(self, mock_get):
        mock_get.return_value = MOCK_PROFILE_TEAM
        result = fetch_profile("TEAM")
        assert result["sector"] == "Technology"
        assert result["industry"] == "Software - Application"
        mock_get.assert_called_once_with(
            "/stable/profile",
            params={"symbol": "TEAM"},
        )

    @patch("quotes.fmp._get")
    def test_returns_none_on_empty_response(self, mock_get):
        mock_get.return_value = MOCK_PROFILE_EMPTY
        result = fetch_profile("FAKE")
        assert result is None


class TestSyncUsSectors:
    @patch("quotes.management.commands.sync_us_sectors.fetch_profile")
    def test_populates_sector_for_us_tickers(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="TEAM", name="Atlassian", type="stock", sector="")
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", type="stock", sector="")

        mock_fetch_profile.side_effect = [
            {"sector": "Technology", "industry": "Software - Application"},
            {"sector": "Technology", "industry": "Consumer Electronics"},
        ]

        out = StringIO()
        call_command("sync_us_sectors", stdout=out, stderr=StringIO())

        team = Ticker.objects.get(symbol="TEAM")
        assert team.sector == "Technology"
        aapl = Ticker.objects.get(symbol="AAPL")
        assert aapl.sector == "Technology"

    @patch("quotes.management.commands.sync_us_sectors.fetch_profile")
    def test_skips_tickers_with_existing_sector(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="TEAM", name="Atlassian", type="stock", sector="Technology")
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", type="stock", sector="")

        mock_fetch_profile.return_value = {"sector": "Technology", "industry": "Consumer Electronics"}

        out = StringIO()
        call_command("sync_us_sectors", stdout=out, stderr=StringIO())

        # Should only fetch profile for AAPL (TEAM already has sector)
        mock_fetch_profile.assert_called_once_with("AAPL")

    @patch("quotes.management.commands.sync_us_sectors.fetch_profile")
    def test_skips_brazilian_tickers(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock", sector="")
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", type="stock", sector="")

        mock_fetch_profile.return_value = {"sector": "Technology", "industry": "Consumer Electronics"}

        out = StringIO()
        call_command("sync_us_sectors", stdout=out, stderr=StringIO())

        # Should only fetch for AAPL, not PETR4
        mock_fetch_profile.assert_called_once_with("AAPL")

    @patch("quotes.management.commands.sync_us_sectors.fetch_profile")
    def test_respects_batch_size(self, mock_fetch_profile, db):
        for name in ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]:
            Ticker.objects.create(symbol=name, name=f"{name} Inc.", type="stock", sector="")

        mock_fetch_profile.return_value = {"sector": "Technology", "industry": "Software"}

        out = StringIO()
        call_command("sync_us_sectors", "--batch-size", "3", stdout=out, stderr=StringIO())

        assert mock_fetch_profile.call_count == 3

    @patch("quotes.management.commands.sync_us_sectors.fetch_profile")
    def test_handles_failed_profile_fetch(self, mock_fetch_profile, db):
        Ticker.objects.create(symbol="TEAM", name="Atlassian", type="stock", sector="")
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", type="stock", sector="")

        # Keyed by symbol rather than by call order: the command decides the
        # order, and a list of results silently attaches them to whichever
        # ticker happens to come first.
        profiles = {
            "TEAM": None,
            "AAPL": {"sector": "Technology", "industry": "Consumer Electronics"},
        }
        mock_fetch_profile.side_effect = lambda symbol: profiles[symbol]

        out = StringIO()
        call_command("sync_us_sectors", stdout=out, stderr=StringIO())

        team = Ticker.objects.get(symbol="TEAM")
        assert team.sector == ""  # Still empty
        aapl = Ticker.objects.get(symbol="AAPL")
        assert aapl.sector == "Technology"

    @patch("quotes.management.commands.sync_us_sectors.fetch_profile")
    def test_prioritizes_tickers_with_market_cap(self, mock_fetch_profile, db):
        """Tickers with market cap (more likely to be viewed) should be processed first."""
        Ticker.objects.create(symbol="SMALL", name="Small Co", type="stock", sector="", market_cap=None)
        Ticker.objects.create(symbol="BIG", name="Big Co", type="stock", sector="", market_cap=1000000000)

        mock_fetch_profile.return_value = {"sector": "Technology", "industry": "Software"}

        out = StringIO()
        call_command("sync_us_sectors", "--batch-size", "1", stdout=out, stderr=StringIO())

        # Should process BIG first (has market cap)
        mock_fetch_profile.assert_called_once_with("BIG")


@pytest.mark.django_db
def test_tickers_without_a_market_cap_are_processed_in_a_stable_order():
    """Ordering by market cap alone leaves ties to the database.

    Every ticker without a market cap sorts equal, so Postgres may return them
    in any order and two runs over the same data can process them differently.
    That makes batch runs unreproducible, and it made
    test_handles_failed_profile_fetch fail intermittently in CI · its mock
    hands out results by call order, so whichever row came first got them.
    """
    for symbol in ("ZZZZ", "AAAA", "MMMM"):
        Ticker.objects.create(symbol=symbol, name=symbol, type="stock", sector="")

    from quotes.management.commands.sync_us_sectors import Command

    first = [t.symbol for t in Command().tickers_needing_sector()]
    second = [t.symbol for t in Command().tickers_needing_sector()]

    assert first == second
    assert first == ["AAAA", "MMMM", "ZZZZ"]
