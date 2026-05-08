"""Notification fan-out helpers.

Each ``notify_*`` function is called from a view after a write succeeds.
We collapse "duplicate" notifications: re-liking the same Spond within 24h
does not create a second ``liked`` row, for instance. Since this is called
inside the same request as the triggering write, we keep it simple — no
async fan-out, no batching. With 32 users that's fine.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from social.models import Block, Notification


_DUPLICATE_WINDOW = timedelta(hours=24)


def _can_notify(actor, recipient) -> bool:
    """Suppress notifications across block boundaries and self-actions."""
    if recipient is None:
        return False
    if actor is not None and getattr(actor, "id", None) == recipient.id:
        return False
    if actor is None:
        return True
    return not Block.objects.filter(actor=recipient, target=actor).exists() and not Block.objects.filter(actor=actor, target=recipient).exists()


def _create(*, recipient, actor, verb, target=None, dedup=True):
    if not _can_notify(actor, recipient):
        return None
    if dedup and target is not None:
        ct = ContentType.objects.get_for_model(type(target))
        cutoff = timezone.now() - _DUPLICATE_WINDOW
        existing = Notification.objects.filter(
            recipient=recipient,
            actor=actor,
            verb=verb,
            target_content_type=ct,
            target_object_id=str(target.pk),
            created_at__gte=cutoff,
        ).first()
        if existing is not None:
            return existing
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        target=target,
    )


def notify_replied(spond):
    """Reply created — notify the parent Spond's author."""
    if spond.parent_id is None:
        return None
    return _create(
        recipient=spond.parent.author,
        actor=spond.author,
        verb=Notification.VERB_REPLIED,
        target=spond,
    )


def notify_mentioned(spond, mentioned_users):
    """Spond created — notify each user mentioned by ``@handle``."""
    created = []
    for user in mentioned_users:
        n = _create(
            recipient=user,
            actor=spond.author,
            verb=Notification.VERB_MENTIONED,
            target=spond,
        )
        if n is not None:
            created.append(n)
    return created


def notify_liked(like):
    return _create(
        recipient=like.spond.author,
        actor=like.user,
        verb=Notification.VERB_LIKED,
        target=like.spond,
    )


def notify_followed(follow):
    """Public follow accepted, OR a previously-pending follow just accepted —
    the *follower* is notified that they are now following ``followee``? No:
    the *followee* is notified that they have a new follower. ``followed``
    means "X followed you"."""
    return _create(
        recipient=follow.followee,
        actor=follow.follower,
        verb=Notification.VERB_FOLLOWED,
        target=follow,
        dedup=False,
    )


def notify_follow_requested(follow):
    return _create(
        recipient=follow.followee,
        actor=follow.follower,
        verb=Notification.VERB_FOLLOW_REQUESTED,
        target=follow,
        dedup=False,
    )
