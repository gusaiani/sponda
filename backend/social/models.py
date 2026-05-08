"""Social models: Sponds (posts), follows, mutes/blocks, likes, notifications.

Visibility rules live in :mod:`social.querysets` so every view filters
through the same code path. These models hold only the data; semantic
filtering is centralized.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


SPOND_BODY_MAX_LENGTH = 500
EDIT_WINDOW = timedelta(minutes=5)


# ─── Spond and its relation tables ────────────────────────────────────────────


class Spond(models.Model):
    """A user post, optionally tagged to a ticker and/or a parent Spond."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sponds",
    )
    body = models.TextField()
    # Primary tagged ticker (the one the composer was scoped to). Ticker
    # mentions inside ``body`` go in :class:`SpondTickerMention` instead. We
    # store the symbol as a string rather than a Ticker FK because other
    # models in the codebase do the same (FavoriteCompany, IndicatorAlert),
    # and because the ticker may not yet exist in the Ticker table at the
    # moment of writing.
    ticker = models.CharField(max_length=10, blank=True, default="")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["ticker", "-created_at"]),
            models.Index(fields=["parent", "created_at"]),
            models.Index(
                fields=["-created_at"],
                name="spond_active_idx",
                condition=Q(deleted_at__isnull=True),
            ),
        ]

    def __str__(self):
        preview = self.body[:60] + "…" if len(self.body) > 60 else self.body
        return f"{self.author_id}: {preview}"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_within_edit_window(self) -> bool:
        return (timezone.now() - self.created_at) <= EDIT_WINDOW

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])


class SpondMention(models.Model):
    """A handle mentioned in a Spond's body. One row per (spond, user)."""

    spond = models.ForeignKey(
        Spond, on_delete=models.CASCADE, related_name="handle_mentions",
    )
    mentioned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentioned_in",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("spond", "mentioned_user")
        indexes = [models.Index(fields=["mentioned_user", "-created_at"])]


class SpondTickerMention(models.Model):
    """A ``$TICKER`` mention extracted from a Spond's body."""

    spond = models.ForeignKey(
        Spond, on_delete=models.CASCADE, related_name="ticker_mentions",
    )
    ticker = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("spond", "ticker")
        indexes = [models.Index(fields=["ticker", "-created_at"])]


class SpondLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    spond = models.ForeignKey(
        Spond, on_delete=models.CASCADE, related_name="likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "spond")
        indexes = [models.Index(fields=["spond", "-created_at"])]


# ─── Social graph: Follow / Mute / Block ──────────────────────────────────────


class Follow(models.Model):
    STATE_PENDING = "pending"
    STATE_ACCEPTED = "accepted"
    STATE_CHOICES = [
        (STATE_PENDING, "Pending"),
        (STATE_ACCEPTED, "Accepted"),
    ]

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_set",
    )
    followee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers_set",
    )
    state = models.CharField(
        max_length=10, choices=STATE_CHOICES, default=STATE_ACCEPTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("follower", "followee")
        indexes = [
            models.Index(fields=["followee", "state"]),
            models.Index(fields=["follower", "state"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(follower=F("followee")),
                name="follow_no_self",
            ),
        ]

    def accept(self):
        self.state = self.STATE_ACCEPTED
        self.accepted_at = timezone.now()
        self.save(update_fields=["state", "accepted_at"])


class _DirectedRelation(models.Model):
    """Abstract base for one-way (actor → target) user relations."""

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Mute(_DirectedRelation):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mutes",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="muted_by",
    )

    class Meta:
        unique_together = ("actor", "target")
        indexes = [models.Index(fields=["actor"])]


class Block(_DirectedRelation):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by",
    )

    class Meta:
        unique_together = ("actor", "target")
        indexes = [
            models.Index(fields=["actor"]),
            models.Index(fields=["target"]),
        ]


# ─── Notifications ────────────────────────────────────────────────────────────


class Notification(models.Model):
    VERB_FOLLOWED = "followed"
    VERB_FOLLOW_REQUESTED = "follow_requested"
    VERB_REPLIED = "replied"
    VERB_MENTIONED = "mentioned"
    VERB_LIKED = "liked"
    VERB_CHOICES = [
        (VERB_FOLLOWED, "Followed"),
        (VERB_FOLLOW_REQUESTED, "Follow requested"),
        (VERB_REPLIED, "Replied"),
        (VERB_MENTIONED, "Mentioned"),
        (VERB_LIKED, "Liked"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emitted_notifications",
    )
    verb = models.CharField(max_length=24, choices=VERB_CHOICES)

    # Generic FK to the target object (Spond, Follow, …). target_object_id is
    # a CharField because Spond's PK is a UUID and Follow's PK is an int.
    target_content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL,
    )
    target_object_id = models.CharField(max_length=64, null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(
                fields=["recipient", "-created_at"],
                name="notif_unread_idx",
                condition=Q(read_at__isnull=True),
            ),
        ]

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])
