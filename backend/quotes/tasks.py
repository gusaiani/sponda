"""Celery tasks for quote/fundamentals data refresh.

The home-page fanout used to pay the cold provider cost inside every
request whose data was older than 24h. With ~30 tickers per visit, that
meant a one-in-30 chance any given user pulled the short straw and
waited ~6 s for a re-sync of a single ticker — and then the next one.

These tasks let the user request return immediately with stale data
while a background worker refreshes the cache.
"""
from __future__ import annotations

import logging

from celery import shared_task

from .derived_data import refresh_derived_data
from .providers import ProviderError, sync_balance_sheets, sync_cash_flows, sync_earnings
from .statement_refresh_state import record_statement_refresh_attempt

logger = logging.getLogger(__name__)


@shared_task(
    name="quotes.refresh_provider_data",
    autoretry_for=(ProviderError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def refresh_provider_data(ticker: str) -> None:
    """Re-pull earnings, cash flows, and balance sheets for one ticker.

    Tolerates per-call ProviderError so an outage on one source does not
    take down the entire refresh of the others.

    Refreshing derived data at the end is what makes stale-while-revalidate
    actually revalidate: without it the freshly synced quarter would sit
    behind a 24h cached payload, so "tomorrow's request sees today's data"
    would not hold.

    The attempt is recorded last and unconditionally. Last, because the page
    refetches the moment the refresh stops being pending and must find the
    caches already dropped. Unconditionally, because a refresh that failed
    is over too, and the page should stop waiting for it.
    """
    try:
        for label, sync_statements in (
            ("earnings", sync_earnings),
            ("cash_flows", sync_cash_flows),
            ("balance_sheets", sync_balance_sheets),
        ):
            try:
                sync_statements(ticker)
            except ProviderError as error:
                logger.warning(
                    "refresh_provider_data: %s sync_%s failed: %s",
                    ticker, label, error,
                )

        refresh_derived_data(ticker)
    finally:
        record_statement_refresh_attempt(ticker)
