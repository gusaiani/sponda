"""Tests for US ticker sync command — ensures only actual companies are imported."""
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.models import Ticker


MOCK_STOCK_LIST = [
    {"symbol": "AAPL", "companyName": "Apple Inc."},
    {"symbol": "MSFT", "companyName": "Microsoft Corporation"},
    {"symbol": "SPY", "companyName": "SPDR S&P 500 ETF Trust"},
    {"symbol": "QQQ", "companyName": "Invesco QQQ Trust"},
    {"symbol": "SCHB", "companyName": "Schwab U.S. Broad Market ETF"},
    {"symbol": "VGSH", "companyName": "Vanguard Short-Term Treasury ETF"},
    {"symbol": "ARKK", "companyName": "ARK Innovation ETF"},
    {"symbol": "BRK.B", "companyName": "Berkshire Hathaway Inc."},
    {"symbol": "PETR4", "companyName": "Petrobras"},
    {"symbol": "PRIF-PG", "companyName": "Priority Income Fund, Inc."},
    {"symbol": "DXSLX", "companyName": "Direxion Monthly Small Cap Bull 2X Fund"},
    {"symbol": "GOOGL", "companyName": "Alphabet Inc."},
    {"symbol": "AAHTX", "companyName": "American Funds 2045 Trgt Date Retire A"},
    {"symbol": "AEGFX", "companyName": "American Funds EuroPacific Growth Cl F-1 Shs"},
    {"symbol": "WTFC", "companyName": "Wintrust Financial Corporation"},
    # Preferred shares, convertibles, debentures, warrants — should be excluded
    {"symbol": "BRKRP", "companyName": "Bruker Corporation 6.375% Mandatory Convertible Preferred Stock, Series A"},
    {"symbol": "WRB-PH", "companyName": "W.R. Berkley Corporation 4.125%"},
    {"symbol": "WRB-PE", "companyName": "W. R. Berkley Corporation 5.70% SB DB 2058"},
    {"symbol": "BAC-PB", "companyName": "Bank of America Corporation Depositary Shares Preferred Series B"},
    {"symbol": "JPM-PD", "companyName": "JPMorgan Chase Depositary Shares Preferred Series DD"},
    {"symbol": "GS-PA", "companyName": "Goldman Sachs 5.50% Fixed-to-Floating Rate Non-Cumulative Preferred Stock"},
    {"symbol": "AAIC-PB", "companyName": "Arlington Asset Investment 6.750% Notes Due 2025"},
    {"symbol": "WTRG-WS", "companyName": "Essential Utilities Inc Warrant"},
    {"symbol": "ACAHW", "companyName": "Atlantic Coastal Acquisition Corp Warrant"},
    {"symbol": "RILYK", "companyName": "B. Riley Financial Inc 5.25% Senior Notes Due 2028"},
    {"symbol": "BRKB", "companyName": "Bruker Corporation"},
]

MOCK_ETF_LIST = [
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust"},
    {"symbol": "ARKK", "name": "ARK Innovation ETF"},
]


def _run_sync():
    out = StringIO()
    call_command("refresh_us_tickers", stdout=out, stderr=StringIO())
    return out.getvalue()


class TestRefreshUsTickers:
    @patch("quotes.management.commands.refresh_us_tickers.fetch_etf_symbols")
    @patch("quotes.management.commands.refresh_us_tickers.requests.get")
    def test_excludes_etfs_by_symbol(self, mock_requests_get, mock_etf_symbols, db):
        mock_requests_get.return_value.json.return_value = MOCK_STOCK_LIST
        mock_requests_get.return_value.raise_for_status = lambda: None
        mock_etf_symbols.return_value = {"SPY", "QQQ", "ARKK"}

        _run_sync()

        assert not Ticker.objects.filter(symbol="SPY").exists()
        assert not Ticker.objects.filter(symbol="QQQ").exists()
        assert not Ticker.objects.filter(symbol="ARKK").exists()

    @patch("quotes.management.commands.refresh_us_tickers.fetch_etf_symbols")
    @patch("quotes.management.commands.refresh_us_tickers.requests.get")
    def test_excludes_funds_by_name_pattern(self, mock_requests_get, mock_etf_symbols, db):
        mock_requests_get.return_value.json.return_value = MOCK_STOCK_LIST
        mock_requests_get.return_value.raise_for_status = lambda: None
        mock_etf_symbols.return_value = set()

        _run_sync()

        assert not Ticker.objects.filter(symbol="SCHB").exists()
        assert not Ticker.objects.filter(symbol="VGSH").exists()
        assert not Ticker.objects.filter(symbol="PRIF-PG").exists()
        assert not Ticker.objects.filter(symbol="DXSLX").exists()
        # "Funds" (plural) and target-date/class-share patterns
        assert not Ticker.objects.filter(symbol="AAHTX").exists()
        assert not Ticker.objects.filter(symbol="AEGFX").exists()

    @patch("quotes.management.commands.refresh_us_tickers.fetch_etf_symbols")
    @patch("quotes.management.commands.refresh_us_tickers.requests.get")
    def test_keeps_actual_companies(self, mock_requests_get, mock_etf_symbols, db):
        mock_requests_get.return_value.json.return_value = MOCK_STOCK_LIST
        mock_requests_get.return_value.raise_for_status = lambda: None
        mock_etf_symbols.return_value = {"SPY", "QQQ", "ARKK"}

        _run_sync()

        assert Ticker.objects.filter(symbol="AAPL").exists()
        assert Ticker.objects.filter(symbol="MSFT").exists()
        assert Ticker.objects.filter(symbol="GOOGL").exists()
        # Companies with "Trust" in their name should NOT be filtered
        assert Ticker.objects.filter(symbol="WTFC").exists()

    @patch("quotes.management.commands.refresh_us_tickers.fetch_etf_symbols")
    @patch("quotes.management.commands.refresh_us_tickers.requests.get")
    def test_excludes_dotted_and_brazilian_tickers(self, mock_requests_get, mock_etf_symbols, db):
        mock_requests_get.return_value.json.return_value = MOCK_STOCK_LIST
        mock_requests_get.return_value.raise_for_status = lambda: None
        mock_etf_symbols.return_value = set()

        _run_sync()

        assert not Ticker.objects.filter(symbol="BRK.B").exists()
        assert not Ticker.objects.filter(symbol="PETR4").exists()

    @patch("quotes.management.commands.refresh_us_tickers.fetch_etf_symbols")
    @patch("quotes.management.commands.refresh_us_tickers.requests.get")
    def test_deletes_stale_us_tickers(self, mock_requests_get, mock_etf_symbols, db):
        # Pre-existing ETF that should be cleaned up
        Ticker.objects.create(symbol="SPY", name="SPDR S&P 500 ETF", type="stock")
        # Pre-existing Brazilian ticker should NOT be deleted
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock")

        mock_requests_get.return_value.json.return_value = [
            {"symbol": "AAPL", "companyName": "Apple Inc."},
        ]
        mock_requests_get.return_value.raise_for_status = lambda: None
        mock_etf_symbols.return_value = set()

        _run_sync()

        assert Ticker.objects.filter(symbol="AAPL").exists()
        assert Ticker.objects.filter(symbol="PETR4").exists()
        assert not Ticker.objects.filter(symbol="SPY").exists()

    @patch("quotes.management.commands.refresh_us_tickers.fetch_etf_symbols")
    @patch("quotes.management.commands.refresh_us_tickers.requests.get")
    def test_excludes_preferred_shares_and_convertibles(self, mock_requests_get, mock_etf_symbols, db):
        mock_requests_get.return_value.json.return_value = MOCK_STOCK_LIST
        mock_requests_get.return_value.raise_for_status = lambda: None
        mock_etf_symbols.return_value = set()

        _run_sync()

        # Preferred shares
        assert not Ticker.objects.filter(symbol="BRKRP").exists()
        assert not Ticker.objects.filter(symbol="BAC-PB").exists()
        assert not Ticker.objects.filter(symbol="GS-PA").exists()
        assert not Ticker.objects.filter(symbol="JPM-PD").exists()
        # Instruments with percentage in name (fixed-rate securities)
        assert not Ticker.objects.filter(symbol="WRB-PH").exists()
        assert not Ticker.objects.filter(symbol="WRB-PE").exists()
        # Notes / debentures
        assert not Ticker.objects.filter(symbol="AAIC-PB").exists()
        assert not Ticker.objects.filter(symbol="RILYK").exists()
        # Warrants
        assert not Ticker.objects.filter(symbol="WTRG-WS").exists()
        assert not Ticker.objects.filter(symbol="ACAHW").exists()
        # But the actual company should remain
        assert Ticker.objects.filter(symbol="BRKB").exists()

    @patch("quotes.management.commands.refresh_us_tickers.fetch_etf_symbols")
    @patch("quotes.management.commands.refresh_us_tickers.requests.get")
    def test_only_companies_remain(self, mock_requests_get, mock_etf_symbols, db):
        mock_requests_get.return_value.json.return_value = MOCK_STOCK_LIST
        mock_requests_get.return_value.raise_for_status = lambda: None
        mock_etf_symbols.return_value = {"SPY", "QQQ", "ARKK"}

        _run_sync()

        symbols = set(Ticker.objects.values_list("symbol", flat=True))
        assert symbols == {"AAPL", "MSFT", "GOOGL", "WTFC", "BRKB"}
