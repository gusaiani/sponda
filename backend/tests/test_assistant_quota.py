"""Tests for assistant.assistant_quota - tier resolution and daily caps.

The tier resolver is the single seam the rest of the system reads from:
flipping a free trial on, adding paying users, or changing caps all happen
behind this one function. Tests pin the contract so callers (view, future
billing) can rely on it.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from assistant.assistant_quota import (
    assistant_access_tier,
    would_exceed_assistant_limit,
)
from assistant.models import LLMQuery


@pytest.mark.django_db
class TestAssistantAccessTier:
    def test_superuser_user_resolves_to_superuser_tier(self, superuser):
        """A Django superuser is the only tier with no cap in v1. The
        resolver must return the literal string 'superuser' so the view
        and quota counter can branch on it without importing User flags.
        """
        assert assistant_access_tier(superuser) == "superuser"

    def test_anonymous_user_resolves_to_denied(self):
        """Anonymous callers get nothing in v1. `is_superuser` on
        AnonymousUser is False, so the resolver must fall through to
        'denied' rather than raising or returning None.
        """
        assert assistant_access_tier(AnonymousUser()) == "denied"

    def test_paying_user_resolves_to_paying_tier(self, paying_user):
        """When is_paying_user(user) is True, the resolver returns
        'paying'. We patch the stub so this test stays green even
        after a real Subscription model lands - the resolver's
        contract is what's being locked, not billing infrastructure.
        """
        with patch(
            "assistant.assistant_quota.is_paying_user",
            return_value=True,
        ):
            assert assistant_access_tier(paying_user) == "paying"


@pytest.mark.django_db
class TestWouldExceedAssistantLimit:
    def test_denied_tier_always_exceeds(self):
        """Anonymous users resolve to the 'denied' tier (cap 0). The
        guard must short-circuit to True without touching the DB or
        OpenAI - the view returns 429 before any cost is incurred.
        """
        assert would_exceed_assistant_limit(AnonymousUser()) is True

    def test_superuser_never_exceeds(self, superuser):
        """Superuser is uncapped in v1."""
        assert would_exceed_assistant_limit(superuser) is False

    def test_paying_user_under_cap_does_not_exceed(self, paying_user, settings):
        """Paying tier with no queries today is under cap. Locks the
        contract that the guard reads ASSISTANT_PAYING_PER_DAY and
        counts only today's LLMQuery rows for this user.
        """
        settings.ASSISTANT_PAYING_PER_DAY = 5

        with patch(
            "assistant.assistant_quota.is_paying_user",
            return_value=True,
        ):
            assert would_exceed_assistant_limit(paying_user) is False

    def test_paying_user_at_cap_exceeds(self, paying_user, settings):
        """Paying tier at exactly the cap is blocked. Locks the
        boundary: the comparison is `>=`, not `>`, so the Nth query
        is the last allowed and the (N+1)th is refused before any
        OpenAI call.
        """
        daily_cap = 3
        settings.ASSISTANT_PAYING_PER_DAY = daily_cap

        for _ in range(daily_cap):
            LLMQuery.objects.create(
                user=paying_user,
                ticker="PETR4",
                question="q",
                classification="on_topic",
            )

        with patch(
            "assistant.assistant_quota.is_paying_user",
            return_value=True,
        ):
            assert would_exceed_assistant_limit(paying_user) is True

    def test_paying_user_yesterdays_rows_do_not_count(self, paying_user, settings):
        """Quota is a *daily* cap. A user at the cap yesterday must be
        free to ask again today. Locks the date filter so a slow-drip
        abuser cannot accumulate forever and brick the account.
        """
        settings.ASSISTANT_PAYING_PER_DAY = 2

        yesterday = timezone.now() - timedelta(days=1)
        for _ in range(5):
            row = LLMQuery.objects.create(
                user=paying_user,
                ticker="PETR4",
                question="q",
                classification="on_topic",
            )
            # auto_now_add ignores manual values during create(), so we
            # backdate with an explicit update after the row exists.
            LLMQuery.objects.filter(pk=row.pk).update(created_at=yesterday)

        with patch(
            "assistant.assistant_quota.is_paying_user",
            return_value=True,
        ):
            assert would_exceed_assistant_limit(paying_user) is False
