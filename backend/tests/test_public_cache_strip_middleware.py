"""StripSessionFromPublicCacheMiddleware tests.

Anonymous GETs to endpoints that declare ``Cache-Control: public`` must
be cacheable at the edge. Django's SessionMiddleware defeats this by
emitting ``Set-Cookie: sessionid=…`` and adding ``Cookie`` to ``Vary``
on every response. This middleware strips both — but only when:

* the request method is GET,
* the request user is anonymous, and
* the response is marked ``Cache-Control: public``.

Authenticated traffic and non-public responses pass through untouched.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.http import HttpResponse

from config.middleware.public_cache_strip import StripSessionFromPublicCacheMiddleware


def _make_request(method: str, path: str, *, is_authenticated: bool):
    request = MagicMock()
    request.method = method
    request.path = path
    request.user = MagicMock(is_authenticated=is_authenticated)
    return request


def _make_response(
    *,
    cache_control: str | None,
    set_session_cookie: bool,
    vary: str | None,
):
    response = HttpResponse(b"{}", content_type="application/json")
    if cache_control is not None:
        response["Cache-Control"] = cache_control
    if set_session_cookie:
        response.set_cookie("sessionid", "abc123", max_age=1209600)
    if vary is not None:
        response["Vary"] = vary
    return response


@pytest.fixture
def middleware():
    """Build the middleware with a stub get_response that returns whatever
    response the test provides via .return_value."""
    inner = MagicMock()
    mw = StripSessionFromPublicCacheMiddleware(inner)
    return mw, inner


class TestPublicGETAnonymous:
    def test_strips_sessionid_set_cookie_on_anonymous_public_get(self, middleware):
        mw, inner = middleware
        inner.return_value = _make_response(
            cache_control="public, max-age=3600",
            set_session_cookie=True,
            vary="origin, Cookie, Accept-Encoding",
        )
        request = _make_request("GET", "/api/quote/VALE3/", is_authenticated=False)

        response = mw(request)

        assert "sessionid" not in response.cookies

    def test_strips_cookie_from_vary_on_anonymous_public_get(self, middleware):
        mw, inner = middleware
        inner.return_value = _make_response(
            cache_control="public, max-age=3600",
            set_session_cookie=True,
            vary="origin, Cookie, Accept-Encoding",
        )
        request = _make_request("GET", "/api/quote/VALE3/", is_authenticated=False)

        response = mw(request)

        vary_values = {v.strip().lower() for v in response.get("Vary", "").split(",") if v}
        assert "cookie" not in vary_values
        assert "origin" in vary_values
        assert "accept-encoding" in vary_values

    def test_drops_vary_header_when_only_cookie_was_listed(self, middleware):
        mw, inner = middleware
        inner.return_value = _make_response(
            cache_control="public, max-age=3600",
            set_session_cookie=True,
            vary="Cookie",
        )
        request = _make_request("GET", "/api/quote/VALE3/", is_authenticated=False)

        response = mw(request)

        assert not response.has_header("Vary")


class TestUnaffectedTraffic:
    def test_leaves_authenticated_responses_alone(self, middleware):
        mw, inner = middleware
        inner.return_value = _make_response(
            cache_control="public, max-age=3600",
            set_session_cookie=True,
            vary="origin, Cookie",
        )
        request = _make_request("GET", "/api/quote/VALE3/", is_authenticated=True)

        response = mw(request)

        assert "sessionid" in response.cookies
        assert "cookie" in response["Vary"].lower()

    def test_leaves_private_responses_alone(self, middleware):
        mw, inner = middleware
        inner.return_value = _make_response(
            cache_control="private, no-store",
            set_session_cookie=True,
            vary="origin, Cookie",
        )
        request = _make_request("GET", "/api/auth/me/", is_authenticated=False)

        response = mw(request)

        assert "sessionid" in response.cookies

    def test_leaves_responses_without_cache_control_alone(self, middleware):
        mw, inner = middleware
        inner.return_value = _make_response(
            cache_control=None,
            set_session_cookie=True,
            vary="origin, Cookie",
        )
        request = _make_request("GET", "/api/auth/lists/", is_authenticated=False)

        response = mw(request)

        assert "sessionid" in response.cookies

    def test_leaves_non_get_methods_alone(self, middleware):
        mw, inner = middleware
        inner.return_value = _make_response(
            cache_control="public, max-age=3600",
            set_session_cookie=True,
            vary="origin, Cookie",
        )
        request = _make_request("POST", "/api/quote/VALE3/", is_authenticated=False)

        response = mw(request)

        assert "sessionid" in response.cookies

    def test_leaves_response_alone_when_no_session_cookie_present(self, middleware):
        """No-op when there is nothing to strip — and Vary should still be cleaned up."""
        mw, inner = middleware
        inner.return_value = _make_response(
            cache_control="public, max-age=3600",
            set_session_cookie=False,
            vary="origin, Accept-Encoding",
        )
        request = _make_request("GET", "/api/quote/VALE3/", is_authenticated=False)

        response = mw(request)

        # No regression on Vary when Cookie was already absent.
        vary_values = {v.strip().lower() for v in response["Vary"].split(",")}
        assert vary_values == {"origin", "accept-encoding"}
