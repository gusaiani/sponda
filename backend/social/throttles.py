"""DRF throttle classes for the social API.

Each user-facing action gets multiple throttle classes (minute / hour / day)
stacked on the view so we limit short bursts and sustained activity at
once. Rates live in ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` so they're
configurable without code changes.

Limits are intentionally tight (5× more stringent than typical defaults).
With a small user base we'd rather see a 429 than tolerate a runaway
script. Loosen later if real users hit ceilings.
"""
from __future__ import annotations

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class _Scoped(UserRateThrottle):
    """Marker base — subclasses set ``scope`` to a key in DEFAULT_THROTTLE_RATES."""


class SpondWriteMinute(_Scoped):
    scope = "spond_write_minute"


class SpondWriteHour(_Scoped):
    scope = "spond_write_hour"


class SpondWriteDay(_Scoped):
    scope = "spond_write_day"


SPOND_WRITE_THROTTLES = [SpondWriteMinute, SpondWriteHour, SpondWriteDay]


class SpondLikeMinute(_Scoped):
    scope = "spond_like_minute"


class SpondLikeHour(_Scoped):
    scope = "spond_like_hour"


class SpondLikeDay(_Scoped):
    scope = "spond_like_day"


SPOND_LIKE_THROTTLES = [SpondLikeMinute, SpondLikeHour, SpondLikeDay]


class FollowWriteMinute(_Scoped):
    scope = "follow_write_minute"


class FollowWriteHour(_Scoped):
    scope = "follow_write_hour"


class FollowWriteDay(_Scoped):
    scope = "follow_write_day"


FOLLOW_WRITE_THROTTLES = [FollowWriteMinute, FollowWriteHour, FollowWriteDay]


class RelationWriteMinute(_Scoped):
    scope = "relation_write_minute"


class RelationWriteHour(_Scoped):
    scope = "relation_write_hour"


RELATION_WRITE_THROTTLES = [RelationWriteMinute, RelationWriteHour]


class ProfileWriteHour(_Scoped):
    scope = "profile_write_hour"


PROFILE_WRITE_THROTTLES = [ProfileWriteHour]


class NotificationWriteMinute(_Scoped):
    scope = "notif_write_minute"


NOTIF_WRITE_THROTTLES = [NotificationWriteMinute]


class SocialAnonRead(AnonRateThrottle):
    scope = "social_anon"


class SocialUserRead(UserRateThrottle):
    scope = "social_user"


SOCIAL_READ_THROTTLES = [SocialAnonRead, SocialUserRead]
