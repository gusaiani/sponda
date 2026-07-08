"""Tests for assistant.assistant_quota - tier resolution and daily caps.

The tier resolver is the single seam the rest of the system reads from:
flipping a free trial on, adding paying users, or changing caps all happen
behind this one function. Tests pin the contract so callers (view, future
billing) can rely on it.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from assistant.assistant_quota import (
    assistant_access_tier,
    would_exceed_assistant_limit,
)
from assistant.models import LLMQuery

User = get_user_model()


@pytest.fixture
def regular_user(db):
    """A logged-in, non-superuser, non-paying user - the 'authenticated
    non-paying' branch of assistant_access_tier (trial when the free
    trial is enabled, denied otherwise).
    """
    return User.objects.create_user(
        username="regular@example.com",
        email="regular@example.com",
        password="pw123456",
    )


@pytest.mark.django_db
class TestAssistantAccessTier:
    def test_superuser_user_resolves_to_superuser_tier(self, superuser):
        """A Django superuser is the only tier with no cap in v1. The
        resolver must return the literal string 'superuser' so the view
        and quota counter can branch on it without importing User flags.
        """
        assert assistant_access_tier(superuser) == "superuser"

    def test_anonymous_user_resolves_to_denied(self, settings):
        """Anonymous callers get nothing while the free trial is off.
        `is_superuser` on AnonymousUser is False, so the resolver must
        fall through to 'denied' rather than raising or returning None.
        The setting is pinned explicitly so the test does not depend on
        the developer's .env default.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 0

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

    def test_anonymous_user_resolves_to_denied_when_trial_is_off(self, settings):
        """ASSISTANT_FREE_TRIAL_PER_DAY defaults to 0 - the trial tier
        must resolve to 'denied' while it is off, not silently open a
        free lane. This is the same assertion as
        test_anonymous_user_resolves_to_denied, stated explicitly
        against the setting so the 'off means off' contract is pinned
        even if that other test's default ever gets overridden.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 0

        assert assistant_access_tier(AnonymousUser()) == "denied"

    def test_anonymous_user_resolves_to_trial_when_trial_is_on(self, settings):
        """Flipping ASSISTANT_FREE_TRIAL_PER_DAY on is the single switch
        that opens the trial tier for anonymous callers - no other code
        change should be required.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 5

        assert assistant_access_tier(AnonymousUser()) == "trial"

    def test_none_user_resolves_to_trial_when_trial_is_on(self, settings):
        """`user` can be a bare None (e.g. a future anonymous call site
        that hasn't gone through AuthenticationMiddleware). The resolver
        must not crash on a missing `.is_authenticated` attribute - None
        is treated the same as an unauthenticated user.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 5

        assert assistant_access_tier(None) == "trial"

    def test_none_user_resolves_to_denied_when_trial_is_off(self, settings):
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 0

        assert assistant_access_tier(None) == "denied"

    def test_authenticated_non_paying_user_resolves_to_denied_when_trial_is_off(
        self, regular_user, settings
    ):
        """A logged-in user who is neither superuser nor paying gets the
        same 'off means off' treatment as an anonymous caller while the
        trial is disabled.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 0

        assert assistant_access_tier(regular_user) == "denied"

    def test_authenticated_non_paying_user_resolves_to_trial_when_trial_is_on(
        self, regular_user, settings
    ):
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 5

        assert assistant_access_tier(regular_user) == "trial"


@pytest.mark.django_db
class TestWouldExceedAssistantLimit:
    def test_denied_tier_always_exceeds(self, settings):
        """With the free trial off, anonymous users resolve to the
        'denied' tier (cap 0). The guard must short-circuit to True
        without touching the DB or OpenAI - the view returns 429 before
        any cost is incurred. The setting is pinned explicitly so the
        test does not depend on the developer's .env default.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 0

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

    def test_trial_authenticated_user_under_cap_does_not_exceed(
        self, regular_user, settings
    ):
        """A logged-in, non-paying user in the trial tier is capped by
        ASSISTANT_FREE_TRIAL_PER_DAY, counted per-user just like the
        paying tier - only the setting read differs.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 3

        assert would_exceed_assistant_limit(regular_user) is False

    def test_trial_authenticated_user_at_cap_exceeds(self, regular_user, settings):
        daily_cap = 2
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = daily_cap

        for _ in range(daily_cap):
            LLMQuery.objects.create(
                user=regular_user,
                ticker="PETR4",
                question="q",
                classification="on_topic",
            )

        assert would_exceed_assistant_limit(regular_user) is True

    def test_trial_anonymous_user_under_cap_does_not_exceed(self, settings):
        """Anonymous trial usage is scoped by ip_hash, not by user (there
        is none) - mirrors quotes.lookup_quota's anonymous/IP scoping.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 3

        assert (
            would_exceed_assistant_limit(AnonymousUser(), ip_hash="a" * 64) is False
        )

    def test_trial_anonymous_user_at_cap_exceeds(self, settings):
        daily_cap = 2
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = daily_cap
        ip_hash = "b" * 64

        for _ in range(daily_cap):
            LLMQuery.objects.create(
                ip_hash=ip_hash,
                ticker="PETR4",
                question="q",
                classification="on_topic",
            )

        assert would_exceed_assistant_limit(AnonymousUser(), ip_hash=ip_hash) is True

    def test_trial_anonymous_user_without_ip_hash_exceeds(self, settings):
        """No ip_hash means no way to scope the cap - fail closed rather
        than let an untracked anonymous caller through for free.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 5

        assert would_exceed_assistant_limit(AnonymousUser(), ip_hash=None) is True

    def test_trial_anonymous_user_with_empty_ip_hash_exceeds(self, settings):
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 5

        assert would_exceed_assistant_limit(AnonymousUser(), ip_hash="") is True

    def test_trial_anonymous_users_other_ip_hash_rows_do_not_count(self, settings):
        """The trial cap is per-IP - another anonymous caller's usage
        must not count against this one, or one heavy IP would brick the
        trial for every other visitor.
        """
        settings.ASSISTANT_FREE_TRIAL_PER_DAY = 1
        LLMQuery.objects.create(
            ip_hash="other-ip-hash",
            ticker="PETR4",
            question="q",
            classification="on_topic",
        )

        assert (
            would_exceed_assistant_limit(AnonymousUser(), ip_hash="my-ip-hash")
            is False
        )

    def test_unknown_tier_exceeds(self):
        """would_exceed_assistant_limit must be total: any tier string it
        doesn't explicitly recognize fails closed (True) rather than
        falling through to an implicit `None`, which is falsy and would
        have silently let an unrecognized/future tier through for free.
        """
        with patch(
            "assistant.assistant_quota.assistant_access_tier",
            return_value="some_future_tier",
        ):
            assert would_exceed_assistant_limit(AnonymousUser()) is True
