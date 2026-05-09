"""Tests for the Server-Timing middleware.

The middleware emits a `Server-Timing` response header so DevTools and
Sentry's Resource Timing capture surface backend wall-clock per request
without requiring a custom UI.
"""
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from config.middleware.server_timing import (
    SERVER_TIMING_HEADER,
    ServerTimingMiddleware,
    record_server_timing,
)


@pytest.fixture
def request_factory():
    return RequestFactory()


def _build_middleware(view_fn):
    return ServerTimingMiddleware(view_fn)


class TestServerTimingMiddleware:
    def test_emits_total_app_duration(self, request_factory):
        def view(request):
            return HttpResponse("ok")

        middleware = _build_middleware(view)
        response = middleware(request_factory.get("/"))
        header = response[SERVER_TIMING_HEADER]
        assert "app;dur=" in header

    def test_app_duration_is_a_positive_float(self, request_factory):
        def view(request):
            return HttpResponse("ok")

        middleware = _build_middleware(view)
        response = middleware(request_factory.get("/"))
        # Header looks like "app;dur=0.42, ..." — extract the app part.
        parts = dict(
            (segment.split(";dur=")[0].strip(), float(segment.split(";dur=")[1]))
            for segment in response[SERVER_TIMING_HEADER].split(",")
            if ";dur=" in segment
        )
        assert parts["app"] >= 0

    def test_view_can_record_custom_marks(self, request_factory):
        def view(request):
            record_server_timing(request, "cache", 1.5, description="hit")
            record_server_timing(request, "db", 12.3)
            return HttpResponse("ok")

        middleware = _build_middleware(view)
        response = middleware(request_factory.get("/"))
        header = response[SERVER_TIMING_HEADER]
        assert "cache;dur=1.5" in header
        assert 'desc="hit"' in header
        assert "db;dur=12.3" in header

    def test_does_not_clobber_existing_server_timing(self, request_factory):
        def view(request):
            response = HttpResponse("ok")
            response[SERVER_TIMING_HEADER] = "upstream;dur=42"
            return response

        middleware = _build_middleware(view)
        response = middleware(request_factory.get("/"))
        header = response[SERVER_TIMING_HEADER]
        assert "upstream;dur=42" in header
        assert "app;dur=" in header

    def test_record_outside_request_is_safe(self):
        # No request object => no-op, should not raise.
        record_server_timing(None, "noop", 1.0)
