"""Tests for assistant.assistant_quota - tier resolution and daily caps.

The tier resolver is the single seam the rest of the system reads from:
flipping a free trial on, adding paying users, or changing caps all happen
behind this one fuction. Tests pin the contract so callers (view, future
billing) can rely on it.
"""
import pytest

from assistant.assistant_quota import assistant_access_tier

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
        from django.contrib.auth.models import AnonymousUser

        assert assistant_access_tier(AnonymousUser()) == "denied"

    def test_paying_user_resolves_to_paying_tier(self, db):
        """When is_paying_user(user) is True, the resolver returns
        'paying'. We patch the stub so this test stays green even
        after a real Subscription model lands - the resolver's
        contract is what's being locked, not billing infrastructure.
        """
        from unittest.mock import patch
        from django.contrib.auth import get_user_model

        regular_user = get_user_model().objects.create_user(
            username = "paid@example.com",
            email = "paid@example.com",
            password = "pw123456",
        )

        with patch(
            "assistant.assistant_quota.is_paying_user",
            return_value=True,
        ):
            assert assistant_access_tier(regular_user) == "paying"