"""Serializers for the social API."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.handles import (
    HandleValidationError,
    is_valid_handle,
    validate_handle,
)
from social.mentions import MENTION_LIMIT_PER_SPOND, extract_handle_mentions
from social.models import (
    SPOND_BODY_MAX_LENGTH,
    Follow,
    Notification,
    Spond,
    SpondLike,
)


User = get_user_model()


# ─── Public user shapes ───────────────────────────────────────────────────────


class PublicUserSerializer(serializers.ModelSerializer):
    """Minimal author/profile shape returned everywhere a user appears."""

    class Meta:
        model = User
        fields = ("handle", "display_name", "bio", "is_private")
        read_only_fields = fields


# ─── Spond ────────────────────────────────────────────────────────────────────


class SpondSerializer(serializers.ModelSerializer):
    """Read shape: includes derived fields (like_count, viewer_has_liked)."""

    author = PublicUserSerializer(read_only=True)
    like_count = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    viewer_has_liked = serializers.SerializerMethodField()
    is_within_edit_window = serializers.BooleanField(read_only=True)
    parent = serializers.UUIDField(source="parent_id", read_only=True, allow_null=True)
    ticker_mentions = serializers.SerializerMethodField()
    handle_mentions = serializers.SerializerMethodField()

    class Meta:
        model = Spond
        fields = (
            "id",
            "author",
            "body",
            "ticker",
            "parent",
            "created_at",
            "updated_at",
            "is_within_edit_window",
            "like_count",
            "reply_count",
            "viewer_has_liked",
            "ticker_mentions",
            "handle_mentions",
        )
        read_only_fields = fields

    def get_like_count(self, obj):
        return getattr(obj, "annotated_like_count", obj.likes.count())

    def get_reply_count(self, obj):
        return getattr(
            obj, "annotated_reply_count",
            obj.replies.filter(deleted_at__isnull=True).count(),
        )

    def get_viewer_has_liked(self, obj):
        viewer = self.context.get("viewer")
        if viewer is None or not viewer.is_authenticated:
            return False
        return SpondLike.objects.filter(user=viewer, spond=obj).exists()

    def get_ticker_mentions(self, obj):
        return [m.ticker for m in obj.ticker_mentions.all()]

    def get_handle_mentions(self, obj):
        return [
            m.mentioned_user.handle
            for m in obj.handle_mentions.select_related("mentioned_user")
            if m.mentioned_user.handle
        ]


class SpondCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=SPOND_BODY_MAX_LENGTH, allow_blank=False)
    ticker = serializers.CharField(
        max_length=10, required=False, allow_blank=True, default="",
    )
    parent = serializers.UUIDField(required=False, allow_null=True)

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Body cannot be empty.")
        # Mention bombs: cap at MENTION_LIMIT_PER_SPOND distinct handles.
        # The parser already truncates, but also catch the case where the
        # raw body has many @-tokens past the limit.
        if len(extract_handle_mentions(value)) > MENTION_LIMIT_PER_SPOND:
            # Defensive — extract_handle_mentions should already cap.
            raise serializers.ValidationError(
                f"At most {MENTION_LIMIT_PER_SPOND} mentions per Spond.",
            )
        return value

    def validate_ticker(self, value):
        return value.strip().upper()


class SpondEditSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=SPOND_BODY_MAX_LENGTH, allow_blank=False)

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Body cannot be empty.")
        return value


# ─── Profile edit ─────────────────────────────────────────────────────────────


class ProfileUpdateSerializer(serializers.Serializer):
    """Partial update — every field is optional. Empty strings clear bio /
    display_name; ``None`` is rejected to avoid ambiguity with "missing"."""

    handle = serializers.CharField(required=False, allow_blank=False)
    display_name = serializers.CharField(
        max_length=64, required=False, allow_blank=True,
    )
    bio = serializers.CharField(max_length=160, required=False, allow_blank=True)
    is_private = serializers.BooleanField(required=False)

    def validate_handle(self, value):
        try:
            validate_handle(value)
        except HandleValidationError as exc:
            raise serializers.ValidationError(str(exc))
        # Uniqueness — case-insensitive comparison, exclude self.
        user = self.context["user"]
        if User.objects.exclude(pk=user.pk).filter(handle=value).exists():
            raise serializers.ValidationError("That handle is taken.")
        return value


# ─── Notification ─────────────────────────────────────────────────────────────


class NotificationSerializer(serializers.ModelSerializer):
    actor = PublicUserSerializer(read_only=True)
    target_id = serializers.SerializerMethodField()
    target_type = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id", "verb", "actor", "target_type", "target_id",
            "read_at", "created_at",
        )
        read_only_fields = fields

    def get_target_id(self, obj):
        return obj.target_object_id

    def get_target_type(self, obj):
        ct = obj.target_content_type
        return ct.model if ct else None


# ─── Follow request listing ───────────────────────────────────────────────────


class FollowRequestSerializer(serializers.ModelSerializer):
    follower = PublicUserSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ("id", "follower", "state", "created_at")
        read_only_fields = fields
