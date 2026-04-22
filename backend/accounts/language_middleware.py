"""Middleware that syncs the sponda-lang cookie into user.language.

The sponda-lang cookie is the user's authoritative locale choice (set by
the Next.js edge middleware whenever the user visits a locale-prefixed URL
or explicitly switches language). This middleware keeps the DB in sync so
server-side concerns like email language stay accurate.

If there is no valid cookie, we do nothing — Accept-Language is the
fallback for routing, and the DB default is good enough for emails until
the user makes an explicit choice.
"""
from .models import SUPPORTED_LANGUAGES

LANGUAGE_COOKIE_NAME = "sponda-lang"


class LanguagePersistenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return response

        cookie_language = request.COOKIES.get(LANGUAGE_COOKIE_NAME)
        if cookie_language not in SUPPORTED_LANGUAGES:
            return response

        user_language = getattr(user, "language", None)
        if cookie_language != user_language:
            user.language = cookie_language
            user.save(update_fields=["language"])

        return response
