"""Who is refreshing a company's statements right now, and who just tried.

A stale company is answered from stored statements while a Celery task
refetches them. Two things went wrong without a shared record of that:

* Quote, fundamentals and chart each noticed the staleness on their own and
  each enqueued a refresh, so one visit cost nine provider calls for three
  statements.
* Nothing could tell the page that fresher numbers were seconds away, so
  the visitor kept the stored ones until a reload.

One cache key per company carries the answer. It is absent when nothing has
happened lately, ``pending`` while a refresh is in flight, and ``attempted``
for a while after one finished. The last state is what stops a company whose
provider keeps failing, and which is therefore still stale after its
refresh, from being refreshed again on every request.
"""
from django.core.cache import cache

STATEMENT_REFRESH_STATE_CACHE_KEY_TEMPLATE = "statement_refresh_state:{ticker}"

REFRESH_PENDING = "pending"
REFRESH_ATTEMPTED = "attempted"

# How long a claim holds without the task reporting back. A refresh is three
# provider calls that each time out after eight seconds, plus its wait in the
# queue, so two minutes means the worker died rather than that it is slow.
# The page stops polling well before this, so an abandoned claim costs one
# company one late refresh and nothing else.
REFRESH_PENDING_TTL_SECONDS = 2 * 60

# How long a finished attempt blocks another one. Long enough to cover the
# three endpoints of one page view and a burst of visitors behind them,
# short enough that a provider outage is retried within the hour.
REFRESH_ATTEMPT_COOLDOWN_SECONDS = 60 * 60


def _state_cache_key(ticker: str) -> str:
    return STATEMENT_REFRESH_STATE_CACHE_KEY_TEMPLATE.format(ticker=ticker.upper())


def claim_statement_refresh(ticker: str) -> bool:
    """Take ownership of refreshing this company's statements.

    True means the caller owns the refresh and must enqueue it. False means
    one is already in flight or was attempted too recently to repeat.
    ``cache.add`` only writes when the key is absent, which is what makes
    this safe across gunicorn workers.
    """
    return cache.add(
        _state_cache_key(ticker), REFRESH_PENDING, REFRESH_PENDING_TTL_SECONDS,
    )


def is_statement_refresh_pending(ticker: str) -> bool:
    return cache.get(_state_cache_key(ticker)) == REFRESH_PENDING


def release_statement_refresh_claim(ticker: str) -> None:
    """Give a claim back when its refresh could not be enqueued."""
    cache.delete(_state_cache_key(ticker))


def record_statement_refresh_attempt(ticker: str) -> None:
    """Mark the refresh as over, whether or not the provider cooperated."""
    cache.set(
        _state_cache_key(ticker), REFRESH_ATTEMPTED, REFRESH_ATTEMPT_COOLDOWN_SECONDS,
    )
