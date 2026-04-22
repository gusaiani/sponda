"""Middleware that primes `sponda-lang` from `user.language` when it's missing.

Frontend/edge middleware treats the `sponda-lang` cookie as the user's
most recent explicit locale choice (including URL-driven navigation to
`/pt`, `/es`, …). We only step in when the cookie is absent or invalid
— for authenticated users, the stored `user.language` is a better
fallback than Accept-Language. If the cookie is already a supported
locale we leave it alone so URL-driven changes aren't clobbered on the
next API round-trip.
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
        if cookie_language in SUPPORTED_LANGUAGES:
            # Cookie already carries the user's most recent choice — leave it
            # alone so URL-driven locale changes aren't clobbered.
            return response

        response.set_cookie(
            LANGUAGE_COOKIE_NAME,
            user_language,
            max_age=LANGUAGE_COOKIE_MAX_AGE,
            path="/",
            samesite="Lax",
        )
        return response
