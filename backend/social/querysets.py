"""Centralized visibility helpers for the social app.

Every view that reads Sponds or User profiles routes through these helpers
so the rules around block / mute / private accounts live in exactly one
place. Anonymous viewers (``None`` or :class:`AnonymousUser`) are handled
the same way: blocks and mutes don't apply, private authors are filtered
out, soft-deleted Sponds are hidden.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q

from social.models import Block, Follow, Mute, Spond


User = get_user_model()


def _is_authenticated(viewer) -> bool:
    return viewer is not None and getattr(viewer, "is_authenticated", False)


def visible_sponds(viewer):
    """Return a Spond queryset filtered to what ``viewer`` may see.

    Excludes:
      * Soft-deleted Sponds.
      * Sponds whose author is in a Block relation with the viewer (either
        direction).
      * Sponds whose author the viewer has muted.
      * Sponds whose author has ``is_private=True`` unless the viewer is the
        author or has an accepted Follow on them.
    """
    qs = Spond.objects.filter(deleted_at__isnull=True)

    if not _is_authenticated(viewer):
        return qs.filter(author__is_private=False)

    blocked_ids = set(
        Block.objects.filter(actor=viewer).values_list("target_id", flat=True),
    )
    blocked_by_ids = set(
        Block.objects.filter(target=viewer).values_list("actor_id", flat=True),
    )
    muted_ids = set(
        Mute.objects.filter(actor=viewer).values_list("target_id", flat=True),
    )
    excluded = blocked_ids | blocked_by_ids | muted_ids
    if excluded:
        qs = qs.exclude(author_id__in=excluded)

    accepted_following_ids = set(
        Follow.objects.filter(
            follower=viewer, state=Follow.STATE_ACCEPTED,
        ).values_list("followee_id", flat=True),
    )
    accepted_following_ids.add(viewer.id)

    qs = qs.filter(
        Q(author__is_private=False)
        | Q(author_id__in=accepted_following_ids),
    )

    return qs


def is_user_visible(viewer, target) -> bool:
    """Whether ``viewer`` may see ``target``'s profile and Sponds.

    Returns ``False`` if either side has blocked the other; if ``target`` is
    private and ``viewer`` is not the target or an accepted follower; or if
    ``target`` is private and ``viewer`` is anonymous.
    """
    if target is None:
        return False

    if Block.objects.filter(actor=target).filter(target=viewer if _is_authenticated(viewer) else None).exists():
        return False
    if _is_authenticated(viewer):
        if Block.objects.filter(actor=viewer, target=target).exists():
            return False

    if not target.is_private:
        return True

    if not _is_authenticated(viewer):
        return False

    if viewer.id == target.id:
        return True

    return Follow.objects.filter(
        follower=viewer, followee=target, state=Follow.STATE_ACCEPTED,
    ).exists()
