"""DRF permission classes specific to the social app.

Three reusable rules:
  * :class:`IsEmailVerified` — write actions require ``email_verified=True``.
    Returns a friendly error code so the frontend can show the existing
    verification prompt UI.
  * :class:`IsAuthorOrReadOnly` — for objects with an ``author`` field
    (Spond): writes only by the author.
  * :class:`IsRecipient` — for Notifications and incoming follow requests:
    only the recipient may modify.
"""
from __future__ import annotations

from rest_framework import permissions


SAFE_METHODS = permissions.SAFE_METHODS


class IsEmailVerified(permissions.BasePermission):
    """Require ``request.user.email_verified`` for unsafe methods.

    Reads (GET/HEAD/OPTIONS) pass through; writes are gated.
    """

    message = {
        "detail": "Email verification required.",
        "code": "EMAIL_VERIFICATION_REQUIRED",
    }

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(getattr(user, "email_verified", False))


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Object-level: only the ``author`` may write."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return getattr(obj, "author_id", None) == getattr(request.user, "id", None)


class IsRecipient(permissions.BasePermission):
    """Object-level: only the ``recipient`` may modify (notifications,
    incoming follow requests)."""

    def has_object_permission(self, request, view, obj):
        recipient_id = getattr(obj, "recipient_id", None)
        if recipient_id is None:
            recipient_id = getattr(obj, "followee_id", None)
        return recipient_id == getattr(request.user, "id", None)
