"""Attach a request ID to each HTTP request.

Usage:
  - Honor inbound ``X-Request-ID`` so request tracing survives service hops.
  - Otherwise mint a UUID.
  - Expose it to log records (via ContextVar) and Sentry (via tag).
  - Echo it back in the response as ``X-Request-ID`` so clients can quote it
    when reporting issues.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

import sentry_sdk

REQUEST_ID_HEADER = "X-Request-ID"
MAX_INBOUND_REQUEST_ID_LENGTH = 128

REQUEST_ID_CONTEXT: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """Return the current request ID, or None outside of a request."""
    return REQUEST_ID_CONTEXT.get()


def _resolve_request_id(inbound: str | None) -> str:
    if inbound:
        return inbound[:MAX_INBOUND_REQUEST_ID_LENGTH]
    return str(uuid.uuid4())


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inbound = request.META.get("HTTP_X_REQUEST_ID")
        request_id = _resolve_request_id(inbound)
        request.request_id = request_id

        token = REQUEST_ID_CONTEXT.set(request_id)
        sentry_sdk.set_tag("request_id", request_id)
        try:
            response = self.get_response(request)
        finally:
            REQUEST_ID_CONTEXT.reset(token)

        response[REQUEST_ID_HEADER] = request_id
        return response
