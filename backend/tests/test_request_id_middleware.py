"""Tests for the request-ID middleware.

Each HTTP request gets a UUID attached to the log context and echoed
back as the X-Request-ID response header. If the inbound request already
carries an X-Request-ID, we honor it (for tracing across services) rather
than minting a new one.
"""
from unittest.mock import patch

import pytest
from django.test import RequestFactory

from config.middleware.request_id import (
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    current_request_id,
)


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def middleware():
    def _get_response(request):
        # Simulate a view that reads the current request ID while handling the request.
        request.seen_request_id = current_request_id()
        from django.http import HttpResponse
        return HttpResponse("ok")

    return RequestIDMiddleware(_get_response)


class TestRequestIDMiddleware:
    def test_generates_uuid_when_header_missing(self, request_factory, middleware):
        request = request_factory.get("/")
        response = middleware(request)
        request_id = response[REQUEST_ID_HEADER]
        assert len(request_id) == 36  # standard UUID length
        assert request.request_id == request_id

    def test_honors_inbound_header(self, request_factory, middleware):
        inbound_id = "abc-123"
        request = request_factory.get("/", **{f"HTTP_X_REQUEST_ID": inbound_id})
        response = middleware(request)
        assert response[REQUEST_ID_HEADER] == inbound_id
        assert request.request_id == inbound_id

    def test_rejects_absurdly_long_inbound_header(self, request_factory, middleware):
        # A defensive cap: never reflect more than 128 chars of user-supplied ID.
        request = request_factory.get("/", **{"HTTP_X_REQUEST_ID": "x" * 500})
        response = middleware(request)
        assert len(response[REQUEST_ID_HEADER]) <= 128

    def test_request_id_is_attached_to_sentry_scope(self, request_factory, middleware):
        with patch("config.middleware.request_id.sentry_sdk.set_tag") as mocked_set_tag:
            request = request_factory.get("/")
            middleware(request)
        mocked_set_tag.assert_any_call("request_id", request.request_id)

    def test_current_request_id_outside_request_is_none(self):
        # No request in flight → ContextVar default.
        assert current_request_id() is None

    def test_current_request_id_is_accessible_during_request(
        self, request_factory, middleware
    ):
        request = request_factory.get("/")
        middleware(request)
        # The middleware attached request.seen_request_id inside the view.
        assert request.seen_request_id == request.request_id
        # After the request, the context var is cleared.
        assert current_request_id() is None
