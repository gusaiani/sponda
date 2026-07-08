"""Tier resolution and daily cap enforcement for the LLM assistant.

The single seam the view reads from: flipping the free trial on, adding 
paying users, or changing caps all happen behind these functions. Keep
behavior tight against tests in tests/test_assistant_quota.py.
"""
from django.conf import settings
from django.utils import timezone

from assistant.models import LLMQuery


def assistant_access_tier(user) -> str:
    """Return the access tier for `user`.

    One of 'superuser' | 'paying' | 'trial' | 'denied'. Callers branch
    on the literal string so they don't need to know about User flags
    or settings - all that knowledge lives here.

    `user` may be None, an AnonymousUser, or an authenticated User -
    every call site (the view, tests, and a future anonymous screening
    call site) can pass whatever it already has without pre-checking
    `is_authenticated` itself.
    """
    if user is None or not user.is_authenticated:
        return "trial" if settings.ASSISTANT_FREE_TRIAL_PER_DAY > 0 else "denied"
    if user.is_superuser:
        return "superuser"
    if is_paying_user(user):
        return "paying"
    return "trial" if settings.ASSISTANT_FREE_TRIAL_PER_DAY > 0 else "denied"

def is_paying_user(user) -> bool:
    """Stub: returns False until a Subscription model exists.

    Defined here so callers - including tests that patch this exact
    symbol - have one stable import path. When billing lands the body
    becomes a real lookup; the signature does not change.
    """
    return False

def would_exceed_assistant_limit(user, ip_hash=None) -> bool:
    """Return True if `user` is already at (or over) their daily cap.

    Called by the view before any OpenAI call so a blocked caller costs
    us nothing. The single seam: tier -> cap -> count. Every tier
    `assistant_access_tier` can return is handled explicitly, and the
    function is total: anything it does not recognize fails closed
    (True) rather than implicitly returning None.

    `ip_hash` scopes the trial cap for anonymous callers (there is no
    `user` to count against) - unused by every other tier. It is a
    caller-supplied hash (see quotes.client_ip.client_ip_hash for the
    established hashing approach); this module does not compute one.
    """
    tier = assistant_access_tier(user)

    if tier == "superuser":
        return False
    if tier == "denied":
        return True
    if tier == "paying":
        # `created_at__date` is evaluated in the project timezone (USE_TZ), so
        # the cap boundary must use the local date too. The UTC date would
        # miscount near UTC midnight (00:00-03:00 in Sao Paulo), letting a
        # capped user through or, as the tests caught, failing to count today.
        today = timezone.localdate()
        used_today = LLMQuery.objects.filter(
            user=user,
            created_at__date=today,
        ).count()
        return used_today >= settings.ASSISTANT_PAYING_PER_DAY
    if tier == "trial":
        # Same localdate rationale as the paying tier above: the cap
        # boundary must track the project timezone, not UTC.
        today = timezone.localdate()
        is_authenticated_user = user is not None and user.is_authenticated
        if is_authenticated_user:
            used_today = LLMQuery.objects.filter(
                user=user,
                created_at__date=today,
            ).count()
        else:
            # No IP to scope the cap by means no way to count this
            # caller's usage - fail closed instead of granting a free,
            # untracked question.
            if not ip_hash:
                return True
            used_today = LLMQuery.objects.filter(
                ip_hash=ip_hash,
                created_at__date=today,
            ).count()
        return used_today >= settings.ASSISTANT_FREE_TRIAL_PER_DAY

    # Unknown/future tier: fail closed rather than silently returning
    # None (falsy, and would have let an unrecognized tier through).
    return True