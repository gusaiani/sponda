"""Tests for the warm_cache management command."""
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.models import IPCAIndex, LookupLog, QuarterlyCashFlow, QuarterlyEarnings


def _mock_fetch_quote(ticker):
    return {
        "symbol": ticker,
        "longName": f"Test {ticker}",
        "shortName": ticker,
        "regularMarketPrice": 50.0,
        "marketCap": 500_000_000_000,
    }


def _mock_sync(ticker):
    return []


def _mock_historical(ticker):
    return [
        {"date": 1704067200, "adjustedClose": 30.0},
        {"date": 1735689600, "adjustedClose": 35.0},
    ]


def _mock_dividends(ticker):
    return {"cashDividends": [], "stockDividends": []}


@pytest.mark.django_db
class TestWarmCacheCommand:
    @patch("quotes.views.fetch_dividends", side_effect=_mock_dividends)
    @patch("quotes.views.fetch_historical_prices", side_effect=_mock_historical)
    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_balance_sheets", side_effect=_mock_sync)
    @patch("quotes.views.sync_cash_flows", side_effect=_mock_sync)
    @patch("quotes.views.sync_earnings", side_effect=_mock_sync)
    def test_warms_cache_for_popular_tickers(
        self, _s1, _s2, _s3, _q, _h, _d, db
    ):
        # Create lookup logs
        LookupLog.objects.create(session_key="s1", ticker="PETR4")
        LookupLog.objects.create(session_key="s2", ticker="PETR4")
        LookupLog.objects.create(session_key="s3", ticker="VALE3")

        # Seed minimal data for the tickers
        for ticker in ["PETR4", "VALE3"]:
            for year in range(2016, 2026):
                for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                    QuarterlyEarnings.objects.create(
                        ticker=ticker, end_date=date(year, month, day),
                        net_income=10_000_000_000,
                    )
                    QuarterlyCashFlow.objects.create(
                        ticker=ticker, end_date=date(year, month, day),
                        operating_cash_flow=20_000_000_000,
                        investment_cash_flow=-8_000_000_000,
                    )
            for year in range(2016, 2026):
                IPCAIndex.objects.get_or_create(
                    date=date(year, 12, 1),
                    defaults={"annual_rate": Decimal("4.5")},
                )

        output = StringIO()
        call_command("warm_cache", "--limit=5", stdout=output)
        result = output.getvalue()
        assert "Done" in result
        assert "cached" in result

    def test_handles_no_lookup_logs(self, db):
        output = StringIO()
        call_command("warm_cache", stdout=output)
        assert "Warming cache for 0 tickers" in output.getvalue()
