"""Tests for per-endpoint provider usage accounting.

FMP bills on a rolling 30-day data volume and mails a warning at 90%. That
mail is the first signal today, and it does not say which endpoint spent
the quota. Every outbound call records its endpoint and response size, so
the answer is a query rather than an afternoon of log archaeology.
"""
from datetime import date, timedelta
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from config.middleware.provider_usage_batch import ProviderUsageBatchMiddleware
from quotes.models import ProviderUsageDay
from quotes.provider_usage import batched_provider_usage, record_provider_call

pytestmark = pytest.mark.django_db


class TestRecordProviderCall:
    def test_first_call_creates_todays_row(self):
        record_provider_call("fmp", "/stable/quote", response_bytes=440)

        usage = ProviderUsageDay.objects.get()
        assert usage.provider == "fmp"
        assert usage.endpoint == "/stable/quote"
        assert usage.call_count == 1
        assert usage.bytes_downloaded == 440
        assert usage.date == date.today()

    def test_later_calls_increment_the_same_row(self):
        record_provider_call("fmp", "/stable/quote", response_bytes=440)
        record_provider_call("fmp", "/stable/quote", response_bytes=60)

        usage = ProviderUsageDay.objects.get()
        assert usage.call_count == 2
        assert usage.bytes_downloaded == 500

    def test_each_endpoint_is_counted_separately(self):
        record_provider_call("fmp", "/stable/quote", response_bytes=440)
        record_provider_call("fmp", "/stable/income-statement", response_bytes=110_000)

        assert ProviderUsageDay.objects.count() == 2
        quote_usage = ProviderUsageDay.objects.get(endpoint="/stable/quote")
        assert quote_usage.bytes_downloaded == 440

    def test_accounting_never_breaks_the_caller(self):
        """A metering failure must not take down a working data fetch."""
        with patch(
            "quotes.provider_usage._write_usage",
            side_effect=RuntimeError("database is down"),
        ):
            record_provider_call("fmp", "/stable/quote", response_bytes=440)


    def test_a_call_outside_a_batch_is_one_statement(self):
        """Insert-or-increment in one round trip, which also closes the
        race two processes had over creating the same row."""
        record_provider_call("fmp", "/stable/quote", response_bytes=10)

        with CaptureQueriesContext(connection) as queries:
            record_provider_call("fmp", "/stable/quote", response_bytes=10)
            record_provider_call("fmp", "/stable/profile", response_bytes=10)

        assert len(queries) == 2


class TestBatchedProviderUsage:
    """One write per request instead of one per outbound call.

    Sentry filed `UPDATE quotes_providerusageday` as an N+1 on
    `/api/quote/{ticker}/`, `/fundamentals/` and `/multiples-history/`: a
    cold page makes one FMP call per statement, and each call wrote its
    own row. Inside a batch the calls are summed in memory and written in
    a single statement when the block ends, however it ends.
    """

    def test_calls_in_a_batch_are_written_in_one_statement(self):
        with CaptureQueriesContext(connection) as queries:
            with batched_provider_usage():
                record_provider_call("fmp", "/stable/income-statement", response_bytes=100)
                record_provider_call("fmp", "/stable/cash-flow-statement", response_bytes=200)
                record_provider_call("fmp", "/stable/balance-sheet-statement", response_bytes=300)
                assert ProviderUsageDay.objects.count() == 0

        writes = [q for q in queries if "providerusageday" in q["sql"].lower()
                  and not q["sql"].lstrip().upper().startswith("SELECT")]
        assert len(writes) == 1
        assert {
            usage.endpoint: (usage.call_count, usage.bytes_downloaded)
            for usage in ProviderUsageDay.objects.all()
        } == {
            "/stable/income-statement": (1, 100),
            "/stable/cash-flow-statement": (1, 200),
            "/stable/balance-sheet-statement": (1, 300),
        }

    def test_repeated_calls_to_one_endpoint_are_summed(self):
        with batched_provider_usage():
            record_provider_call("fmp", "/stable/quote", response_bytes=40)
            record_provider_call("fmp", "/stable/quote", response_bytes=60)

        usage = ProviderUsageDay.objects.get()
        assert (usage.call_count, usage.bytes_downloaded) == (2, 100)

    def test_a_batch_adds_to_what_today_already_counted(self):
        record_provider_call("fmp", "/stable/quote", response_bytes=40)

        with batched_provider_usage():
            record_provider_call("fmp", "/stable/quote", response_bytes=60)

        usage = ProviderUsageDay.objects.get()
        assert (usage.call_count, usage.bytes_downloaded) == (2, 100)

    @pytest.mark.parametrize("abort", [RuntimeError("view crashed"), SystemExit(1)])
    def test_the_batch_is_written_however_the_block_ends(self, abort):
        """SystemExit is what gunicorn raises in a worker it times out."""
        with pytest.raises(type(abort)):
            with batched_provider_usage():
                record_provider_call("fmp", "/stable/quote", response_bytes=40)
                raise abort

        assert ProviderUsageDay.objects.get().call_count == 1

    def test_a_failed_write_never_breaks_the_caller(self):
        with patch(
            "quotes.provider_usage._write_usage",
            side_effect=RuntimeError("database is down"),
        ):
            with batched_provider_usage():
                record_provider_call("fmp", "/stable/quote", response_bytes=40)

    def test_an_empty_batch_writes_nothing(self):
        with CaptureQueriesContext(connection) as queries:
            with batched_provider_usage():
                pass

        assert len(queries) == 0


class TestProviderUsageBatchMiddleware:
    def test_a_request_writes_its_calls_once(self):
        def view(request):
            record_provider_call("fmp", "/stable/income-statement", response_bytes=100)
            record_provider_call("fmp", "/stable/cash-flow-statement", response_bytes=200)
            assert ProviderUsageDay.objects.count() == 0
            return "response"

        response = ProviderUsageBatchMiddleware(view)(request=Mock())

        assert response == "response"
        assert ProviderUsageDay.objects.count() == 2

    def test_is_installed(self, settings):
        assert (
            "config.middleware.provider_usage_batch.ProviderUsageBatchMiddleware"
            in settings.MIDDLEWARE
        )


class TestFMPClientRecordsUsage:
    @patch("quotes.fmp.requests.get")
    def test_get_records_the_endpoint_and_response_size(self, mock_requests_get):
        response = Mock(status_code=200, content=b'[{"symbol": "AAPL"}]')
        response.json.return_value = [{"symbol": "AAPL"}]
        mock_requests_get.return_value = response

        from quotes.fmp import _get

        _get("/stable/quote", params={"symbol": "AAPL"})

        usage = ProviderUsageDay.objects.get()
        assert usage.provider == "fmp"
        assert usage.endpoint == "/stable/quote"
        assert usage.call_count == 1
        assert usage.bytes_downloaded == len(b'[{"symbol": "AAPL"}]')

    @patch("quotes.fmp.requests.get")
    def test_a_rejected_call_is_still_counted(self, mock_requests_get):
        """A 429 spends the allowance too, so it has to show up in the report."""
        response = Mock(status_code=429, content=b"Limit Reach")
        response.text = "Limit Reach"
        mock_requests_get.return_value = response

        from quotes.fmp import FMPError, _get

        with pytest.raises(FMPError):
            _get("/stable/quote", params={"symbol": "AAPL"})

        usage = ProviderUsageDay.objects.get()
        assert usage.call_count == 1


class TestReportProviderUsageCommand:
    def test_reports_bytes_and_calls_per_endpoint(self):
        record_provider_call("fmp", "/stable/historical-price-eod/light", response_bytes=500_000)
        record_provider_call("fmp", "/stable/quote", response_bytes=440)

        output = StringIO()
        call_command("report_provider_usage", stdout=output)
        report = output.getvalue()

        assert "/stable/historical-price-eod/light" in report
        assert "/stable/quote" in report
        assert "500,440" in report.replace(" ", "") or "500440" in report.replace(",", "")

    def test_ignores_days_outside_the_window(self):
        ProviderUsageDay.objects.create(
            provider="fmp",
            date=date.today() - timedelta(days=45),
            endpoint="/stable/ancient",
            call_count=1,
            bytes_downloaded=999,
        )
        record_provider_call("fmp", "/stable/quote", response_bytes=440)

        output = StringIO()
        call_command("report_provider_usage", "--days", "30", stdout=output)
        report = output.getvalue()

        assert "/stable/ancient" not in report
        assert "/stable/quote" in report
