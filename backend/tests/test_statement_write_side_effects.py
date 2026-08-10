"""Every path that writes statements must refresh what was derived from them.

Three writers exist: the Celery stale-while-revalidate task, the weekly
fundamentals refresh, and the CVM seeder. A writer that skips this leaves the
Fundamentos payload cached for 24h and the screener disagreeing with the
detail page for up to a week.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command

from quotes.derived_data import fundamentals_cache_key, statement_derived_cache_keys
from quotes.models import IndicatorSnapshot, IPCAIndex, QuarterlyEarnings, Ticker
from quotes.tasks import refresh_provider_data
from tests.test_seed_quarter_from_cvm import gerdau_archive

TICKER = "GGBR3"
SEED_COMMAND_MODULE = "quotes.management.commands.seed_quarter_from_cvm"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def warm_statement_caches():
    for key in statement_derived_cache_keys(TICKER):
        cache.set(key, {"stale": True}, 3600)
    return statement_derived_cache_keys(TICKER)


def assert_caches_cleared(keys):
    assert all(cache.get(key) is None for key in keys), (
        "a statement write left a stale payload cached"
    )


@pytest.mark.django_db
def test_seeding_from_cvm_clears_the_statement_caches(warm_statement_caches):
    with patch(f"{SEED_COMMAND_MODULE}.download_itr_archive") as download:
        download.return_value = gerdau_archive()
        call_command(
            "seed_quarter_from_cvm", "--quarter", "2026-06-30", "--ticker", TICKER,
        )

    assert_caches_cleared(warm_statement_caches)


@pytest.mark.django_db
def test_seeding_dry_run_leaves_caches_intact(warm_statement_caches):
    """Nothing was written, so nothing derived is stale."""
    with patch(f"{SEED_COMMAND_MODULE}.download_itr_archive") as download:
        download.return_value = gerdau_archive()
        call_command(
            "seed_quarter_from_cvm", "--quarter", "2026-06-30",
            "--ticker", TICKER, "--dry-run",
        )

    assert cache.get(fundamentals_cache_key(TICKER)) == {"stale": True}


@pytest.mark.django_db
def test_background_provider_refresh_clears_the_statement_caches(warm_statement_caches):
    """The whole point of stale-while-revalidate is defeated by a 24h cache."""
    with patch("quotes.tasks.sync_earnings"), \
         patch("quotes.tasks.sync_cash_flows"), \
         patch("quotes.tasks.sync_balance_sheets"):
        refresh_provider_data(TICKER)

    assert_caches_cleared(warm_statement_caches)


@pytest.mark.django_db
def test_weekly_fundamentals_refresh_clears_the_statement_caches(warm_statement_caches):
    IPCAIndex.objects.update_or_create(
        date=date(2026, 12, 31), defaults={"annual_rate": Decimal("0")},
    )
    Ticker.objects.create(
        symbol=TICKER, name="Gerdau", type="stock", market_cap=400_000_000,
    )
    QuarterlyEarnings.objects.create(
        ticker=TICKER, end_date=date(2025, 12, 31), net_income=1_000_000,
    )

    with patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_earnings"), \
         patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_cash_flows"), \
         patch("quotes.management.commands.refresh_snapshot_fundamentals.sync_balance_sheets"), \
         patch("quotes.management.commands.refresh_snapshot_fundamentals.fetch_quote") as quote:
        quote.return_value = {"marketCap": 400_000_000, "regularMarketPrice": 20.0}
        call_command("refresh_snapshot_fundamentals", "--ticker", TICKER)

    assert_caches_cleared(warm_statement_caches)


@pytest.mark.django_db
def test_seeding_recomputes_the_screener_snapshot():
    """The screener reads IndicatorSnapshot, not the statements directly."""
    Ticker.objects.create(
        symbol=TICKER, name="Gerdau", type="stock", market_cap=400_000_000,
    )
    IndicatorSnapshot.objects.create(
        ticker=TICKER, pe10=Decimal("99"), market_cap=400_000_000,
    )

    with patch(f"{SEED_COMMAND_MODULE}.download_itr_archive") as download:
        download.return_value = gerdau_archive()
        call_command(
            "seed_quarter_from_cvm", "--quarter", "2026-06-30", "--ticker", TICKER,
        )

    # One quarter of data is far too little for a ten-year multiple, so the
    # stale 99 must be cleared rather than left standing.
    assert IndicatorSnapshot.objects.get(ticker=TICKER).pe10 != Decimal("99")
