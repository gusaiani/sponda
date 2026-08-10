"""Tests for derived_data — keeping caches and snapshots in step with writes.

A statement write is only half the job: the Fundamentos payload, the PE10
payload and the multiples history are all cached for 24h, and the screener
reads a precomputed IndicatorSnapshot. Without this module a correct write
stays invisible for a day.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.cache import cache

from quotes.derived_data import (
    STATEMENT_DERIVED_CACHE_CONTROL,
    STATEMENT_DERIVED_CLIENT_CACHE_TTL,
    fundamentals_cache_key,
    invalidate_statement_caches,
    multiples_history_cache_key,
    pe10_cache_key,
    recompute_indicator_snapshot,
    refresh_derived_data,
    statement_derived_cache_keys,
)
from quotes.models import (
    BalanceSheet,
    IndicatorSnapshot,
    IPCAIndex,
    QuarterlyCashFlow,
    QuarterlyEarnings,
    Ticker,
)

TICKER = "GGBR3"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def ipca_zero(db):
    for year in range(2010, 2027):
        IPCAIndex.objects.update_or_create(
            date=date(year, 12, 31), defaults={"annual_rate": Decimal("0")},
        )


def seed_ten_years(ticker, net_income, free_cash_flow):
    for year in range(2016, 2026):
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            QuarterlyEarnings.objects.create(
                ticker=ticker, end_date=date(year, month, day),
                net_income=net_income, revenue=net_income * 10,
            )
            QuarterlyCashFlow.objects.create(
                ticker=ticker, end_date=date(year, month, day),
                operating_cash_flow=free_cash_flow, investment_cash_flow=0,
            )
    BalanceSheet.objects.create(
        ticker=ticker, end_date=date(2025, 12, 31),
        total_debt=1_000_000, total_lease=0, total_liabilities=2_000_000,
        stockholders_equity=4_000_000, current_assets=3_000_000,
        current_liabilities=1_500_000,
    )


# --- Cache keys -------------------------------------------------------------

def test_cache_keys_match_the_keys_the_views_actually_use():
    """Pinning the literals: drift here silently breaks invalidation."""
    assert fundamentals_cache_key(TICKER) == "fundamentals:GGBR3"
    assert pe10_cache_key(TICKER) == "pe10:GGBR3"
    assert multiples_history_cache_key(TICKER) == "multiples_history:GGBR3"


def test_cache_keys_are_uppercased():
    assert statement_derived_cache_keys("ggbr3") == [
        "fundamentals:GGBR3", "pe10:GGBR3", "multiples_history:GGBR3",
    ]


def test_invalidation_drops_every_statement_derived_key():
    for key in statement_derived_cache_keys(TICKER):
        cache.set(key, {"stale": True}, 300)

    invalidate_statement_caches(TICKER)

    assert all(cache.get(key) is None for key in statement_derived_cache_keys(TICKER))


def test_invalidation_leaves_unrelated_caches_alone():
    """Company metadata and peers do not derive from statements."""
    cache.set(f"ticker_detail_{TICKER}", {"name": "Gerdau"}, 300)
    cache.set(f"ticker_peers_{TICKER}", [{"symbol": "CSNA3"}], 300)
    cache.set("search:abc123", ["GGBR3"], 300)

    invalidate_statement_caches(TICKER)

    assert cache.get(f"ticker_detail_{TICKER}") == {"name": "Gerdau"}
    assert cache.get(f"ticker_peers_{TICKER}") == [{"symbol": "CSNA3"}]
    assert cache.get("search:abc123") == ["GGBR3"]


def test_invalidation_of_an_uncached_ticker_is_a_no_op():
    invalidate_statement_caches("NOPE3")  # must not raise


# --- Client cache header ----------------------------------------------------

def test_statement_derived_payloads_are_held_for_five_minutes():
    """The last remaining staleness between a filing and the page.

    Server-side caches are dropped on write, so this header is the only
    delay left. It was an hour, which capped how fresh the site could ever
    be regardless of ingestion speed.
    """
    assert STATEMENT_DERIVED_CLIENT_CACHE_TTL == 300
    assert STATEMENT_DERIVED_CACHE_CONTROL == "public, max-age=300"


# --- Snapshot recomputation -------------------------------------------------

@pytest.mark.django_db
def test_recompute_updates_the_snapshot_from_current_statements(ipca_zero):
    seed_ten_years(TICKER, net_income=1_000_000, free_cash_flow=1_000_000)
    IndicatorSnapshot.objects.create(
        ticker=TICKER, pe10=Decimal("99"), market_cap=400_000_000,
        current_price=Decimal("20"),
    )

    assert recompute_indicator_snapshot(TICKER) is True

    snapshot = IndicatorSnapshot.objects.get(ticker=TICKER)
    assert snapshot.pe10 != Decimal("99")
    assert snapshot.pe10 == Decimal("100.0000")  # 400m cap / 4m annual earnings


@pytest.mark.django_db
def test_recompute_preserves_market_cap_and_price(ipca_zero):
    """Statements changed, market data did not — do not blank it."""
    seed_ten_years(TICKER, net_income=1_000_000, free_cash_flow=1_000_000)
    IndicatorSnapshot.objects.create(
        ticker=TICKER, market_cap=400_000_000, current_price=Decimal("20"),
    )

    recompute_indicator_snapshot(TICKER)

    snapshot = IndicatorSnapshot.objects.get(ticker=TICKER)
    assert snapshot.market_cap == 400_000_000
    assert snapshot.current_price == Decimal("20")


@pytest.mark.django_db
def test_recompute_falls_back_to_the_ticker_market_cap(ipca_zero):
    seed_ten_years(TICKER, net_income=1_000_000, free_cash_flow=1_000_000)
    Ticker.objects.create(
        symbol=TICKER, name="Gerdau", type="stock", market_cap=400_000_000,
    )

    assert recompute_indicator_snapshot(TICKER) is True

    assert IndicatorSnapshot.objects.get(ticker=TICKER).pe10 == Decimal("100.0000")


@pytest.mark.django_db
def test_recompute_skips_when_no_market_cap_is_known(ipca_zero):
    """Without a market cap the valuation multiples would all be null."""
    seed_ten_years(TICKER, net_income=1_000_000, free_cash_flow=1_000_000)

    assert recompute_indicator_snapshot(TICKER) is False
    assert not IndicatorSnapshot.objects.filter(ticker=TICKER).exists()


# --- The combined entry point ----------------------------------------------

@pytest.mark.django_db
def test_refresh_recomputes_the_snapshot_before_dropping_the_caches(ipca_zero):
    """Ordering matters: a request arriving after the drop must rebuild
    from an already-correct snapshot, never from a stale one."""
    seed_ten_years(TICKER, net_income=1_000_000, free_cash_flow=1_000_000)
    IndicatorSnapshot.objects.create(
        ticker=TICKER, pe10=Decimal("99"), market_cap=400_000_000,
    )
    for key in statement_derived_cache_keys(TICKER):
        cache.set(key, {"stale": True}, 300)

    observed = []
    original_delete_many = cache.delete_many

    def spy(keys):
        observed.append(IndicatorSnapshot.objects.get(ticker=TICKER).pe10)
        return original_delete_many(keys)

    cache.delete_many = spy
    try:
        refresh_derived_data(TICKER)
    finally:
        cache.delete_many = original_delete_many

    assert observed == [Decimal("100.0000")]
    assert all(cache.get(key) is None for key in statement_derived_cache_keys(TICKER))


@pytest.mark.django_db
def test_refresh_still_clears_caches_when_the_snapshot_is_skipped(ipca_zero):
    seed_ten_years(TICKER, net_income=1_000_000, free_cash_flow=1_000_000)
    for key in statement_derived_cache_keys(TICKER):
        cache.set(key, {"stale": True}, 300)

    refresh_derived_data(TICKER)

    assert all(cache.get(key) is None for key in statement_derived_cache_keys(TICKER))
