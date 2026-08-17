"""Which language Sponda should write to a given user in.

Outbound email and the unsubscribe page both need this answer, and neither
belongs to the other, so the rule lives on its own instead of being reached
for across modules.
"""
from .models import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES


def resolve_user_language(user):
    """Return the user's language, falling back when it is unset or unknown.

    Accepts ``None`` so callers holding an anonymous or unresolved user do
    not have to guard the call.
    """
    language = getattr(user, "language", None) or DEFAULT_LANGUAGE
    if language not in SUPPORTED_LANGUAGES:
        return DEFAULT_LANGUAGE
    return language
