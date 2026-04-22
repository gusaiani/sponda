"""Middleware that keeps the `sponda-lang` cookie in sync with `user.language`.

The Next.js edge middleware decides the locale from that cookie, so if it
ever drifts from the user's stored preference (e.g. the browser cleared
it, or Google OAuth logged the user in without setting the cookie), the
user would bounce to the wrong locale on bare-URL visits. This middleware
rewrites the cookie on every authenticated response so one round-trip to
any authenticated endpoint is enough to restore consistency.
"""
from .models import SUPPORTED_LANGUAGES

LANGUAGE_COOKIE_NAME = "sponda-lang"
LANGUAGE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


class LanguagePersistenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return response

        user_language = getattr(user, "language", None)
        if user_language not in SUPPORTED_LANGUAGES:
            return response

        cookie_language = request.COOKIES.get(LANGUAGE_COOKIE_NAME)
        if cookie_language == user_language:
            return response

        # set_cookie replaces any previously-scheduled Set-Cookie with the same name
        response.set_cookie(
            LANGUAGE_COOKIE_NAME,
            user_language,
            max_age=LANGUAGE_COOKIE_MAX_AGE,
            path="/",
            samesite="Lax",
        )
        return response
