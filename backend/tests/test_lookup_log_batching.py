"""The batch endpoint must log its lookups in one INSERT, not one each.

Sentry reported `/api/quotes/batch/` as an N+1 on
`INSERT INTO "quotes_lookuplog"`. The view logged a lookup per ticker in
a Python loop, so a full batch of 100 symbols meant 100 round trips to
Postgres after the fan-out had already finished, on the request's
critical path and for rows nothing reads until the next quota check.

Unlike the other N+1s in this area, this one really is a database query:
the rate-limiter and circuit-breaker reports were Redis spans that Sentry
files under the same heading.
"""
import json
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import Client

from quotes.models import LookupLog, Ticker

TICKERS = ["PETR4", "VALE3", "ITUB4", "BBAS3", "WEGE3"]


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def catalogue(db):
    for symbol in TICKERS:
        Ticker.objects.create(
            symbol=symbol, name=f"{symbol} SA", sector="Oil",
            market_cap=1_000_000, country="BR",
        )


def lookuplog_inserts(captured):
    return [
        query for query in captured.captured_queries
        if 'INSERT INTO "quotes_lookuplog"' in query["sql"]
    ]


@pytest.mark.django_db(transaction=True)
class TestBatchLookupLogging:
    def _post(self, api_client):
        return api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": TICKERS}),
            content_type="application/json",
        )

    @patch("quotes.views._compute_quote_payload")
    def test_every_ticker_is_logged_in_a_single_insert(
        self, mock_payload, api_client, catalogue
    ):
        mock_payload.return_value = {"price": 10, "pe10": 5}

        with CaptureQueriesContext(connection) as captured:
            response = self._post(api_client)

        assert response.status_code == 200
        assert len(lookuplog_inserts(captured)) == 1

    @patch("quotes.views._compute_quote_payload")
    def test_one_row_lands_per_ticker(self, mock_payload, api_client, catalogue):
        mock_payload.return_value = {"price": 10, "pe10": 5}

        self._post(api_client)

        assert sorted(LookupLog.objects.values_list("ticker", flat=True)) == sorted(
            TICKERS
        )

    @patch("quotes.views._compute_quote_payload")
    def test_a_ticker_that_failed_is_not_logged(
        self, mock_payload, api_client, catalogue
    ):
        """Only a lookup that actually produced a quote counts against the
        cap, which is what the per-ticker loop used to express."""
        def payload_for(ticker, request=None):
            if ticker == "VALE3":
                raise RuntimeError("provider is down")
            return {"price": 10, "pe10": 5}

        mock_payload.side_effect = payload_for

        self._post(api_client)

        logged = set(LookupLog.objects.values_list("ticker", flat=True))
        assert "VALE3" not in logged
        assert logged == set(TICKERS) - {"VALE3"}

    @patch("quotes.views._compute_quote_payload")
    def test_nothing_is_written_when_no_ticker_produced_a_quote(
        self, mock_payload, api_client, catalogue
    ):
        """An empty bulk_create is still a round trip worth not making."""
        mock_payload.side_effect = RuntimeError("provider is down")

        with CaptureQueriesContext(connection) as captured:
            self._post(api_client)

        assert LookupLog.objects.count() == 0
        assert lookuplog_inserts(captured) == []


@pytest.mark.django_db(transaction=True)
class TestBatchLookupsCountTowardTheCap:
    """The batch endpoint must attribute a lookup the way every other
    ticker endpoint does.

    `quotes.lookup_quota` scopes an anonymous caller by `ip_hash` alone,
    so rows written with only a `session_key` are invisible to it. The
    batch view wrote exactly those, which left a client able to POST 100
    symbols at a time and never trip the daily cap that
    `LookupQuotaEnforcedView` exists to enforce on the single-company
    endpoints.

    Nothing in the UI reaches this path anonymously: the home page only
    batches a signed-in visitor's favourites and saved lists, and the
    quota scopes a signed-in caller by user. The hole was the endpoint
    being POSTed to directly.
    """

    ANONYMOUS_IP = "203.0.113.7"

    def _post(self, api_client, tickers=TICKERS):
        return api_client.post(
            "/api/quotes/batch/",
            data=json.dumps({"tickers": tickers}),
            content_type="application/json",
            REMOTE_ADDR=self.ANONYMOUS_IP,
        )

    @patch("quotes.views._compute_quote_payload")
    def test_an_anonymous_lookup_records_the_client_ip(
        self, mock_payload, api_client, catalogue
    ):
        mock_payload.return_value = {"price": 10, "pe10": 5}

        self._post(api_client)

        assert LookupLog.objects.filter(ip_hash="").count() == 0
        assert LookupLog.objects.filter(ip_hash__isnull=True).count() == 0

    @patch("quotes.views._compute_quote_payload")
    def test_the_ip_matches_what_a_single_company_lookup_records(
        self, mock_payload, api_client, catalogue
    ):
        """Both paths must hash the same request the same way, or the cap
        counts a batch lookup and a page view as different people."""
        from django.test import RequestFactory

        from quotes.client_ip import client_ip_hash

        mock_payload.return_value = {"price": 10, "pe10": 5}
        expected = client_ip_hash(
            RequestFactory().get("/", REMOTE_ADDR=self.ANONYMOUS_IP)
        )

        self._post(api_client)

        assert set(LookupLog.objects.values_list("ip_hash", flat=True)) == {expected}

    @patch("quotes.views._compute_quote_payload")
    def test_the_rows_count_against_the_anonymous_daily_quota(
        self, mock_payload, api_client, catalogue
    ):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser

        from quotes.lookup_quota import lookup_quota

        mock_payload.return_value = {"price": 10, "pe10": 5}

        self._post(api_client)

        request = RequestFactory().get("/", REMOTE_ADDR=self.ANONYMOUS_IP)
        request.user = AnonymousUser()
        assert lookup_quota(request)["used"] == len(TICKERS)

    @patch("quotes.views._compute_quote_payload")
    def test_a_signed_in_lookup_is_attributed_to_the_user_not_the_ip(
        self, mock_payload, api_client, catalogue, django_user_model
    ):
        mock_payload.return_value = {"price": 10, "pe10": 5}
        user = django_user_model.objects.create_user(
            username="reader", email="reader@example.com", password="x"
        )
        api_client.force_login(user)

        self._post(api_client)

        rows = LookupLog.objects.all()
        assert rows.count() == len(TICKERS)
        assert all(row.user_id == user.id for row in rows)

    @patch("quotes.views._compute_quote_payload")
    def test_it_is_still_one_insert(self, mock_payload, api_client, catalogue):
        """Attribution must not cost back the round trips just saved."""
        mock_payload.return_value = {"price": 10, "pe10": 5}

        with CaptureQueriesContext(connection) as captured:
            self._post(api_client)

        assert len(lookuplog_inserts(captured)) == 1
