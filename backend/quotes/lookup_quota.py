"""Single source of truth for the daily company-lookup cap.

Tiers (distinct tickers per day, in the active timezone — matching the
historical QuotaView day boundary):

  - anonymous              -> SPONDA_ANON_LOOKUPS_PER_DAY, scoped by IP hash
  - logged in, unverified  -> SPONDA_UNVERIFIED_LOOKUPS_PER_DAY, scoped by user
  - logged in, verified    -> unlimited

Both PE10View (enforcement) and QuotaView (reporting) call into here so
the number a user sees and the number that blocks them can never drift.
"""
from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from quotes.client_ip import client_ip_hash
from quotes.models import LookupLog

SCOPE_ANONYMOUS = "anonymous"
SCOPE_UNVERIFIED = "unverified"
SCOPE_VERIFIED = "verified"


def _day_start():
    return timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _scope(request):
    """Return (scope, filter_kwargs, limit). limit is None for unlimited."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        if getattr(user, "email_verified", False):
            return SCOPE_VERIFIED, {"user": user}, None
        return (
            SCOPE_UNVERIFIED,
            {"user": user},
            settings.SPONDA_UNVERIFIED_LOOKUPS_PER_DAY,
        )
    return (
        SCOPE_ANONYMOUS,
        {"ip_hash": client_ip_hash(request)},
        settings.SPONDA_ANON_LOOKUPS_PER_DAY,
    )


def _distinct_today(filter_kwargs) -> int:
    return (
        LookupLog.objects.filter(timestamp__gte=_day_start(), **filter_kwargs)
        .values("ticker")
        .distinct()
        .count()
    )


def _ticker_seen_today(filter_kwargs, ticker: str) -> bool:
    return LookupLog.objects.filter(
        timestamp__gte=_day_start(), ticker=ticker, **filter_kwargs
    ).exists()


def lookup_quota(request) -> dict:
    scope, filter_kwargs, limit = _scope(request)
    used = _distinct_today(filter_kwargs)
    remaining = None if limit is None else max(0, limit - used)
    user = getattr(request, "user", None)
    authenticated = bool(user is not None and user.is_authenticated)
    return {
        "scope": scope,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "authenticated": authenticated,
        "email_verified": bool(authenticated and getattr(user, "email_verified", False)),
    }


def would_exceed_limit(request, ticker: str) -> bool:
    """True if serving ``ticker`` now would push this scope past its cap.

    Re-viewing a ticker already counted today is always free, so a user
    who hit the cap can still revisit what they have seen.
    """
    scope, filter_kwargs, limit = _scope(request)
    if limit is None:
        return False
    if _ticker_seen_today(filter_kwargs, ticker):
        return False
    return _distinct_today(filter_kwargs) >= limit
