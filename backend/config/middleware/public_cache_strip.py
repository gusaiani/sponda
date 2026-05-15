"""Strip headers that defeat edge caching on anonymous public responses.

Django's SessionMiddleware emits ``Set-Cookie: sessionid=…`` and adds
``Cookie`` to the ``Vary`` header on every response, including anonymous
GETs to endpoints we mark ``Cache-Control: public`` (e.g. ``/api/quote/*``).
Cloudflare and any other shared cache refuse to cache responses that
carry ``Set-Cookie`` or vary on ``Cookie`` — so the public Cache-Control
header is wasted bytes without this middleware.

Three conditions must all hold for stripping to happen:

* ``request.method == "GET"`` — POSTs aren't cacheable anyway.
* ``request.user`` is anonymous — authenticated traffic must keep its
  session cookie or the user loses their login.
* The response declares ``Cache-Control: public`` — opt-in by views,
  so anything we haven't explicitly marked cacheable is untouched.
"""
from __future__ import annotations

from django.conf import settings


class StripSessionFromPublicCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not self._is_anonymous_public_get(request, response):
            return response

        self._strip_session_cookie(response)
        self._strip_cookie_from_vary(response)
        return response

    @staticmethod
    def _is_anonymous_public_get(request, response) -> bool:
        # Cheapest discriminator first: most responses are not public-cached,
        # which lets us short-circuit before touching the lazy ``request.user``
        # and triggering session reads we don't need.
        cache_control = response.get("Cache-Control", "")
        if "public" not in cache_control.lower():
            return False
        if request.method != "GET":
            return False
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return False
        return True

    @staticmethod
    def _strip_session_cookie(response) -> None:
        cookie_name = settings.SESSION_COOKIE_NAME
        if cookie_name in response.cookies:
            del response.cookies[cookie_name]

    @staticmethod
    def _strip_cookie_from_vary(response) -> None:
        if not response.has_header("Vary"):
            return
        kept = [
            value.strip()
            for value in response["Vary"].split(",")
            if value.strip() and value.strip().lower() != "cookie"
        ]
        if kept:
            response["Vary"] = ", ".join(kept)
        else:
            del response["Vary"]
