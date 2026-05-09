"""Tests for the favorites-aware warm_cache command.

The rewritten command:
- Sources tickers from active users' favorites + saved lists in addition
  to the LookupLog top-N (popularity).
- Fans out across a thread pool instead of a serial sleep loop.
- Skips tickers whose pe10 cache is already warm enough.
"""
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command

from accounts.models import FavoriteCompany, SavedList
from quotes.models import LookupLog, QuarterlyCashFlow, QuarterlyEarnings, IPCAIndex


User = get_user_model()


def _mock_fetch_quote(ticker):
    return {
        "symbol": ticker,
        "longName": f"Test {ticker}",
        "shortName": ticker,
        "regularMarketPrice": 50.0,
        "marketCap": 500_000_000_000,
    }


def _seed_data_for(ticker: str) -> None:
    for year in range(2016, 2026):
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker=ticker, end_date=date(year, month, day), net_income=10_000_000_000,
            )
            QuarterlyCashFlow.objects.create(
                ticker=ticker, end_date=date(year, month, day),
                operating_cash_flow=20_000_000_000, investment_cash_flow=-8_000_000_000,
            )
    for year in range(2016, 2026):
        IPCAIndex.objects.get_or_create(
            date=date(year, 12, 1), defaults={"annual_rate": Decimal("4.5")},
        )


@pytest.fixture(autouse=True)
def clear_cache_fixture():
    cache.clear()
    yield
    cache.clear()


# Same reason as test_quotes_batch.py: warm_cache uses a thread pool
# whose worker connections do not participate in the test rollback.
@pytest.mark.django_db(transaction=True)
class TestWarmCacheV2:
    @patch("quotes.views.fetch_dividends", return_value={"cashDividends": [], "stockDividends": []})
    @patch("quotes.views.fetch_historical_prices", return_value=[])
    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_balance_sheets", return_value=[])
    @patch("quotes.views.sync_cash_flows", return_value=[])
    @patch("quotes.views.sync_earnings", return_value=[])
    def test_includes_favorites_and_lists(
        self, _se, _scf, _sbs, _q, _h, _d,
    ):
        user = User.objects.create_user(username="u", email="u@test.com", password="pw")
        FavoriteCompany.objects.create(user=user, ticker="PETR4")
        SavedList.objects.create(
            user=user, name="My list", tickers=["VALE3"], share_token="t1",
        )
        for ticker in ("PETR4", "VALE3"):
            _seed_data_for(ticker)

        output = StringIO()
        call_command("warm_cache", "--limit=10", stdout=output)
        text = output.getvalue()
        # Both tickers got warmed, even though neither is in LookupLog.
        assert "PETR4" in text or "Done" in text
        # Cache key for PETR4 should now be set.
        assert cache.get("pe10:PETR4") is not None
        assert cache.get("pe10:VALE3") is not None

    @patch("quotes.views.fetch_dividends", return_value={"cashDividends": [], "stockDividends": []})
    @patch("quotes.views.fetch_historical_prices", return_value=[])
    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_balance_sheets", return_value=[])
    @patch("quotes.views.sync_cash_flows", return_value=[])
    @patch("quotes.views.sync_earnings", return_value=[])
    def test_dedupes_across_sources(
        self, _se, _scf, _sbs, mock_quote, _h, _d,
    ):
        user = User.objects.create_user(username="u", email="u@test.com", password="pw")
        FavoriteCompany.objects.create(user=user, ticker="PETR4")
        SavedList.objects.create(
            user=user, name="x", tickers=["PETR4"], share_token="t2",
        )
        for _ in range(3):
            LookupLog.objects.create(session_key="s", ticker="PETR4")
        _seed_data_for("PETR4")

        call_command("warm_cache", "--limit=10", stdout=StringIO())
        # fetch_quote should be invoked at most once for PETR4 (not three times).
        symbols_called = [
            call.args[0] if call.args else call.kwargs.get("ticker")
            for call in mock_quote.call_args_list
        ]
        assert symbols_called.count("PETR4") == 1

    @patch("quotes.views.fetch_dividends", return_value={"cashDividends": [], "stockDividends": []})
    @patch("quotes.views.fetch_historical_prices", return_value=[])
    @patch("quotes.views.fetch_quote", side_effect=_mock_fetch_quote)
    @patch("quotes.views.sync_balance_sheets", return_value=[])
    @patch("quotes.views.sync_cash_flows", return_value=[])
    @patch("quotes.views.sync_earnings", return_value=[])
    def test_skips_already_warm_tickers(
        self, _se, _scf, _sbs, mock_quote, _h, _d,
    ):
        cache.set("pe10:PETR4", {"already": "warm"}, 60 * 60)
        LookupLog.objects.create(session_key="s", ticker="PETR4")
        _seed_data_for("PETR4")

        call_command("warm_cache", "--limit=10", stdout=StringIO())
        # Cache was already warm, so the command should skip the recompute.
        mock_quote.assert_not_called()
