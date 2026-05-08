"""DRF views for the social API.

Reads use ``visible_sponds`` / ``is_user_visible`` for centralized filtering.
Writes are gated by :class:`IsEmailVerified` and stacked rate-limit
throttles; mention/ticker extraction and notification fan-out happen inside
the create transaction.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, Throttled, ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from accounts.handles import validate_handle, HandleValidationError
from quotes.models import Ticker as TickerModel
from social import notifications, throttles
from social.mentions import extract_handle_mentions, extract_ticker_mentions
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
from social.permissions import IsAuthorOrReadOnly, IsEmailVerified
from social.querysets import is_user_visible, visible_sponds
from social.serializers import (
    FollowRequestSerializer,
    NotificationSerializer,
    ProfileUpdateSerializer,
    PublicUserSerializer,
    SpondCreateSerializer,
    SpondEditSerializer,
    SpondSerializer,
)


User = get_user_model()


_DEDUP_WINDOW = timedelta(minutes=5)
_FOLLOW_HOURLY_BURST_LIMIT = 20


def _serializer_context(request):
    """The viewer is the authenticated user, or ``None`` for anonymous."""
    user = request.user if request.user.is_authenticated else None
    return {"viewer": user, "request": request}


def _annotate_sponds(qs):
    return qs.select_related("author").prefetch_related(
        "ticker_mentions", "handle_mentions__mentioned_user",
    ).annotate(
        annotated_like_count=Count("likes", distinct=True),
        annotated_reply_count=Count(
            "replies",
            filter=Q(replies__deleted_at__isnull=True),
            distinct=True,
        ),
    )


# ─── Pagination ───────────────────────────────────────────────────────────────


class SpondCursorPagination(CursorPagination):
    page_size = 25
    max_page_size = 100
    ordering = "-created_at"
    cursor_query_param = "cursor"


# ─── Spond CRUD + Like ────────────────────────────────────────────────────────


class SpondCreateView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = throttles.SPOND_WRITE_THROTTLES

    def post(self, request):
        ser = SpondCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        body = ser.validated_data["body"]
        ticker = ser.validated_data.get("ticker", "") or ""
        parent_id = ser.validated_data.get("parent")

        self._enforce_dedup(request.user, body)

        parent = None
        if parent_id is not None:
            parent = get_object_or_404(Spond, pk=parent_id, deleted_at__isnull=True)
            # Block check on the parent's author.
            if Block.objects.filter(
                Q(actor=parent.author, target=request.user)
                | Q(actor=request.user, target=parent.author),
            ).exists():
                raise PermissionDenied("You cannot reply to this Spond.")

        with transaction.atomic():
            spond = Spond.objects.create(
                author=request.user,
                body=body,
                ticker=ticker,
                parent=parent,
            )
            self._persist_mentions(spond, body)
            if parent is not None:
                notifications.notify_replied(spond)

        out = SpondSerializer(
            _annotate_sponds(Spond.objects.filter(pk=spond.pk)).first(),
            context=_serializer_context(request),
        )
        return Response(out.data, status=status.HTTP_201_CREATED)

    def _enforce_dedup(self, user, body):
        cutoff = timezone.now() - _DEDUP_WINDOW
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        recent = (
            Spond.objects.filter(
                author=user, deleted_at__isnull=True, created_at__gte=cutoff,
            )
            .values_list("body", flat=True)
        )
        for existing in recent:
            if hashlib.sha256(existing.encode("utf-8")).hexdigest() == body_hash:
                raise ValidationError({
                    "body": "You just posted this. Wait a few minutes before reposting.",
                })

    def _persist_mentions(self, spond, body):
        # Handle mentions: only persist the ones that resolve to a real,
        # non-blocked User. We notify each.
        handles = extract_handle_mentions(body)
        if handles:
            users = list(User.objects.filter(handle__in=handles))
            mentions = [
                SpondMention(spond=spond, mentioned_user=u) for u in users
            ]
            SpondMention.objects.bulk_create(mentions, ignore_conflicts=True)
            notifications.notify_mentioned(spond, users)

        tickers = extract_ticker_mentions(body)
        # Also include the primary ``ticker`` field so the per-ticker feed
        # finds replies that don't otherwise mention the symbol.
        if spond.ticker:
            if spond.ticker not in tickers:
                tickers = [spond.ticker] + tickers
        if tickers:
            existing_symbols = set(
                TickerModel.objects.filter(symbol__in=tickers)
                .values_list("symbol", flat=True),
            )
            rows = [
                SpondTickerMention(spond=spond, ticker=t)
                for t in tickers if t in existing_symbols
            ]
            if rows:
                SpondTickerMention.objects.bulk_create(rows, ignore_conflicts=True)


class SpondDetailView(APIView):
    permission_classes = [IsAuthorOrReadOnly]

    def get_throttles(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [t() for t in throttles.SPOND_WRITE_THROTTLES]
        return [t() for t in throttles.SOCIAL_READ_THROTTLES]

    def get(self, request, pk):
        viewer = request.user if request.user.is_authenticated else None
        spond = get_object_or_404(_annotate_sponds(visible_sponds(viewer)), pk=pk)
        replies = _annotate_sponds(
            visible_sponds(viewer).filter(parent_id=spond.pk),
        ).order_by("created_at")
        ctx = _serializer_context(request)
        return Response({
            "spond": SpondSerializer(spond, context=ctx).data,
            "replies": SpondSerializer(replies, many=True, context=ctx).data,
        })

    def patch(self, request, pk):
        spond = get_object_or_404(Spond, pk=pk, deleted_at__isnull=True)
        self.check_object_permissions(request, spond)
        if not getattr(request.user, "email_verified", False):
            raise PermissionDenied(IsEmailVerified.message)
        if not spond.is_within_edit_window:
            raise ValidationError({
                "detail": "Edit window has expired.",
                "code": "EDIT_WINDOW_EXPIRED",
            })
        ser = SpondEditSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        spond.body = ser.validated_data["body"]
        spond.save(update_fields=["body", "updated_at"])
        out = SpondSerializer(
            _annotate_sponds(Spond.objects.filter(pk=spond.pk)).first(),
            context=_serializer_context(request),
        )
        return Response(out.data)

    def delete(self, request, pk):
        spond = get_object_or_404(Spond, pk=pk, deleted_at__isnull=True)
        self.check_object_permissions(request, spond)
        if not getattr(request.user, "email_verified", False):
            raise PermissionDenied(IsEmailVerified.message)
        spond.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SpondLikeView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = throttles.SPOND_LIKE_THROTTLES

    def post(self, request, pk):
        viewer = request.user
        spond = get_object_or_404(visible_sponds(viewer), pk=pk)
        like, created = SpondLike.objects.get_or_create(user=viewer, spond=spond)
        if created:
            notifications.notify_liked(like)
        return Response(
            {"liked": True, "like_count": spond.likes.count()},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        viewer = request.user
        spond = get_object_or_404(Spond, pk=pk)
        SpondLike.objects.filter(user=viewer, spond=spond).delete()
        return Response({"liked": False, "like_count": spond.likes.count()})


# ─── Feeds ────────────────────────────────────────────────────────────────────


class FollowingFeedView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = throttles.SOCIAL_READ_THROTTLES
    pagination_class = SpondCursorPagination

    def get(self, request):
        viewer = request.user
        following_ids = set(
            Follow.objects.filter(
                follower=viewer, state=Follow.STATE_ACCEPTED,
            ).values_list("followee_id", flat=True),
        )
        following_ids.add(viewer.id)
        qs = visible_sponds(viewer).filter(
            author_id__in=following_ids, parent__isnull=True,
        )
        return _paginated_spond_response(qs, request)


class GlobalFeedView(APIView):
    throttle_classes = throttles.SOCIAL_READ_THROTTLES
    pagination_class = SpondCursorPagination

    def get(self, request):
        viewer = request.user if request.user.is_authenticated else None
        qs = visible_sponds(viewer).filter(parent__isnull=True)
        return _paginated_spond_response(qs, request)


class CompanyFeedView(APIView):
    throttle_classes = throttles.SOCIAL_READ_THROTTLES
    pagination_class = SpondCursorPagination

    def get(self, request, symbol):
        symbol = symbol.upper()
        viewer = request.user if request.user.is_authenticated else None
        qs = visible_sponds(viewer).filter(
            Q(ticker=symbol) | Q(ticker_mentions__ticker=symbol),
        ).distinct()
        return _paginated_spond_response(qs, request)


def _paginated_spond_response(qs, request):
    qs = _annotate_sponds(qs)
    paginator = SpondCursorPagination()
    page = paginator.paginate_queryset(qs, request)
    ctx = _serializer_context(request)
    return paginator.get_paginated_response(
        SpondSerializer(page, many=True, context=ctx).data,
    )


# ─── Profiles ────────────────────────────────────────────────────────────────


class UserProfileView(APIView):
    throttle_classes = throttles.SOCIAL_READ_THROTTLES

    def get(self, request, handle):
        target = get_object_or_404(User, handle=handle)
        viewer = request.user if request.user.is_authenticated else None
        if not is_user_visible(viewer, target):
            return Response(status=status.HTTP_404_NOT_FOUND)
        qs = visible_sponds(viewer).filter(
            author=target, parent__isnull=True,
        )
        return Response({
            "user": PublicUserSerializer(target).data,
            "follower_count": target.followers_set.filter(
                state=Follow.STATE_ACCEPTED,
            ).count(),
            "following_count": target.following_set.filter(
                state=Follow.STATE_ACCEPTED,
            ).count(),
            "viewer_is_following": (
                viewer is not None
                and Follow.objects.filter(
                    follower=viewer, followee=target,
                ).values_list("state", flat=True).first()
            ),
            "sponds": SpondSerializer(
                _annotate_sponds(qs)[:25],
                many=True,
                context=_serializer_context(request),
            ).data,
        })


class MyProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = throttles.PROFILE_WRITE_THROTTLES

    def patch(self, request):
        ser = ProfileUpdateSerializer(
            data=request.data, context={"user": request.user},
        )
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        update_fields = []
        if "handle" in data:
            self._check_handle_change_window(request.user)
            request.user.handle = data["handle"]
            request.user.handle_changed_at = timezone.now()
            update_fields.extend(["handle", "handle_changed_at"])
        if "display_name" in data:
            request.user.display_name = data["display_name"]
            update_fields.append("display_name")
        if "bio" in data:
            request.user.bio = data["bio"]
            update_fields.append("bio")
        if "is_private" in data:
            request.user.is_private = data["is_private"]
            update_fields.append("is_private")

        if update_fields:
            request.user.save(update_fields=update_fields)
        return Response(PublicUserSerializer(request.user).data)

    def _check_handle_change_window(self, user):
        if user.handle_changed_at is None:
            return
        cutoff = timezone.now() - timedelta(days=30)
        if user.handle_changed_at > cutoff:
            raise ValidationError({
                "handle": "You can only change your handle once every 30 days.",
                "code": "HANDLE_CHANGE_TOO_SOON",
            })


# ─── Follow / Mute / Block ────────────────────────────────────────────────────


class FollowView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = throttles.FOLLOW_WRITE_THROTTLES

    def post(self, request, handle):
        target = get_object_or_404(User, handle=handle)
        viewer = request.user
        if target.id == viewer.id:
            raise ValidationError({"detail": "You cannot follow yourself."})
        if Block.objects.filter(
            Q(actor=target, target=viewer) | Q(actor=viewer, target=target),
        ).exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Hourly burst guard.
        cutoff = timezone.now() - timedelta(hours=1)
        recent = Follow.objects.filter(
            follower=viewer, created_at__gte=cutoff,
        ).count()
        if recent >= _FOLLOW_HOURLY_BURST_LIMIT:
            raise Throttled(
                detail={
                    "detail": "Slow down — you've followed many accounts recently.",
                    "code": "FOLLOW_BURST_LIMIT",
                },
            )

        state = (
            Follow.STATE_PENDING if target.is_private else Follow.STATE_ACCEPTED
        )
        follow, created = Follow.objects.get_or_create(
            follower=viewer, followee=target, defaults={"state": state},
        )
        if created:
            if state == Follow.STATE_ACCEPTED:
                follow.accepted_at = timezone.now()
                follow.save(update_fields=["accepted_at"])
                notifications.notify_followed(follow)
            else:
                notifications.notify_follow_requested(follow)
        return Response({"state": follow.state}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, handle):
        target = get_object_or_404(User, handle=handle)
        Follow.objects.filter(follower=request.user, followee=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowRequestActionView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = throttles.FOLLOW_WRITE_THROTTLES

    def post(self, request, follow_id, action):
        follow = get_object_or_404(
            Follow, pk=follow_id, followee=request.user,
            state=Follow.STATE_PENDING,
        )
        if action == "accept":
            follow.accept()
            notifications.notify_followed(follow)
            return Response({"state": follow.state})
        if action == "reject":
            follow.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise ValidationError({"detail": "Unknown action."})


class FollowRequestListView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = throttles.SOCIAL_READ_THROTTLES

    def get(self, request):
        qs = Follow.objects.filter(
            followee=request.user, state=Follow.STATE_PENDING,
        ).select_related("follower").order_by("-created_at")
        return Response(FollowRequestSerializer(qs, many=True).data)


class MuteView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = throttles.RELATION_WRITE_THROTTLES

    def post(self, request, handle):
        target = get_object_or_404(User, handle=handle)
        if target.id == request.user.id:
            raise ValidationError({"detail": "You cannot mute yourself."})
        Mute.objects.get_or_create(actor=request.user, target=target)
        return Response({"muted": True}, status=status.HTTP_201_CREATED)

    def delete(self, request, handle):
        target = get_object_or_404(User, handle=handle)
        Mute.objects.filter(actor=request.user, target=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = throttles.RELATION_WRITE_THROTTLES

    def post(self, request, handle):
        target = get_object_or_404(User, handle=handle)
        if target.id == request.user.id:
            raise ValidationError({"detail": "You cannot block yourself."})
        with transaction.atomic():
            Block.objects.get_or_create(actor=request.user, target=target)
            # Blocking auto-removes any Follow rows in either direction so
            # private-account follow grants don't survive the block.
            Follow.objects.filter(
                Q(follower=request.user, followee=target)
                | Q(follower=target, followee=request.user),
            ).delete()
        return Response({"blocked": True}, status=status.HTTP_201_CREATED)

    def delete(self, request, handle):
        target = get_object_or_404(User, handle=handle)
        Block.objects.filter(actor=request.user, target=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Notifications ────────────────────────────────────────────────────────────


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = throttles.SOCIAL_READ_THROTTLES

    def get(self, request):
        qs = (
            Notification.objects.filter(recipient=request.user)
            .select_related("actor")
            .order_by("-created_at")[:100]
        )
        unread = Notification.objects.filter(
            recipient=request.user, read_at__isnull=True,
        ).count()
        return Response({
            "unread_count": unread,
            "notifications": NotificationSerializer(qs, many=True).data,
        })


class NotificationsMarkReadView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = throttles.NOTIF_WRITE_THROTTLES

    def post(self, request):
        ids = request.data.get("ids")
        qs = Notification.objects.filter(
            recipient=request.user, read_at__isnull=True,
        )
        if ids:
            qs = qs.filter(pk__in=ids)
        qs.update(read_at=timezone.now())
        return Response({"ok": True})


# ─── Autocomplete ─────────────────────────────────────────────────────────────


class HandleAutocompleteView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = throttles.SOCIAL_READ_THROTTLES

    def get(self, request):
        q = (request.query_params.get("q") or "").strip().lower()
        if len(q) < 1:
            return Response({"results": []})
        # Don't suggest users blocked-by/blocking the viewer or private
        # accounts the viewer doesn't follow. We accept private-but-followed
        # users (they're already known) but skip strangers' private handles.
        viewer = request.user
        blocked_ids = set(
            Block.objects.filter(actor=viewer).values_list("target_id", flat=True)
        ) | set(
            Block.objects.filter(target=viewer).values_list("actor_id", flat=True),
        )
        accepted_following_ids = set(
            Follow.objects.filter(
                follower=viewer, state=Follow.STATE_ACCEPTED,
            ).values_list("followee_id", flat=True),
        )
        qs = (
            User.objects.filter(handle__startswith=q)
            .exclude(pk__in=blocked_ids)
            .exclude(pk=viewer.pk)
        )
        results = []
        for user in qs[:24]:
            if user.is_private and user.id not in accepted_following_ids:
                continue
            results.append({
                "handle": user.handle,
                "display_name": user.display_name or user.handle,
            })
            if len(results) >= 8:
                break
        return Response({"results": results})


class TickerAutocompleteView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = throttles.SOCIAL_READ_THROTTLES

    def get(self, request):
        q = (request.query_params.get("q") or "").strip().upper()
        if not q:
            return Response({"results": []})
        qs = TickerModel.objects.filter(
            Q(symbol__startswith=q) | Q(display_name__icontains=q),
        ).order_by("symbol")[:8]
        return Response({
            "results": [
                {"symbol": t.symbol, "display_name": t.display_name or t.name}
                for t in qs
            ],
        })
