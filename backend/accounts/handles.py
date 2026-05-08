"""Validation, normalization, and derivation helpers for User.handle.

A handle is a public, unique identifier shown next to the display name in the
social UI (`@alice`). Rules below are intentionally narrow so URLs like
``/user/<handle>`` never collide with locales, ticker symbols, or other
top-level routes, and so handles read cleanly across all 7 supported locales.
"""
from __future__ import annotations

import re


HANDLE_MIN_LENGTH = 3
HANDLE_MAX_LENGTH = 24


# Lowercase alphanumeric or underscore; cannot start or end with underscore;
# no consecutive underscores. Length is checked separately.
_HANDLE_BODY_RE = re.compile(r"^[a-z0-9](?:[a-z0-9]|_(?!_))*[a-z0-9]$")


# Words we will not let users register because they collide with current or
# plausible future routes, would be confusing in URLs, or are brand-sensitive.
# Locale codes appear so /user/pt etc. cannot be a real profile.
RESERVED_HANDLES: frozenset[str] = frozenset({
    # Brand and core nouns
    "sponda", "spond", "sponds",
    # Auth
    "auth", "login", "logout", "signup", "signin", "signout",
    "password", "verify", "verification",
    # Generic top-level routes
    "admin", "api", "user", "users", "me", "settings", "account",
    "profile", "profiles", "search", "feed", "global", "explore",
    "notifications", "notification", "favorites", "favourites",
    "lists", "screener", "alerts", "alertas", "listas",
    "static", "assets", "robots", "sitemap", "favicon",
    "help", "about", "terms", "privacy", "contact", "legal",
    "blog", "docs", "support", "home", "index", "root", "system",
    # Locales — must mirror SUPPORTED_LANGUAGES in accounts/models.py
    "pt", "en", "es", "zh", "fr", "de", "it",
})


class HandleValidationError(ValueError):
    """Raised when a handle violates the validation rules."""


def is_reserved_handle(handle: str) -> bool:
    return handle.lower() in RESERVED_HANDLES


def is_valid_handle(handle: str) -> bool:
    if not isinstance(handle, str):
        return False
    if len(handle) < HANDLE_MIN_LENGTH or len(handle) > HANDLE_MAX_LENGTH:
        return False
    if not _HANDLE_BODY_RE.match(handle):
        return False
    if is_reserved_handle(handle):
        return False
    return True


def validate_handle(handle: str) -> None:
    """Raise :class:`HandleValidationError` if ``handle`` is not acceptable."""
    if not isinstance(handle, str) or not handle:
        raise HandleValidationError("Handle is required.")
    if len(handle) < HANDLE_MIN_LENGTH:
        raise HandleValidationError(
            f"Handle must be at least {HANDLE_MIN_LENGTH} characters.",
        )
    if len(handle) > HANDLE_MAX_LENGTH:
        raise HandleValidationError(
            f"Handle must be at most {HANDLE_MAX_LENGTH} characters.",
        )
    if not _HANDLE_BODY_RE.match(handle):
        raise HandleValidationError(
            "Handle must use lowercase letters, digits, and single underscores; "
            "may not start or end with an underscore.",
        )
    if is_reserved_handle(handle):
        raise HandleValidationError("That handle is reserved.")


def normalize_handle_input(raw: str) -> str:
    """Best-effort normalization of arbitrary input toward a valid handle.

    Lowercases, strips characters outside ``[a-z0-9_]``, collapses runs of
    underscores to a single one, and trims leading/trailing underscores. The
    result is *not guaranteed valid* — it may still be too short or land on a
    reserved word. Callers (form serializers, the data migration backfill)
    layer additional rules on top.
    """
    if not raw:
        return ""
    lowered = raw.lower()
    kept = re.sub(r"[^a-z0-9_]", "", lowered)
    collapsed = re.sub(r"_+", "_", kept)
    return collapsed.strip("_")


def _email_local_part(email: str) -> str:
    """Return the local part of an email, with any ``+tag`` suffix removed.

    ``alice+spam@example.com`` and ``alice@example.com`` both yield ``alice``;
    treating them the same when picking a handle avoids leaking tags users
    use for filtering.
    """
    if not email or "@" not in email:
        local = email or ""
    else:
        local = email.split("@", 1)[0]
    if "+" in local:
        local = local.split("+", 1)[0]
    return local


def derive_handle(email: str, existing: set[str]) -> str:
    """Pick a unique, valid handle for a new user given their email.

    The base is the email's local part, normalized. If the base is too short,
    reserved, or already taken, we append a numeric suffix (``_2``, ``_3``, …)
    until we find one that is valid and not in ``existing``. ``existing`` is
    mutated by the caller between invocations — pass the running set of
    handles already taken in this batch.

    Always returns a valid handle. Truncates the base if necessary so the
    result respects ``HANDLE_MAX_LENGTH`` even after the suffix.
    """
    base = normalize_handle_input(_email_local_part(email))
    if not base:
        base = "user"

    # Truncate base to leave room for a 5-char suffix like "_9999".
    max_base = HANDLE_MAX_LENGTH - 5
    if len(base) > max_base:
        base = base[:max_base].rstrip("_")
        if not base:
            base = "user"

    candidate = base
    if is_valid_handle(candidate) and candidate not in existing:
        existing.add(candidate)
        return candidate

    # Pad short bases up to the minimum length before adding suffixes.
    if len(candidate) < HANDLE_MIN_LENGTH:
        candidate = (candidate + "user")[:HANDLE_MAX_LENGTH]

    if is_valid_handle(candidate) and candidate not in existing:
        existing.add(candidate)
        return candidate

    suffix = 2
    while True:
        attempt = f"{base}_{suffix}"
        # Defensive truncation — extremely unlikely with max_base above but
        # still worth checking in case the suffix grows past 5 chars.
        if len(attempt) > HANDLE_MAX_LENGTH:
            attempt = attempt[-HANDLE_MAX_LENGTH:].lstrip("_") or "user"
        if is_valid_handle(attempt) and attempt not in existing:
            existing.add(attempt)
            return attempt
        suffix += 1
        if suffix > 99999:  # pragma: no cover — sanity guard
            raise RuntimeError("could not derive a unique handle")
