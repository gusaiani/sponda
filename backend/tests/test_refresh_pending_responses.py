"""Tests for telling the page that fresher statements are on their way.

A stale company is answered from stored statements while a background task
refetches them. The page used to have no way of knowing that, so the visitor
kept the stored numbers until a reload. These tests pin the three things the
page needs: a flag on each statement-derived payload, a cheap endpoint to
poll until the refresh lands, and the guarantee that a payload built during
a refresh is never kept in a cache that would outlive it.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from quotes.derived_data import (
    fundamentals_cache_key,
    multiples_history_cache_key,
    pe10_cache_key,
)
from quotes.models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings, Ticker
from quotes.providers import ProviderError
from quotes.statement_refresh_state import (
    claim_statement_refresh,
    is_statement_refresh_pending,
    record_statement_refresh_attempt,
)
from quotes.tasks import refresh_provider_data
from quotes.views import _ensure_fresh_data

STALE_FETCH_AGE_DAYS = 10
STATEMENT_MODELS = (QuarterlyEarnings, QuarterlyCashFlow, BalanceSheet)

PETR4_QUOTE = {
    "symbol": "PETR4",
    "longName": "Petroleo Brasileiro SA Pfd",
    "regularMarketPrice": 45.0,
    "marketCap": 585_000_000_000,
}
NO_DIVIDENDS = {"cashDividends": [], "stockDividends": []}


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def petr4_statements(db, sample_earnings, sample_cash_flows, sample_balance_sheet, sample_ipca):
    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", sector="Oil",
        market_cap=585_000_000_000, country="BR", reported_currency="BRL",
    )


@pytest.fixture
def stale_petr4_statements(petr4_statements):
    """Statements last checked long enough ago that a recheck is due."""
    last_checked = timezone.now() - timedelta(days=STALE_FETCH_AGE_DAYS)
    for model in STATEMENT_MODELS:
        model.objects.filter(ticker="PETR4").update(fetched_at=last_checked)


@pytest.fixture
def provider_calls():
    """Stand in for every provider the three company endpoints reach, and for
    the background task, so a stale request leaves its refresh in flight."""
    with (
        patch("quotes.views.fetch_quote", return_value=PETR4_QUOTE),
        patch("quotes.views.fetch_historical_prices", return_value=[]),
        patch("quotes.views.fetch_historical_market_caps", return_value=None),
        patch("quotes.views.fetch_dividends", return_value=NO_DIVIDENDS),
        patch("quotes.views.refresh_provider_data") as background_refresh,
    ):
        yield background_refresh


@pytest.mark.django_db
class TestEnqueueingOneRefresh:
    @patch("quotes.views.refresh_provider_data")
    def test_a_stale_company_reports_its_refresh_in_flight(
        self, background_refresh, stale_petr4_statements,
    ):
        assert _ensure_fresh_data("PETR4") is True

    @patch("quotes.views.refresh_provider_data")
    def test_a_fresh_company_reports_nothing_in_flight(
        self, background_refresh, petr4_statements,
    ):
        assert _ensure_fresh_data("PETR4") is False

    @patch("quotes.views.refresh_provider_data")
    def test_a_second_request_does_not_enqueue_a_second_refresh(
        self, background_refresh, stale_petr4_statements,
    ):
        """Quote, fundamentals and chart each pass through here for the same
        company within the same second."""
        _ensure_fresh_data("PETR4")
        still_in_flight = _ensure_fresh_data("PETR4")

        background_refresh.delay.assert_called_once_with("PETR4")
        assert still_in_flight is True

    @patch("quotes.views.refresh_provider_data")
    def test_a_company_still_stale_after_an_attempt_is_not_refreshed_again_at_once(
        self, background_refresh, stale_petr4_statements,
    ):
        claim_statement_refresh("PETR4")
        record_statement_refresh_attempt("PETR4")

        refresh_in_flight = _ensure_fresh_data("PETR4")

        background_refresh.delay.assert_not_called()
        assert refresh_in_flight is False

    @patch("quotes.views.refresh_provider_data")
    def test_a_refresh_that_cannot_be_enqueued_gives_its_claim_back(
        self, background_refresh, stale_petr4_statements,
    ):
        """A broker outage must not leave the company marked as refreshing
        with no task behind the mark."""
        background_refresh.delay.side_effect = ConnectionError("broker unreachable")

        with pytest.raises(ConnectionError):
            _ensure_fresh_data("PETR4")

        assert is_statement_refresh_pending("PETR4") is False
        assert claim_statement_refresh("PETR4") is True


@pytest.mark.django_db
class TestTheTaskClosesTheRefresh:
    @patch("quotes.tasks.refresh_derived_data")
    @patch("quotes.tasks.sync_balance_sheets")
    @patch("quotes.tasks.sync_cash_flows")
    @patch("quotes.tasks.sync_earnings")
    def test_a_finished_refresh_is_no_longer_pending(
        self, _sync_earnings, _sync_cash_flows, _sync_balance_sheets, _refresh_derived,
    ):
        claim_statement_refresh("PETR4")

        refresh_provider_data("PETR4")

        assert is_statement_refresh_pending("PETR4") is False

    @patch("quotes.tasks.refresh_derived_data")
    @patch("quotes.tasks.sync_balance_sheets")
    @patch("quotes.tasks.sync_cash_flows")
    @patch("quotes.tasks.sync_earnings", side_effect=ProviderError("provider down"))
    def test_a_refresh_the_provider_refused_still_closes(
        self, _sync_earnings, _sync_cash_flows, _sync_balance_sheets, _refresh_derived,
    ):
        """Otherwise the page would poll until the claim expired on its own."""
        claim_statement_refresh("PETR4")

        refresh_provider_data("PETR4")

        assert is_statement_refresh_pending("PETR4") is False
        assert claim_statement_refresh("PETR4") is False

    @patch("quotes.tasks.sync_balance_sheets")
    @patch("quotes.tasks.sync_cash_flows")
    @patch("quotes.tasks.sync_earnings")
    def test_the_caches_are_dropped_before_the_refresh_stops_being_pending(
        self, _sync_earnings, _sync_cash_flows, _sync_balance_sheets,
    ):
        """The page refetches the moment the refresh stops being pending. If
        the caches were dropped afterwards it would refetch the old payload."""
        claim_statement_refresh("PETR4")
        pending_when_caches_were_dropped = []

        def _drop_caches(ticker):
            pending_when_caches_were_dropped.append(is_statement_refresh_pending(ticker))

        with patch("quotes.tasks.refresh_derived_data", side_effect=_drop_caches):
            refresh_provider_data("PETR4")

        assert pending_when_caches_were_dropped == [True]


COMPANY_ENDPOINTS = (
    ("/api/quote/PETR4/", pe10_cache_key),
    ("/api/quote/PETR4/fundamentals/", fundamentals_cache_key),
    ("/api/quote/PETR4/multiples-history/", multiples_history_cache_key),
)


@pytest.mark.django_db
@pytest.mark.parametrize("path, cache_key_for", COMPANY_ENDPOINTS)
class TestCompanyPayloadsDuringARefresh:
    def test_a_stale_company_is_answered_and_flagged_as_refreshing(
        self, path, cache_key_for, api_client, stale_petr4_statements, provider_calls,
    ):
        response = api_client.get(path)

        assert response.status_code == 200
        assert response.json()["refreshPending"] is True
        provider_calls.delay.assert_called_once_with("PETR4")

    def test_a_payload_built_during_a_refresh_is_not_cached_anywhere(
        self, path, cache_key_for, api_client, stale_petr4_statements, provider_calls,
    ):
        """Neither on the server for a day, nor in the browser for five
        minutes: the refetch that follows the refresh has to reach fresh
        statements."""
        response = api_client.get(path)

        assert cache.get(cache_key_for("PETR4")) is None
        assert response["Cache-Control"] == "no-store"

    def test_a_fresh_company_is_not_flagged_and_stays_cacheable(
        self, path, cache_key_for, api_client, petr4_statements, provider_calls,
    ):
        response = api_client.get(path)

        assert response.status_code == 200
        assert response.json()["refreshPending"] is False
        assert response["Cache-Control"].startswith("public")
        assert cache.get(cache_key_for("PETR4")) is not None
        provider_calls.delay.assert_not_called()

    def test_the_flag_is_not_stored_with_the_cached_payload(
        self, path, cache_key_for, api_client, petr4_statements, provider_calls,
    ):
        """It describes this moment, not the payload."""
        api_client.get(path)

        assert "refreshPending" not in cache.get(cache_key_for("PETR4"))

    def test_a_cached_payload_is_flagged_while_a_refresh_is_in_flight(
        self, path, cache_key_for, api_client, petr4_statements, provider_calls,
    ):
        """One endpoint's cache can outlive another's, so a payload served
        from cache may still be about to be replaced."""
        api_client.get(path)
        claim_statement_refresh("PETR4")

        response = api_client.get(path)

        assert response.json()["refreshPending"] is True
        assert response["Cache-Control"] == "no-store"

    def test_once_the_refresh_lands_the_next_answer_is_cached_again(
        self, path, cache_key_for, api_client, stale_petr4_statements, provider_calls,
    ):
        api_client.get(path)
        record_statement_refresh_attempt("PETR4")

        response = api_client.get(path)

        assert response.json()["refreshPending"] is False
        assert cache.get(cache_key_for("PETR4")) is not None


@pytest.mark.django_db
class TestRefreshStatusEndpoint:
    def test_reports_nothing_pending_for_a_company_at_rest(self, api_client):
        response = api_client.get("/api/quote/PETR4/refresh-status/")

        assert response.status_code == 200
        assert response.json() == {"refreshPending": False}

    def test_reports_a_refresh_in_flight(self, api_client):
        claim_statement_refresh("PETR4")

        response = api_client.get("/api/quote/PETR4/refresh-status/")

        assert response.json() == {"refreshPending": True}

    def test_reports_the_refresh_as_over_once_the_task_has_run(self, api_client):
        claim_statement_refresh("PETR4")
        record_statement_refresh_attempt("PETR4")

        response = api_client.get("/api/quote/PETR4/refresh-status/")

        assert response.json() == {"refreshPending": False}

    def test_is_never_cached(self, api_client):
        response = api_client.get("/api/quote/PETR4/refresh-status/")

        assert response["Cache-Control"] == "no-store"

    def test_accepts_a_lowercase_ticker(self, api_client):
        claim_statement_refresh("PETR4")

        response = api_client.get("/api/quote/petr4/refresh-status/")

        assert response.json() == {"refreshPending": True}

    def test_refuses_a_symbol_that_cannot_be_a_company(self, api_client):
        response = api_client.get("/api/quote/$TFCO4/refresh-status/")

        assert response.status_code == 404

    def test_does_not_count_against_the_lookup_quota(self, api_client):
        """Polling a company the visitor is already looking at is not a new
        lookup, and the answer reveals nothing about the company."""
        from quotes.models import LookupLog

        api_client.get("/api/quote/PETR4/refresh-status/")

        assert LookupLog.objects.count() == 0
