"""A symbol that cannot name a company must not cost a provider call.

Traffic to `/pt/$TFCO4` (a cashtag, linked or pasted) reached the quote
endpoints server-side. `$TFCO4` fails the Brazilian pattern, so it was
routed to FMP, which spent an income-statement, a cash-flow, a
balance-sheet and a quote call to conclude what its shape already said.
Nothing is stored for a symbol that does not exist, so every repeat
request paid again.
"""

import json

import pytest
from django.test import Client

from quotes import providers
from quotes.models import LookupLog

MALFORMED = "$TFCO4"


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def no_provider_calls(monkeypatch):
    """Fail loudly if a malformed symbol ever reaches a provider."""
    import quotes.views as views

    def _boom(*_args, **_kwargs):  # pragma: no cover - asserted via not-called
        raise AssertionError("a provider was called for a malformed symbol")

    for attribute in (
        "_ensure_fresh_data",
        "fetch_quote",
        "sync_earnings",
        "sync_cash_flows",
        "sync_balance_sheets",
    ):
        monkeypatch.setattr(views, attribute, _boom)


class TestQuoteEndpoints:
    @pytest.mark.parametrize(
        "url",
        [
            f"/api/quote/{MALFORMED}/",
            f"/api/quote/{MALFORMED}/multiples-history/",
            f"/api/quote/{MALFORMED}/fundamentals/",
        ],
    )
    def test_malformed_symbol_is_a_404_without_a_provider_call(
        self, url, api_client, db, no_provider_calls
    ):
        response = api_client.get(url)

        assert response.status_code == 404
        assert "error" in response.json()

    def test_a_rejected_symbol_does_not_count_against_the_daily_cap(
        self, api_client, db, no_provider_calls
    ):
        api_client.get(f"/api/quote/{MALFORMED}/")

        assert LookupLog.objects.count() == 0

    def test_a_well_formed_symbol_still_reaches_the_quote_path(
        self, api_client, db, monkeypatch
    ):
        """The guard must not swallow the ordinary case."""
        import quotes.views as views

        reached = []
        monkeypatch.setattr(views, "_ensure_fresh_data", lambda ticker: reached.append(ticker))
        monkeypatch.setattr(
            views, "fetch_quote", lambda ticker: {"regularMarketPrice": 10, "marketCap": 1_000}
        )

        api_client.get("/api/quote/PETR4/")

        assert reached == ["PETR4"]


class TestBatchEndpoint:
    def test_malformed_symbol_fails_alone(self, api_client, db, monkeypatch):
        import quotes.views as views

        def _boom(ticker):  # pragma: no cover - asserted via not-called
            raise AssertionError(f"a provider was called for {ticker}")

        monkeypatch.setattr(views, "_ensure_fresh_data", _boom)
        monkeypatch.setattr(views, "fetch_quote", _boom)

        response = api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": [MALFORMED]}),
            content_type="application/json",
        )

        assert response.status_code == 200
        result = response.json()["results"][MALFORMED]
        assert result["status"] == 404
        assert "error" in result


class TestProviderBackstop:
    """The rule also holds one layer down, for every future caller."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda: providers.fetch_quote(MALFORMED),
            lambda: providers.fetch_dividends(MALFORMED),
            lambda: providers.fetch_historical_prices(MALFORMED),
            lambda: providers.sync_earnings(MALFORMED),
            lambda: providers.sync_cash_flows(MALFORMED),
            lambda: providers.sync_balance_sheets(MALFORMED),
        ],
    )
    def test_provider_entry_points_refuse_malformed_symbols(self, call, monkeypatch):
        def _boom(*_args, **_kwargs):  # pragma: no cover - asserted via not-called
            raise AssertionError("FMP was called for a malformed symbol")

        monkeypatch.setattr(providers.fmp, "_get", _boom)
        monkeypatch.setattr(providers.brapi, "_get", _boom)

        with pytest.raises(providers.ProviderError, match="No results"):
            call()

    def test_batch_quotes_drops_malformed_symbols(self, monkeypatch):
        seen = {}

        def _fake_fmp_batch(tickers):
            seen["tickers"] = tickers
            return {"AAPL": {"price": 1}}

        monkeypatch.setattr(providers.fmp, "fetch_quotes_batch", _fake_fmp_batch)

        results = providers.fetch_quotes_batch(["AAPL", MALFORMED])

        assert seen["tickers"] == ["AAPL"]
        assert MALFORMED not in results

    def test_historical_market_caps_refuses_malformed_symbols(self, monkeypatch):
        def _boom(*_args, **_kwargs):  # pragma: no cover - asserted via not-called
            raise AssertionError("the market cap store was called for a malformed symbol")

        monkeypatch.setattr(providers.market_cap_store, "get_daily_market_caps", _boom)

        with pytest.raises(providers.ProviderError, match="No results"):
            providers.fetch_historical_market_caps(MALFORMED)
