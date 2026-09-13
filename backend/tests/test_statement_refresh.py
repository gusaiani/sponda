"""Tests for choosing which companies need their statements refetched.

The weekly job used to refetch all three statements for all 18,158 tickers,
7.3 GB a run, to discover that almost none of them had filed anything. A
company files four times a year and FMP publishes an earnings calendar, so
the question "who could plausibly have something new" is answerable in one
call instead of 54,000.
"""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from quotes.models import QuarterlyEarnings
from quotes.statement_refresh import (
    LONG_OVERDUE_DAYS,
    RETRY_OVERDUE_AFTER_DAYS,
    symbols_needing_statement_refresh,
)

pytestmark = pytest.mark.django_db


def store_earnings(symbol: str, quarter_end: date, fetched_days_ago: int = 0) -> None:
    QuarterlyEarnings.objects.create(
        ticker=symbol, end_date=quarter_end, net_income=1_000_000
    )
    QuarterlyEarnings.objects.filter(ticker=symbol).update(
        fetched_at=timezone.now() - timedelta(days=fetched_days_ago)
    )


class TestCompaniesThatReported:
    def test_a_company_on_the_earnings_calendar_is_refreshed(self):
        store_earnings("AAPL", date.today() - timedelta(days=30))

        needing = symbols_needing_statement_refresh(
            ["AAPL"], recent_reporters={"AAPL"}
        )

        assert needing == {"AAPL"}

    def test_a_company_that_did_not_report_is_left_alone(self):
        store_earnings("AAPL", date.today() - timedelta(days=30))

        needing = symbols_needing_statement_refresh(
            ["AAPL"], recent_reporters={"MSFT"}
        )

        assert needing == set()


class TestCompaniesWithNothingStored:
    def test_a_company_with_no_statements_is_always_refreshed(self):
        needing = symbols_needing_statement_refresh(["NEWCO"], recent_reporters=set())

        assert needing == {"NEWCO"}


class TestTheSafetyNet:
    """The calendar does not cover everything · thinly traded foreign issuers
    in particular · so a company whose newest quarter has gone stale is
    retried on a slow cadence rather than never."""

    def test_a_long_overdue_company_is_retried(self):
        store_earnings(
            "OTCXX",
            date.today() - timedelta(days=LONG_OVERDUE_DAYS + 10),
            fetched_days_ago=RETRY_OVERDUE_AFTER_DAYS + 1,
        )

        needing = symbols_needing_statement_refresh(["OTCXX"], recent_reporters=set())

        assert needing == {"OTCXX"}

    def test_a_long_overdue_company_retried_recently_waits(self):
        store_earnings(
            "OTCXX",
            date.today() - timedelta(days=LONG_OVERDUE_DAYS + 10),
            fetched_days_ago=1,
        )

        needing = symbols_needing_statement_refresh(["OTCXX"], recent_reporters=set())

        assert needing == set()

    def test_a_company_inside_its_reporting_cycle_is_not_retried(self):
        store_earnings(
            "AAPL", date.today() - timedelta(days=40), fetched_days_ago=365
        )

        needing = symbols_needing_statement_refresh(["AAPL"], recent_reporters=set())

        assert needing == set()


class TestBrazilianTickers:
    """B3 statements come from BRAPI and CVM, not from FMP, so they are
    neither on FMP's calendar nor charged to its quota. There are a few
    hundred of them and they keep the old cadence."""

    def test_brazilian_tickers_are_always_refreshed(self):
        store_earnings("PETR4", date.today() - timedelta(days=30))

        needing = symbols_needing_statement_refresh(
            ["PETR4"], recent_reporters=set()
        )

        assert needing == {"PETR4"}


class TestSelectionIsOneQuery:
    def test_thousands_of_symbols_cost_a_constant_number_of_queries(
        self, django_assert_num_queries
    ):
        for index in range(20):
            store_earnings(f"SYM{index}", date.today() - timedelta(days=30))

        with django_assert_num_queries(1):
            symbols_needing_statement_refresh(
                [f"SYM{index}" for index in range(20)], recent_reporters=set()
            )
