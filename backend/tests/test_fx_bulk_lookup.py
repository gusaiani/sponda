"""Query-count tests for FX resolution across many dates.

Sentry flagged two endpoints as N+1s with an identical fingerprint,
``/api/quote/{ticker}/multiples-history/`` (WEB-DJANGO-1E, 680ms) and
``/api/quote/{ticker}/fundamentals/`` (WEB-DJANGO-1F, 1000ms). Both walk a
per-year loop calling ``get_fx_rate(date(year, 12, 31), ...)``, and each
call runs its own "latest rate on or before this date" query. A company
with thirty years of history therefore paid thirty round trips, doubled
for a cross-rate pair because that pivots through USD.

``get_fx_rates_for_dates`` answers the whole set of dates from one query
per non-USD leg. These tests pin both halves of that promise: the answers
stay identical to the single-date helper, and the cost stops scaling with
the number of dates.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from quotes.fx import get_fx_rate, get_fx_rates_for_dates
from quotes.models import FxRate


def _store_year_end_rates(quote_currency, first_year, last_year, starting_rate):
    """One USD -> quote_currency anchor per year end, drifting a little."""
    for offset, year in enumerate(range(first_year, last_year + 1)):
        FxRate.objects.create(
            date=date(year, 12, 31),
            base_currency="USD",
            quote_currency=quote_currency,
            rate=Decimal(starting_rate) + Decimal(offset),
        )


@pytest.mark.django_db
def test_bulk_lookup_matches_single_date_lookup():
    """The bulk resolver must agree with get_fx_rate, date for date."""
    _store_year_end_rates("BRL", 2000, 2024, "2.00")
    requested = [date(year, 12, 31) for year in range(2000, 2025)]

    bulk = get_fx_rates_for_dates(requested, "USD", "BRL")

    for on_date in requested:
        assert bulk[on_date] == get_fx_rate(on_date, "USD", "BRL")


@pytest.mark.django_db
def test_bulk_lookup_cost_does_not_grow_with_the_number_of_dates():
    """Twenty-five year ends must cost the same as two."""
    _store_year_end_rates("BRL", 2000, 2024, "2.00")

    with CaptureQueriesContext(connection) as few:
        get_fx_rates_for_dates(
            [date(2023, 12, 31), date(2024, 12, 31)], "USD", "BRL",
        )
    with CaptureQueriesContext(connection) as many:
        get_fx_rates_for_dates(
            [date(year, 12, 31) for year in range(2000, 2025)], "USD", "BRL",
        )

    assert len(many) == len(few), (
        f"FX lookup scales with the date count: {len(few)} queries for 2 "
        f"dates, {len(many)} for 25."
    )


@pytest.mark.django_db
def test_cross_rate_pivots_through_usd_in_a_bounded_number_of_queries():
    """A non-USD pair reads both legs, and still only once each."""
    _store_year_end_rates("BRL", 2015, 2024, "3.00")
    _store_year_end_rates("DKK", 2015, 2024, "6.00")
    requested = [date(year, 12, 31) for year in range(2015, 2025)]

    with CaptureQueriesContext(connection) as captured:
        bulk = get_fx_rates_for_dates(requested, "BRL", "DKK")

    assert len(captured) <= 2, f"expected one query per leg, got {len(captured)}"
    for on_date in requested:
        assert bulk[on_date] == get_fx_rate(on_date, "BRL", "DKK")


@pytest.mark.django_db
def test_identical_currencies_need_no_query_at_all():
    requested = [date(2024, 12, 31), date(2023, 12, 31)]

    with CaptureQueriesContext(connection) as captured:
        bulk = get_fx_rates_for_dates(requested, "USD", "USD")

    assert len(captured) == 0
    assert all(rate == Decimal("1") for rate in bulk.values())


@pytest.mark.django_db
def test_dates_before_the_oldest_anchor_resolve_to_none():
    """Same degradation contract as get_fx_rate: no anchor means None."""
    _store_year_end_rates("BRL", 2020, 2024, "5.00")
    requested = [date(2010, 12, 31), date(2024, 12, 31)]

    bulk = get_fx_rates_for_dates(requested, "USD", "BRL")

    assert bulk[date(2010, 12, 31)] is None
    assert bulk[date(2024, 12, 31)] == get_fx_rate(date(2024, 12, 31), "USD", "BRL")


@pytest.mark.django_db
def test_lookup_uses_the_latest_anchor_on_or_before_the_date():
    """Weekend and holiday dates fall back to the previous stored day."""
    FxRate.objects.create(
        date=date(2024, 12, 27), base_currency="USD",
        quote_currency="BRL", rate=Decimal("6.00"),
    )
    requested = [date(2024, 12, 31)]

    bulk = get_fx_rates_for_dates(requested, "USD", "BRL")

    assert bulk[date(2024, 12, 31)] == Decimal("6.00")


@pytest.mark.django_db
def test_empty_date_list_is_answered_without_touching_the_database():
    with CaptureQueriesContext(connection) as captured:
        assert get_fx_rates_for_dates([], "USD", "BRL") == {}
    assert len(captured) == 0
