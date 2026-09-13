"""Tests for pruning stored price history nobody reads.

A full daily series back to 2000 is about 0.6 MB of rows per company. The
store fills lazily, so it only ever holds companies someone asked for, but
"someone asked once, a year ago" still costs disk on a 49 GB droplet.
Companies nobody has looked at in months are dropped; the next visitor
refetches the series.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from quotes.models import DailyClosePrice, LookupLog

pytestmark = pytest.mark.django_db


def store_series(ticker: str) -> None:
    DailyClosePrice.objects.create(
        ticker=ticker, date=date(2020, 1, 2), close=Decimal("100")
    )


def log_lookup(ticker: str, days_ago: int) -> None:
    entry = LookupLog.objects.create(ticker=ticker, ip_hash="ip-a")
    LookupLog.objects.filter(pk=entry.pk).update(
        timestamp=timezone.now() - timedelta(days=days_ago)
    )


class TestPruneDailyPrices:
    def test_drops_series_for_companies_nobody_looked_at(self):
        store_series("STALE")
        log_lookup("STALE", days_ago=200)

        call_command("prune_daily_prices", "--days", "90", stdout=StringIO())

        assert not DailyClosePrice.objects.filter(ticker="STALE").exists()

    def test_keeps_series_for_companies_still_being_read(self):
        store_series("POPULAR")
        log_lookup("POPULAR", days_ago=3)

        call_command("prune_daily_prices", "--days", "90", stdout=StringIO())

        assert DailyClosePrice.objects.filter(ticker="POPULAR").exists()

    def test_a_company_with_no_lookups_at_all_is_pruned(self):
        store_series("ORPHAN")

        call_command("prune_daily_prices", "--days", "90", stdout=StringIO())

        assert not DailyClosePrice.objects.filter(ticker="ORPHAN").exists()

    def test_dry_run_reports_without_deleting(self):
        store_series("STALE")
        output = StringIO()

        call_command("prune_daily_prices", "--days", "90", "--dry-run", stdout=output)

        assert DailyClosePrice.objects.filter(ticker="STALE").exists()
        assert "STALE" in output.getvalue() or "1" in output.getvalue()
