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
    """
    if user.is_superuser:
        return "superuser"
    if is_paying_user(user):
        return "paying"
    return "denied"

def is_paying_user(user) -> bool:
    """Stub: returns False until a Subscription model exists.

    Defined here so callers - including tests that patch this exact
    symbol - have one stable import path. When billing lands the body
    becomes a real lookup; the signature does not change.
    """
    return False

def would_exceed_assistant_limit(user) -> bool:
    """Return True if `user` is already at (or over) their daily cap.

    Called by the  view before any OpenAI call so a blocked caller
    costs us nothing. The singe seam: tier -> cap -> count. For
    now only the 'denied' bdranch is wired; other tiers land in the next baby steps.
    """
    tier = assistant_access_tier(user)

    if tier == "superuser":
        return False
    if tier == "denied":
        return True
    if tier == "paying":
        today = timezone.now().date()
        used_today = LLMQuery.objects.filter(
            user=user,
            created_at__date=today,
        ).count()
        return used_today >= settings.ASSISTANT_PAYING_PER_DAY