"""Tests for the centralized visibility helpers in social.querysets.

Covers the matrix of (viewer state) × (author state) × (relation) × (Spond
state) — what a viewer can and cannot see across blocks, mutes, private
accounts, and soft-deletes.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from social.models import Block, Follow, Mute, Spond
from social.querysets import is_user_visible, visible_sponds


User = get_user_model()


def _user(email, **kwargs):
    return User.objects.create_user(
        username=email, email=email, password="x",
        handle=email.split("@")[0], email_verified=True, **kwargs,
    )


@pytest.fixture
def alice(db):
    return _user("alice@x.com")


@pytest.fixture
def bob(db):
    return _user("bob@x.com")


@pytest.fixture
def carol(db):
    return _user("carol@x.com")


@pytest.fixture
def private_dave(db):
    return _user("dave@x.com", is_private=True)


# ─── Default (public) visibility ──────────────────────────────────────────────


@pytest.mark.django_db
class TestPublicVisibility:
    def test_authenticated_sees_public_spond(self, alice, bob):
        spond = Spond.objects.create(author=alice, body="hi")
        assert spond in visible_sponds(bob)

    def test_anonymous_sees_public_spond(self, alice):
        spond = Spond.objects.create(author=alice, body="hi")
        assert spond in visible_sponds(AnonymousUser())

    def test_anonymous_with_none_viewer(self, alice):
        spond = Spond.objects.create(author=alice, body="hi")
        assert spond in visible_sponds(None)

    def test_author_sees_own_spond(self, alice):
        spond = Spond.objects.create(author=alice, body="hi")
        assert spond in visible_sponds(alice)


# ─── Soft delete ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSoftDelete:
    def test_deleted_spond_hidden_from_everyone(self, alice, bob):
        spond = Spond.objects.create(author=alice, body="hi")
        spond.soft_delete()
        assert spond not in visible_sponds(bob)
        assert spond not in visible_sponds(alice)
        assert spond not in visible_sponds(AnonymousUser())


# ─── Mute (one-way) ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMute:
    def test_muted_authors_hidden_from_actor(self, alice, bob):
        spond = Spond.objects.create(author=bob, body="hi")
        Mute.objects.create(actor=alice, target=bob)
        assert spond not in visible_sponds(alice)

    def test_mute_does_not_affect_others(self, alice, bob, carol):
        spond = Spond.objects.create(author=bob, body="hi")
        Mute.objects.create(actor=alice, target=bob)
        # Carol still sees Bob; mute is one-way.
        assert spond in visible_sponds(carol)

    def test_mute_does_not_hide_target_from_self(self, alice, bob):
        spond = Spond.objects.create(author=bob, body="hi")
        Mute.objects.create(actor=alice, target=bob)
        # Bob still sees his own Spond.
        assert spond in visible_sponds(bob)


# ─── Block (symmetric in queries) ─────────────────────────────────────────────


@pytest.mark.django_db
class TestBlock:
    def test_actor_does_not_see_target(self, alice, bob):
        spond = Spond.objects.create(author=bob, body="hi")
        Block.objects.create(actor=alice, target=bob)
        assert spond not in visible_sponds(alice)

    def test_target_does_not_see_actor(self, alice, bob):
        spond = Spond.objects.create(author=alice, body="hi")
        Block.objects.create(actor=alice, target=bob)
        # Symmetry: Bob can't see Alice's Sponds either.
        assert spond not in visible_sponds(bob)

    def test_third_party_unaffected(self, alice, bob, carol):
        spond_alice = Spond.objects.create(author=alice, body="a")
        spond_bob = Spond.objects.create(author=bob, body="b")
        Block.objects.create(actor=alice, target=bob)
        # Carol sees both.
        assert spond_alice in visible_sponds(carol)
        assert spond_bob in visible_sponds(carol)


# ─── Private accounts ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPrivateAccount:
    def test_private_author_hidden_from_anonymous(self, private_dave):
        spond = Spond.objects.create(author=private_dave, body="hi")
        assert spond not in visible_sponds(AnonymousUser())

    def test_private_author_hidden_from_non_follower(self, private_dave, alice):
        spond = Spond.objects.create(author=private_dave, body="hi")
        assert spond not in visible_sponds(alice)

    def test_private_author_visible_to_self(self, private_dave):
        spond = Spond.objects.create(author=private_dave, body="hi")
        assert spond in visible_sponds(private_dave)

    def test_pending_follow_does_not_grant_visibility(
        self, private_dave, alice,
    ):
        spond = Spond.objects.create(author=private_dave, body="hi")
        Follow.objects.create(
            follower=alice, followee=private_dave, state=Follow.STATE_PENDING,
        )
        assert spond not in visible_sponds(alice)

    def test_accepted_follow_grants_visibility(self, private_dave, alice):
        spond = Spond.objects.create(author=private_dave, body="hi")
        Follow.objects.create(
            follower=alice, followee=private_dave, state=Follow.STATE_ACCEPTED,
        )
        assert spond in visible_sponds(alice)


# ─── User profile visibility ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestIsUserVisible:
    def test_public_user_visible_to_anyone(self, alice, bob):
        assert is_user_visible(bob, alice)
        assert is_user_visible(AnonymousUser(), alice)
        assert is_user_visible(None, alice)

    def test_blocker_invisible_to_blocked(self, alice, bob):
        Block.objects.create(actor=alice, target=bob)
        # Bob views Alice — hidden.
        assert not is_user_visible(bob, alice)

    def test_blocked_invisible_to_blocker(self, alice, bob):
        Block.objects.create(actor=alice, target=bob)
        assert not is_user_visible(alice, bob)

    def test_private_visible_to_follower(self, private_dave, alice):
        Follow.objects.create(
            follower=alice, followee=private_dave, state=Follow.STATE_ACCEPTED,
        )
        assert is_user_visible(alice, private_dave)

    def test_private_invisible_to_non_follower(self, private_dave, alice):
        assert not is_user_visible(alice, private_dave)

    def test_private_visible_to_self(self, private_dave):
        assert is_user_visible(private_dave, private_dave)

    def test_private_invisible_to_anonymous(self, private_dave):
        assert not is_user_visible(AnonymousUser(), private_dave)
