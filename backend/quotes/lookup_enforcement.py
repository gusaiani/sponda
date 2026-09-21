"""Reusable lookup-quota enforcement for ticker payload endpoints.

The daily distinct-company cap (see :mod:`quotes.lookup_quota`) must guard
*every* endpoint that turns a ticker into an expensive provider-backed
payload, not just ``PE10View``. Otherwise a client can enumerate the whole
catalogue through the sub-endpoints (fundamentals, multiples-history) while
never tripping the cap, hammering the data providers once per ticker.

This mixin centralises the two operations every such view needs:

  * :meth:`enforce_lookup_quota` — short-circuit with a 429 *before* any work
    when the scope is over its cap (re-viewing a ticker already counted today
    is always free).
  * :meth:`record_lookup` / :meth:`record_lookups` — attribute successful
    lookups to the user (when authenticated) or to the hashed client IP +
    session (when anonymous), so the distinct-company count grows and the
    cap can take effect.

Attribution lives here, in one place, because getting it subtly wrong is
silent. :mod:`quotes.lookup_quota` scopes an anonymous caller by
``ip_hash`` alone, so a row written with only a ``session_key`` is
invisible to the cap. ``BatchQuotesView`` kept its own copy of this and
wrote exactly that, which left a client able to POST a hundred symbols at
a time and never trip the limit the single-company endpoints enforce.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from quotes.client_ip import client_ip_hash
from quotes.lookup_quota import lookup_quota, would_exceed_limit
from quotes.models import LookupLog


class LookupQuotaEnforcedView:
    """Mixin granting a DRF view the shared lookup-quota gate and logger."""

    def enforce_lookup_quota(self, request, ticker: str):
        """Return a non-cacheable 429 ``Response`` if ``ticker`` is over cap.

        Returns ``None`` when the request may proceed, so callers write::

            blocked = self.enforce_lookup_quota(request, ticker)
            if blocked is not None:
                return blocked
        """
        if not would_exceed_limit(request, ticker):
            return None
        quota = lookup_quota(request)
        response = Response(
            {
                "error": "lookup_limit_reached",
                "code": "lookup_limit",
                "limit": quota["limit"],
                "scope": quota["scope"],
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Cache-Control"] = "no-store"
        return response

    def record_lookup(self, request, ticker: str) -> None:
        """Persist a successful lookup so it counts toward the daily cap."""
        self.record_lookups(request, [ticker])

    def record_lookups(self, request, tickers: list[str]) -> None:
        """Persist several successful lookups in a single INSERT.

        A row per ticker in a Python loop is up to ``MAX_BATCH_SIZE``
        round trips to Postgres on the request's critical path, for rows
        nothing reads until the next quota check.
        """
        if not tickers:
            return
        LookupLog.objects.bulk_create(self._lookup_rows(request, tickers))

    @staticmethod
    def _lookup_rows(request, tickers: list[str]) -> list[LookupLog]:
        """Who each of these lookups belongs to, unsaved."""
        if request.user.is_authenticated:
            return [
                LookupLog(user=request.user, ticker=ticker) for ticker in tickers
            ]
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        ip_hash = client_ip_hash(request)
        return [
            LookupLog(session_key=session_key, ip_hash=ip_hash, ticker=ticker)
            for ticker in tickers
        ]
