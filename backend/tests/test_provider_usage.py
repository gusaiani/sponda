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

from quotes.models import ProviderUsageDay
from quotes.provider_usage import record_provider_call

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
            "quotes.provider_usage.ProviderUsageDay.objects"
        ) as mock_manager:
            mock_manager.filter.side_effect = RuntimeError("database is down")
            record_provider_call("fmp", "/stable/quote", response_bytes=440)


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
