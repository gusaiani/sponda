"""Sentry initialization and event scrubbing.

Call `init_sentry(...)` from settings. It is a no-op when `dsn` is falsy,
so dev and test environments stay quiet unless SENTRY_DSN is set.

`scrub_event` is registered as Sentry's `before_send` hook. It redacts
Authorization headers, Cookie headers, and DATABASE_URL from events
before they leave the process.
"""
from __future__ import annotations

import logging
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

SENSITIVE_HEADER_NAMES = frozenset({"authorization", "cookie", "set-cookie"})
SENSITIVE_EXTRA_KEYS = frozenset({"DATABASE_URL", "SECRET_KEY", "DJANGO_SECRET_KEY"})
FILTERED = "[Filtered]"

# Hosts we own. The SDK injects the sentry-trace header into outbound
# HTTP requests whose URL matches one of these patterns. Default is
# "match everything", which would attach trace IDs to every third-party
# API call (brapi, FRED, FMP, OpenAI). Sticking to our own infra keeps
# trace IDs internal and reduces noise on partner-side request logs.
DEFAULT_TRACE_PROPAGATION_TARGETS = [
    r"^https?://(127\.0\.0\.1|localhost)(:\d+)?/",
    r"^https?://([a-z0-9-]+\.)*poe\.ma/",
    r"^https?://([a-z0-9-]+\.)*sponda\.capital/",
]


def init_sentry(
    dsn: str | None,
    environment: str,
    release: str | None,
    traces_sample_rate: float = 1.0,
    profiles_sample_rate: float = 0.0,
    trace_propagation_targets: list[str] | None = None,
) -> bool:
    """Initialize Sentry if a DSN is configured. Returns True when initialized."""
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        send_default_pii=False,
        before_send=scrub_event,
        trace_propagation_targets=(
            trace_propagation_targets
            if trace_propagation_targets is not None
            else DEFAULT_TRACE_PROPAGATION_TARGETS
        ),
    )
    return True


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from a Sentry event before it is sent."""
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            for header_name in list(headers.keys()):
                if header_name.lower() in SENSITIVE_HEADER_NAMES:
                    headers[header_name] = FILTERED

    extra = event.get("extra")
    if isinstance(extra, dict):
        for key in list(extra.keys()):
            if key in SENSITIVE_EXTRA_KEYS:
                extra[key] = FILTERED

    return event
