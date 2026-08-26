"""Query-count regression test for multiples history FX translation.

WEB-DJANGO-1E: ``/api/quote/{ticker}/multiples-history/`` took 680ms and
Sentry attributed it to a repeated "latest FX rate on or before this date"
query. The per-year translation asked for its rate one year at a time, and
did it twice over, once in the P/L10 loop and again in the P/FCL10 loop.

A company with three decades of price history should not cost more FX
queries than one with three years.
"""
from __future__ import annotations

import calendar
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from quotes.models import FxRate, QuarterlyEarnings, Ticker
from quotes.multiples_history import compute_multiples_history


def _monthly_prices(years):
    """One price point per month for every year in ``years``."""
    points = []
    for year in years:
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            moment = datetime(year, month, last_day, tzinfo=timezone.utc)
            points.append(
                {"date": int(moment.timestamp()), "adjustedClose": 100.0},
            )
    return points


def _seed_cross_currency_ticker(years):
    """A USD-listed, DKK-reporting company with earnings and FX for each year."""
    Ticker.objects.create(
        symbol="NVO", name="Novo Nordisk", reported_currency="DKK",
    )
    for year in years:
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date_type(year, 12, 31), rate=Decimal("7.00"),
        )
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="NVO", end_date=date_type(year, month, day),
                net_income=25_000_000_000,
            )


def _count_queries_for(years):
    with CaptureQueriesContext(connection) as captured:
        result = compute_multiples_history(
            "NVO", _monthly_prices(years),
            market_cap=1_950_000_000.0, current_price=120.0,
        )
    return len(captured), result


@pytest.mark.django_db
def test_fx_translation_cost_is_flat_in_the_number_of_years():
    short_span = list(range(2022, 2025))
    _seed_cross_currency_ticker(short_span)
    short_count, _ = _count_queries_for(short_span)

    long_span = list(range(1995, 2025))
    _seed_cross_currency_ticker_extra_years(long_span, short_span)
    long_count, result = _count_queries_for(long_span)

    assert len(result["multiples"]["pl"]) == len(long_span)
    assert long_count == short_count, (
        f"multiples history scales with year count: {short_count} queries "
        f"for {len(short_span)} years, {long_count} for {len(long_span)}."
    )


def _seed_cross_currency_ticker_extra_years(all_years, already_seeded):
    """Top up FX and earnings for the years the short span did not cover."""
    for year in all_years:
        if year in already_seeded:
            continue
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date_type(year, 12, 31), rate=Decimal("7.00"),
        )
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="NVO", end_date=date_type(year, month, day),
                net_income=25_000_000_000,
            )


@pytest.mark.django_db
def test_translated_multiples_are_unchanged_by_the_bulk_lookup():
    """Cheaper must not mean different: pin the actual translated value."""
    years = [2023, 2024, 2025]
    Ticker.objects.create(
        symbol="NVO", name="Novo Nordisk", reported_currency="DKK",
    )
    for fx_date, rate in [
        (date_type(2023, 12, 29), Decimal("6.80")),
        (date_type(2024, 12, 31), Decimal("7.10")),
        (date_type(2025, 12, 31), Decimal("6.85")),
    ]:
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK", date=fx_date, rate=rate,
        )
    for year in years:
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker="NVO", end_date=date_type(year, month, day),
                net_income=25_000_000_000,
            )

    prices = []
    for year, price in [(2023, 100.0), (2024, 110.0), (2025, 120.0)]:
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            moment = datetime(year, month, last_day, tzinfo=timezone.utc)
            prices.append(
                {"date": int(moment.timestamp()), "adjustedClose": price},
            )

    result = compute_multiples_history(
        "NVO", prices, market_cap=1_950_000_000.0, current_price=120.0,
    )

    pl_2025 = next(p for p in result["multiples"]["pl"] if p["year"] == 2025)
    assert pl_2025["value"] is not None
    assert 0.10 < pl_2025["value"] < 0.20
    assert result["currency_warning"] is False
