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

from .providers import ProviderError, sync_balance_sheets, sync_cash_flows, sync_earnings

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
    """
    for label, fn in (
        ("earnings", sync_earnings),
        ("cash_flows", sync_cash_flows),
        ("balance_sheets", sync_balance_sheets),
    ):
        try:
            fn(ticker)
        except ProviderError as error:
            logger.warning(
                "refresh_provider_data: %s sync_%s failed: %s",
                ticker, label, error,
            )
