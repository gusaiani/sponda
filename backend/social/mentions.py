"""Extract ``@handle`` and ``$TICKER`` mentions from Spond bodies.

The parser is intentionally permissive: it matches plausible patterns and
hands them off to the persistence layer to validate against the database
(only handles that exist as real Users get a Mention row; only tickers that
exist in the Ticker table get a TickerMention row).

Both extractors are pure — no DB access — so they're safe to call inside a
serializer's ``validate_body`` and again inside the create-Spond view's
transaction without paying I/O twice.
"""
from __future__ import annotations

import re

from accounts.handles import (
    HANDLE_MAX_LENGTH,
    HANDLE_MIN_LENGTH,
    is_reserved_handle,
)


# Cap from the plan: a single Spond may not mention more than 8 distinct
# handles. Anti-spam (mention bombs).
MENTION_LIMIT_PER_SPOND = 8

# An @handle is preceded by start-of-string or a non-handle, non-email char.
# We forbid matches preceded by an alphanumeric or "." so addresses like
# ``foo@bar.com`` and ``a.b@c`` don't read as mentions of ``bar``/``b``.
_HANDLE_RE = re.compile(
    r"(?:^|(?<=[^a-zA-Z0-9._]))@([a-z0-9](?:[a-z0-9_]{1,%d})[a-z0-9])(?![a-zA-Z0-9_])"
    % (HANDLE_MAX_LENGTH - 2),
    re.IGNORECASE,
)

# A $TICKER is 1-5 letters optionally followed by 1-2 digits. The leading
# ``$`` must be preceded by start-of-string or whitespace/punctuation that
# isn't itself a digit (``$500B`` should not match).
_TICKER_RE = re.compile(
    r"(?:^|(?<=[^A-Za-z0-9.]))\$([A-Za-z]{1,5}\d{0,2})\b",
)


def extract_handle_mentions(body: str) -> list[str]:
    """Return the list of distinct lowercase handles mentioned in ``body``.

    Order is preserved (first-seen wins). Handles shorter than the minimum
    length, longer than the maximum, or matching reserved words are dropped.
    The result is capped at :data:`MENTION_LIMIT_PER_SPOND`.
    """
    if not body:
        return []
    seen: list[str] = []
    seen_set: set[str] = set()
    for match in _HANDLE_RE.finditer(body):
        handle = match.group(1).lower()
        if len(handle) < HANDLE_MIN_LENGTH or len(handle) > HANDLE_MAX_LENGTH:
            continue
        if is_reserved_handle(handle):
            continue
        if handle in seen_set:
            continue
        seen.append(handle)
        seen_set.add(handle)
        if len(seen) >= MENTION_LIMIT_PER_SPOND:
            break
    return seen


def extract_ticker_mentions(body: str) -> list[str]:
    """Return distinct uppercase ticker symbols mentioned in ``body``.

    Only matches the ``$SYMBOL`` form; bare ticker words like "PETR4" are
    not extracted (too noisy). Order is preserved.
    """
    if not body:
        return []
    seen: list[str] = []
    seen_set: set[str] = set()
    for match in _TICKER_RE.finditer(body):
        symbol = match.group(1).upper()
        if symbol in seen_set:
            continue
        seen.append(symbol)
        seen_set.add(symbol)
    return seen
