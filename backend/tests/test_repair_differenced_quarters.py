"""The repair for quarters already stored differenced.

The ingestion guard stops new ones arriving. These are the rows written
before it existed: 2025 and 2026 for every Brazilian company BRAPI serves.
"""
from datetime import date
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.brapi import BRAPIError, IncomeStatements
from quotes.models import SOURCE_BRAPI, SOURCE_FMP, QuarterlyEarnings

COMMAND = "repair_differenced_quarters"
FETCH = f"quotes.management.commands.{COMMAND}.fetch_income_statements"

KEPLER_STORED = {
    date(2025, 3, 31): (357_230_020, 25_552_000),
    date(2025, 6, 30): (-46_157_000, -11_156_000),
    date(2025, 9, 30): (112_262_000, 37_174_000),
    date(2025, 12, 31): (398_662_020, 64_752_000),
    date(2026, 3, 31): (318_059_000, 17_128_000),
    date(2026, 6, 30): (-18_988_000, -10_810_000),
}

KEPLER_ANNUALS = IncomeStatements(quarterly=[], annual=[
    {"endDate": "2025-12-31", "totalRevenue": 1_490_300_000, "netIncome": 156_270_000},
])

EMBRAER_STORED = {
    date(2025, 3, 31): (6_405_270_000, 470_895_000),
    date(2025, 6, 30): (10_270_363_000, 397_477_000),
    date(2025, 9, 30): (10_866_683_000, 688_122_000),
    date(2025, 12, 31): (14_340_918_000, 435_543_000),
}

EMBRAER_ANNUALS = IncomeStatements(quarterly=[], annual=[
    {"endDate": "2025-12-31", "totalRevenue": 41_883_234_000, "netIncome": 1_992_037_000},
])


def _store(ticker, rows, source=SOURCE_BRAPI):
    for end_date, (revenue, net_income) in rows.items():
        QuarterlyEarnings.objects.create(
            ticker=ticker, end_date=end_date,
            revenue=revenue, net_income=net_income, source=source,
        )


def _run(**options) -> str:
    out = StringIO()
    call_command(COMMAND, stdout=out, stderr=out, pause=0, **options)
    return out.getvalue()


def _revenue(ticker, end_date):
    return QuarterlyEarnings.objects.get(ticker=ticker, end_date=end_date).revenue


@pytest.mark.django_db
class TestRepairsWhatTheAnnualCondemns:
    def test_restates_the_differenced_quarters(self):
        _store("KEPL3", KEPLER_STORED)
        with patch(FETCH, return_value=KEPLER_ANNUALS):
            _run()

        assert _revenue("KEPL3", date(2025, 6, 30)) == 311_073_020
        assert _revenue("KEPL3", date(2025, 9, 30)) == 423_335_020

    def test_repaired_year_ties_to_the_audited_annual(self):
        _store("KEPL3", KEPLER_STORED)
        with patch(FETCH, return_value=KEPLER_ANNUALS):
            _run()

        year = QuarterlyEarnings.objects.filter(ticker="KEPL3", end_date__year=2025)
        assert sum(row.net_income for row in year) == 156_270_000

    def test_repairs_the_year_still_in_progress(self):
        _store("KEPL3", KEPLER_STORED)
        with patch(FETCH, return_value=KEPLER_ANNUALS):
            _run()

        assert _revenue("KEPL3", date(2026, 6, 30)) == 299_071_000

    def test_leaves_a_healthy_company_untouched(self):
        _store("EMBR3", EMBRAER_STORED)
        with patch(FETCH, return_value=EMBRAER_ANNUALS):
            _run()

        assert _revenue("EMBR3", date(2025, 6, 30)) == 10_270_363_000

    def test_is_safe_to_run_twice(self):
        """A repaired year now ties as filed, so the second pass finds nothing.

        Idempotence is not a nicety here: a second restatement would
        accumulate the already-accumulated quarters and inflate the year.
        """
        _store("KEPL3", KEPLER_STORED)
        with patch(FETCH, return_value=KEPLER_ANNUALS):
            _run()
            _run()

        assert _revenue("KEPL3", date(2025, 6, 30)) == 311_073_020
        assert _revenue("KEPL3", date(2026, 6, 30)) == 299_071_000

    def test_dry_run_writes_nothing(self):
        _store("KEPL3", KEPLER_STORED)
        with patch(FETCH, return_value=KEPLER_ANNUALS):
            output = _run(dry_run=True)

        assert _revenue("KEPL3", date(2025, 6, 30)) == -46_157_000
        assert "nothing written" in output

    def test_reports_the_quarters_it_changed(self):
        _store("KEPL3", KEPLER_STORED)
        with patch(FETCH, return_value=KEPLER_ANNUALS):
            output = _run()

        assert "KEPL3" in output
        assert "3 quarters" in output


@pytest.mark.django_db
class TestQueue:
    def test_leaves_other_providers_alone(self):
        """FMP has its own defects and none of them are this one."""
        _store("AAPL", KEPLER_STORED, source=SOURCE_FMP)
        with patch(FETCH, return_value=KEPLER_ANNUALS) as fetch:
            _run()

        assert fetch.call_count == 0
        assert _revenue("AAPL", date(2025, 6, 30)) == -46_157_000

    def test_asks_the_provider_once_per_company_not_once_per_quarter(self):
        """QuarterlyEarnings carries a Meta ordering, and Django folds the
        ordering column into a DISTINCT, so the obvious query returns a
        company once per quarter it has. One BRAPI call each makes that the
        difference between 363 calls and several thousand."""
        _store("KEPL3", KEPLER_STORED)
        with patch(FETCH, return_value=KEPLER_ANNUALS) as fetch:
            output = _run()

        assert fetch.call_count == 1
        assert output.startswith("1 companies this run")

    def test_repairs_a_single_company_on_request(self):
        _store("KEPL3", KEPLER_STORED)
        _store("EMBR3", EMBRAER_STORED)
        with patch(FETCH, return_value=KEPLER_ANNUALS) as fetch:
            _run(ticker="KEPL3")

        assert fetch.call_count == 1

    def test_limit_takes_a_tranche_and_reports_the_cursor(self):
        _store("AAAA3", EMBRAER_STORED)
        _store("BBBB3", EMBRAER_STORED)
        with patch(FETCH, return_value=EMBRAER_ANNUALS) as fetch:
            output = _run(limit=1)

        assert fetch.call_count == 1
        assert "--after AAAA3" in output

    def test_after_resumes_past_the_cursor(self):
        _store("AAAA3", EMBRAER_STORED)
        _store("BBBB3", EMBRAER_STORED)
        with patch(FETCH, return_value=EMBRAER_ANNUALS) as fetch:
            _run(after="AAAA3")

        assert fetch.call_count == 1


@pytest.mark.django_db
class TestProviderOutage:
    def test_stops_rather_than_stepping_the_cursor_past_unreached_companies(self):
        """The lesson of the fiscal-year backfill, which wrote off 1,611.

        A provider that cannot answer says nothing about the company, so a
        run that cannot reach it must leave it queued rather than record it
        as examined and move the cursor on.
        """
        _store("AAAA3", KEPLER_STORED)
        _store("BBBB3", KEPLER_STORED)

        responses = [KEPLER_ANNUALS] + [BRAPIError("circuit open")] * 8

        def _flaky(ticker):
            outcome = responses.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch(FETCH, side_effect=_flaky), patch(
            f"quotes.management.commands.{COMMAND}.time.sleep",
        ):
            output = _run()

        assert "stopped" in output
        assert "--after AAAA3" in output
        assert _revenue("BBBB3", date(2025, 6, 30)) == -46_157_000

    def test_waits_out_a_refusal_rather_than_losing_the_company(self):
        _store("KEPL3", KEPLER_STORED)
        responses = [BRAPIError("circuit open"), KEPLER_ANNUALS]

        def _flaky(ticker):
            outcome = responses.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch(FETCH, side_effect=_flaky), patch(
            f"quotes.management.commands.{COMMAND}.time.sleep",
        ):
            _run()

        assert _revenue("KEPL3", date(2025, 6, 30)) == 311_073_020
