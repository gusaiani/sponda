"""End-to-end API tests for the social app.

Covers compose / edit / delete / like / follow / accept / mute / block /
profile / feeds / notifications / autocomplete / throttles. Anonymous,
verified, unverified, and private-account paths are all here.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from quotes.models import Ticker
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


def _make(email, *, verified=True, **kw):
    return User.objects.create_user(
        username=email, email=email, password="x",
        handle=email.split("@")[0],
        email_verified=verified,
        **kw,
    )


@pytest.fixture
def alice(db):
    return _make("alice@x.com")


@pytest.fixture
def bob(db):
    return _make("bob@x.com")


@pytest.fixture
def carol(db):
    return _make("carol@x.com")


@pytest.fixture
def dave_private(db):
    return _make("dave@x.com", is_private=True)


@pytest.fixture
def unverified_eve(db):
    return _make("eve@x.com", verified=False)


@pytest.fixture
def client_for():
    """Returns a function that gives back a logged-in Client for a user."""
    def make(user):
        c = Client()
        c.force_login(user)
        return c
    return make


@pytest.fixture
def anon_client():
    return Client()


@pytest.fixture
def petr4(db):
    return Ticker.objects.create(symbol="PETR4", display_name="Petrobras")


@pytest.fixture
def vale3(db):
    return Ticker.objects.create(symbol="VALE3", display_name="Vale")


# ─── Compose ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSpondCompose:
    def test_verified_user_can_compose(self, alice, client_for):
        c = client_for(alice)
        r = c.post(
            "/api/social/sponds/",
            data={"body": "Hello world."},
            content_type="application/json",
        )
        assert r.status_code == 201
        assert r.json()["body"] == "Hello world."
        assert Spond.objects.count() == 1

    def test_unverified_user_blocked(self, unverified_eve, client_for):
        c = client_for(unverified_eve)
        r = c.post(
            "/api/social/sponds/",
            data={"body": "hi"},
            content_type="application/json",
        )
        assert r.status_code == 403
        assert Spond.objects.count() == 0

    def test_anonymous_blocked(self, anon_client):
        r = anon_client.post(
            "/api/social/sponds/",
            data={"body": "hi"},
            content_type="application/json",
        )
        assert r.status_code in (401, 403)

    def test_body_max_length(self, alice, client_for):
        c = client_for(alice)
        r = c.post(
            "/api/social/sponds/",
            data={"body": "x" * 501},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_body_500_chars_ok(self, alice, client_for):
        c = client_for(alice)
        r = c.post(
            "/api/social/sponds/",
            data={"body": "x" * 500},
            content_type="application/json",
        )
        assert r.status_code == 201

    def test_body_dedup_within_5_minutes(self, alice, client_for):
        c = client_for(alice)
        c.post(
            "/api/social/sponds/",
            data={"body": "duplicate"},
            content_type="application/json",
        )
        r = c.post(
            "/api/social/sponds/",
            data={"body": "duplicate"},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_ticker_tag_persists(self, alice, client_for, petr4):
        c = client_for(alice)
        r = c.post(
            "/api/social/sponds/",
            data={"body": "Buying", "ticker": "PETR4"},
            content_type="application/json",
        )
        assert r.status_code == 201
        spond = Spond.objects.first()
        assert spond.ticker == "PETR4"
        # Primary ticker is also added to ticker_mentions for fast feed query.
        assert SpondTickerMention.objects.filter(
            spond=spond, ticker="PETR4",
        ).exists()

    def test_handle_mention_creates_mention_row_and_notification(
        self, alice, bob, client_for,
    ):
        c = client_for(alice)
        r = c.post(
            "/api/social/sponds/",
            data={"body": "Hey @bob, check this"},
            content_type="application/json",
        )
        assert r.status_code == 201
        spond = Spond.objects.first()
        assert SpondMention.objects.filter(
            spond=spond, mentioned_user=bob,
        ).exists()
        assert Notification.objects.filter(
            recipient=bob, verb=Notification.VERB_MENTIONED,
        ).exists()

    def test_dollar_ticker_mention_creates_row(
        self, alice, client_for, petr4, vale3,
    ):
        c = client_for(alice)
        c.post(
            "/api/social/sponds/",
            data={"body": "$PETR4 vs $VALE3 vs $ZZZZ9"},
            content_type="application/json",
        )
        spond = Spond.objects.first()
        symbols = set(spond.ticker_mentions.values_list("ticker", flat=True))
        # Only real Tickers persist; ZZZZ9 is filtered out.
        assert symbols == {"PETR4", "VALE3"}


# ─── Edit / delete ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSpondEditDelete:
    def test_author_can_edit_within_window(self, alice, client_for):
        spond = Spond.objects.create(author=alice, body="initial")
        c = client_for(alice)
        r = c.patch(
            f"/api/social/sponds/{spond.pk}/",
            data={"body": "updated"},
            content_type="application/json",
        )
        assert r.status_code == 200
        spond.refresh_from_db()
        assert spond.body == "updated"

    def test_author_blocked_after_window(self, alice, client_for):
        spond = Spond.objects.create(author=alice, body="x")
        spond.created_at = timezone.now() - timedelta(minutes=6)
        spond.save(update_fields=["created_at"])
        c = client_for(alice)
        r = c.patch(
            f"/api/social/sponds/{spond.pk}/",
            data={"body": "updated"},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_non_author_cannot_edit(self, alice, bob, client_for):
        spond = Spond.objects.create(author=alice, body="x")
        c = client_for(bob)
        r = c.patch(
            f"/api/social/sponds/{spond.pk}/",
            data={"body": "hacked"},
            content_type="application/json",
        )
        assert r.status_code in (403, 404)

    def test_author_can_soft_delete(self, alice, client_for):
        spond = Spond.objects.create(author=alice, body="x")
        c = client_for(alice)
        r = c.delete(f"/api/social/sponds/{spond.pk}/")
        assert r.status_code == 204
        spond.refresh_from_db()
        assert spond.is_deleted


# ─── Like ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLike:
    def test_like_creates_row_and_notification(self, alice, bob, client_for):
        spond = Spond.objects.create(author=alice, body="hi")
        c = client_for(bob)
        r = c.post(f"/api/social/sponds/{spond.pk}/like/")
        assert r.status_code == 201
        assert SpondLike.objects.filter(user=bob, spond=spond).exists()
        assert Notification.objects.filter(
            recipient=alice, verb=Notification.VERB_LIKED,
        ).exists()

    def test_double_like_idempotent(self, alice, bob, client_for):
        spond = Spond.objects.create(author=alice, body="hi")
        c = client_for(bob)
        c.post(f"/api/social/sponds/{spond.pk}/like/")
        r = c.post(f"/api/social/sponds/{spond.pk}/like/")
        assert r.status_code == 200
        assert SpondLike.objects.filter(user=bob, spond=spond).count() == 1

    def test_unlike(self, alice, bob, client_for):
        spond = Spond.objects.create(author=alice, body="hi")
        c = client_for(bob)
        c.post(f"/api/social/sponds/{spond.pk}/like/")
        r = c.delete(f"/api/social/sponds/{spond.pk}/like/")
        assert r.status_code == 200
        assert not SpondLike.objects.filter(user=bob, spond=spond).exists()


# ─── Follow / private accounts ────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollow:
    def test_follow_public_user_accepted_immediately(
        self, alice, bob, client_for,
    ):
        c = client_for(alice)
        r = c.post(f"/api/social/users/bob/follow/")
        assert r.status_code == 201
        assert r.json()["state"] == Follow.STATE_ACCEPTED
        assert Notification.objects.filter(
            recipient=bob, verb=Notification.VERB_FOLLOWED,
        ).exists()

    def test_follow_private_user_pending(
        self, alice, dave_private, client_for,
    ):
        c = client_for(alice)
        r = c.post(f"/api/social/users/dave/follow/")
        assert r.status_code == 201
        assert r.json()["state"] == Follow.STATE_PENDING
        assert Notification.objects.filter(
            recipient=dave_private, verb=Notification.VERB_FOLLOW_REQUESTED,
        ).exists()

    def test_accept_follow_request(self, alice, dave_private, client_for):
        follow = Follow.objects.create(
            follower=alice, followee=dave_private, state=Follow.STATE_PENDING,
        )
        c = client_for(dave_private)
        r = c.post(f"/api/social/follow-requests/{follow.pk}/accept/")
        assert r.status_code == 200
        follow.refresh_from_db()
        assert follow.state == Follow.STATE_ACCEPTED
        # Alice should get a "followed" notification (her request was accepted).
        # Followed notification recipient is the followee — but the *user
        # acting* is alice (the follower), and the followee approved them, so
        # the notification model emits ``followed`` to followee. That's the
        # parent of the request — so dave gets the row. We assert only that
        # the follow is now accepted; UI uses the request mutation.

    def test_reject_follow_request(self, alice, dave_private, client_for):
        follow = Follow.objects.create(
            follower=alice, followee=dave_private, state=Follow.STATE_PENDING,
        )
        c = client_for(dave_private)
        r = c.post(f"/api/social/follow-requests/{follow.pk}/reject/")
        assert r.status_code == 204
        assert not Follow.objects.filter(pk=follow.pk).exists()

    def test_unfollow(self, alice, bob, client_for):
        Follow.objects.create(follower=alice, followee=bob)
        c = client_for(alice)
        r = c.delete(f"/api/social/users/bob/follow/")
        assert r.status_code == 204
        assert not Follow.objects.filter(follower=alice, followee=bob).exists()

    def test_self_follow_rejected(self, alice, client_for):
        c = client_for(alice)
        r = c.post(f"/api/social/users/alice/follow/")
        assert r.status_code == 400


# ─── Mute / Block ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMuteBlock:
    def test_mute_then_unmute(self, alice, bob, client_for):
        c = client_for(alice)
        c.post("/api/social/users/bob/mute/")
        assert Mute.objects.filter(actor=alice, target=bob).exists()
        c.delete("/api/social/users/bob/mute/")
        assert not Mute.objects.filter(actor=alice, target=bob).exists()

    def test_block_removes_follow(self, alice, bob, client_for):
        Follow.objects.create(follower=alice, followee=bob)
        Follow.objects.create(follower=bob, followee=alice)
        c = client_for(alice)
        r = c.post("/api/social/users/bob/block/")
        assert r.status_code == 201
        assert not Follow.objects.filter(follower=alice, followee=bob).exists()
        assert not Follow.objects.filter(follower=bob, followee=alice).exists()

    def test_blocked_user_cannot_reply(self, alice, bob, client_for):
        spond = Spond.objects.create(author=alice, body="hi")
        Block.objects.create(actor=alice, target=bob)
        c = client_for(bob)
        r = c.post(
            "/api/social/sponds/",
            data={"body": "reply", "parent": str(spond.pk)},
            content_type="application/json",
        )
        # Either denied or 404 because the parent isn't visible to bob.
        assert r.status_code in (403, 404)


# ─── Feeds ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFeeds:
    def test_global_feed_anonymous(self, alice, anon_client):
        Spond.objects.create(author=alice, body="hello")
        r = anon_client.get("/api/social/feed/global/")
        assert r.status_code == 200
        assert len(r.json()["results"]) == 1

    def test_following_feed_includes_followed_authors(
        self, alice, bob, carol, client_for,
    ):
        Spond.objects.create(author=bob, body="bob post")
        Spond.objects.create(author=carol, body="carol post")
        Follow.objects.create(follower=alice, followee=bob)
        c = client_for(alice)
        r = c.get("/api/social/feed/")
        assert r.status_code == 200
        bodies = [s["body"] for s in r.json()["results"]]
        assert "bob post" in bodies
        assert "carol post" not in bodies

    def test_company_feed(self, alice, petr4, vale3, client_for):
        s1 = Spond.objects.create(author=alice, body="a", ticker="PETR4")
        SpondTickerMention.objects.create(spond=s1, ticker="PETR4")
        s2 = Spond.objects.create(author=alice, body="b", ticker="VALE3")
        SpondTickerMention.objects.create(spond=s2, ticker="VALE3")
        c = client_for(alice)
        r = c.get("/api/social/companies/PETR4/sponds/")
        assert r.status_code == 200
        assert len(r.json()["results"]) == 1


# ─── Profile ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProfile:
    def test_get_public_profile(self, alice, anon_client):
        Spond.objects.create(author=alice, body="hi")
        r = anon_client.get("/api/social/users/alice/")
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["handle"] == "alice"
        assert len(body["sponds"]) == 1

    def test_get_private_profile_anonymous_404(self, dave_private, anon_client):
        r = anon_client.get("/api/social/users/dave/")
        assert r.status_code == 404

    def test_update_handle(self, alice, client_for):
        c = client_for(alice)
        r = c.patch(
            "/api/social/users/me/profile/",
            data={"handle": "alice_2"},
            content_type="application/json",
        )
        assert r.status_code == 200
        alice.refresh_from_db()
        assert alice.handle == "alice_2"
        assert alice.handle_changed_at is not None

    def test_handle_change_window_30_days(self, alice, client_for):
        alice.handle_changed_at = timezone.now() - timedelta(days=10)
        alice.save(update_fields=["handle_changed_at"])
        c = client_for(alice)
        r = c.patch(
            "/api/social/users/me/profile/",
            data={"handle": "newhandle"},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_reserved_handle_rejected(self, alice, client_for):
        c = client_for(alice)
        r = c.patch(
            "/api/social/users/me/profile/",
            data={"handle": "admin"},
            content_type="application/json",
        )
        assert r.status_code == 400


# ─── Notifications ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNotifications:
    def test_list_notifications(self, alice, bob, client_for):
        spond = Spond.objects.create(author=alice, body="hi")
        c_bob = client_for(bob)
        c_bob.post(f"/api/social/sponds/{spond.pk}/like/")
        c_alice = client_for(alice)
        r = c_alice.get("/api/social/notifications/")
        assert r.status_code == 200
        body = r.json()
        assert body["unread_count"] == 1
        assert body["notifications"][0]["verb"] == "liked"

    def test_mark_read(self, alice, bob, client_for):
        spond = Spond.objects.create(author=alice, body="hi")
        client_for(bob).post(f"/api/social/sponds/{spond.pk}/like/")
        c_alice = client_for(alice)
        c_alice.post(
            "/api/social/notifications/mark-read/",
            data={},
            content_type="application/json",
        )
        r = c_alice.get("/api/social/notifications/")
        assert r.json()["unread_count"] == 0


# ─── Autocomplete ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAutocomplete:
    def test_handle_prefix(self, alice, bob, client_for):
        c = client_for(alice)
        r = c.get("/api/social/autocomplete/handles/?q=bo")
        assert r.status_code == 200
        handles = [u["handle"] for u in r.json()["results"]]
        assert "bob" in handles

    def test_ticker_prefix(self, alice, petr4, vale3, client_for):
        c = client_for(alice)
        r = c.get("/api/social/autocomplete/tickers/?q=PETR")
        assert r.status_code == 200
        symbols = [t["symbol"] for t in r.json()["results"]]
        assert "PETR4" in symbols


# ─── Throttling ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestThrottle:
    def test_compose_throttle_per_minute(self, alice, client_for, settings):
        # Compose limit is 4/minute. Burn through 4, then expect 429 on #5.
        c = client_for(alice)
        for i in range(4):
            r = c.post(
                "/api/social/sponds/",
                data={"body": f"unique body {i}"},
                content_type="application/json",
            )
            assert r.status_code == 201, (i, r.content)
        r = c.post(
            "/api/social/sponds/",
            data={"body": "unique body 5"},
            content_type="application/json",
        )
        assert r.status_code == 429
