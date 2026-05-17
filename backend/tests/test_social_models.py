"""Model-level tests for the social app: Spond, Follow, Mute, Block,
SpondLike, Notification."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from social.models import (
    Block,
    Follow,
    Mute,
    Notification,
    Spond,
    SpondLike,
    SpondMention,
    SpondTickerMention,
)


User = get_user_model()


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def alice(db):
    return User.objects.create_user(
        username="alice@x.com", email="alice@x.com", password="x",
        handle="alice", email_verified=True,
    )


@pytest.fixture
def bob(db):
    return User.objects.create_user(
        username="bob@x.com", email="bob@x.com", password="x",
        handle="bob", email_verified=True,
    )


@pytest.fixture
def carol(db):
    return User.objects.create_user(
        username="carol@x.com", email="carol@x.com", password="x",
        handle="carol", email_verified=True,
    )


# ─── Spond ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSpond:
    def test_create_simple_spond(self, alice):
        spond = Spond.objects.create(author=alice, body="Hello world.")
        assert spond.id is not None  # UUID assigned
        assert spond.body == "Hello world."
        assert spond.deleted_at is None
        assert spond.parent is None
        assert spond.ticker == ""
        assert spond.created_at is not None

    def test_uuid_primary_key(self, alice):
        s1 = Spond.objects.create(author=alice, body="a")
        s2 = Spond.objects.create(author=alice, body="b")
        # IDs are random UUIDs, not sequential ints.
        assert s1.id != s2.id
        assert hasattr(s1.id, "hex")  # uuid.UUID

    def test_soft_delete(self, alice):
        spond = Spond.objects.create(author=alice, body="Hi")
        assert not spond.is_deleted
        spond.soft_delete()
        spond.refresh_from_db()
        assert spond.is_deleted
        assert spond.deleted_at is not None

    def test_edit_window_within_5_minutes(self, alice):
        spond = Spond.objects.create(author=alice, body="Hi")
        assert spond.is_within_edit_window
        # Simulate a 6-minute-old Spond.
        spond.created_at = timezone.now() - timedelta(minutes=6)
        spond.save(update_fields=["created_at"])
        assert not spond.is_within_edit_window

    def test_reply_chain_one_level(self, alice, bob):
        parent = Spond.objects.create(author=alice, body="What do you think?")
        reply = Spond.objects.create(
            author=bob, body="Looks great", parent=parent,
        )
        assert reply.parent_id == parent.id
        assert list(parent.replies.all()) == [reply]

    def test_ticker_field(self, alice):
        spond = Spond.objects.create(author=alice, body="Buying", ticker="PETR4")
        assert spond.ticker == "PETR4"


# ─── SpondMention / SpondTickerMention ────────────────────────────────────────


@pytest.mark.django_db
class TestMentionTables:
    def test_handle_mention_unique(self, alice, bob):
        spond = Spond.objects.create(author=alice, body="@bob hi")
        SpondMention.objects.create(spond=spond, mentioned_user=bob)
        with pytest.raises(IntegrityError):
            SpondMention.objects.create(spond=spond, mentioned_user=bob)

    def test_ticker_mention_unique(self, alice):
        spond = Spond.objects.create(author=alice, body="$PETR4")
        SpondTickerMention.objects.create(spond=spond, ticker="PETR4")
        with pytest.raises(IntegrityError):
            SpondTickerMention.objects.create(spond=spond, ticker="PETR4")


# ─── SpondLike ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSpondLike:
    def test_like_unique_per_user_spond(self, alice, bob):
        spond = Spond.objects.create(author=alice, body="hi")
        SpondLike.objects.create(user=bob, spond=spond)
        with pytest.raises(IntegrityError):
            SpondLike.objects.create(user=bob, spond=spond)

    def test_user_can_like_own(self, alice):
        spond = Spond.objects.create(author=alice, body="hi")
        like = SpondLike.objects.create(user=alice, spond=spond)
        assert like.id is not None


# ─── Follow ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollow:
    def test_default_state_accepted(self, alice, bob):
        f = Follow.objects.create(follower=alice, followee=bob)
        assert f.state == Follow.STATE_ACCEPTED

    def test_pending_state(self, alice, bob):
        f = Follow.objects.create(
            follower=alice, followee=bob, state=Follow.STATE_PENDING,
        )
        assert f.state == Follow.STATE_PENDING

    def test_unique_pair(self, alice, bob):
        Follow.objects.create(follower=alice, followee=bob)
        with pytest.raises(IntegrityError):
            Follow.objects.create(follower=alice, followee=bob)

    def test_self_follow_rejected(self, alice):
        with pytest.raises(IntegrityError):
            Follow.objects.create(follower=alice, followee=alice)

    def test_accept_pending_sets_timestamp(self, alice, bob):
        f = Follow.objects.create(
            follower=alice, followee=bob, state=Follow.STATE_PENDING,
        )
        assert f.accepted_at is None
        f.accept()
        f.refresh_from_db()
        assert f.state == Follow.STATE_ACCEPTED
        assert f.accepted_at is not None


# ─── Mute / Block ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMute:
    def test_unique_pair(self, alice, bob):
        Mute.objects.create(actor=alice, target=bob)
        with pytest.raises(IntegrityError):
            Mute.objects.create(actor=alice, target=bob)

    def test_independent_directions(self, alice, bob):
        Mute.objects.create(actor=alice, target=bob)
        Mute.objects.create(actor=bob, target=alice)  # OK; one-way each


@pytest.mark.django_db
class TestBlock:
    def test_unique_pair(self, alice, bob):
        Block.objects.create(actor=alice, target=bob)
        with pytest.raises(IntegrityError):
            Block.objects.create(actor=alice, target=bob)


# ─── Notification ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNotification:
    def test_create_notification_pointing_to_spond(self, alice, bob):
        spond = Spond.objects.create(author=alice, body="hi")
        notif = Notification.objects.create(
            recipient=alice,
            actor=bob,
            verb=Notification.VERB_LIKED,
            target=spond,
        )
        assert notif.read_at is None
        assert notif.target == spond

    def test_mark_read(self, alice, bob):
        spond = Spond.objects.create(author=alice, body="hi")
        notif = Notification.objects.create(
            recipient=alice,
            actor=bob,
            verb=Notification.VERB_LIKED,
            target=spond,
        )
        notif.mark_read()
        notif.refresh_from_db()
        assert notif.read_at is not None
