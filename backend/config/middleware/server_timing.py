"""Emit a Server-Timing response header for every request.

The header lists the total app wall-clock under the ``app`` mark plus any
custom marks recorded by views via ``record_server_timing(request, ...)``.
Browsers and Sentry's Resource Timing capture surface these durations
without bespoke client code, so views can attach hot-path measurements
(cache hit/miss, DB time, provider time) for free.
"""
from __future__ import annotations

import time
from typing import Iterable

SERVER_TIMING_HEADER = "Server-Timing"
_REQUEST_ATTR = "_server_timing_marks"


def record_server_timing(
    request, name: str, duration_ms: float, *, description: str | None = None
) -> None:
    """Append a custom Server-Timing mark for this request.

    No-op when ``request`` is None (e.g. background tasks). Names are not
    sanitized — the caller controls them. Duration is rounded to one decimal
    place because sub-millisecond noise rarely informs decisions.
    """
    if request is None:
        return
    marks: list[tuple[str, float, str | None]] = getattr(request, _REQUEST_ATTR, [])
    marks.append((name, round(duration_ms, 1), description))
    setattr(request, _REQUEST_ATTR, marks)


def _format_marks(marks: Iterable[tuple[str, float, str | None]]) -> str:
    segments: list[str] = []
    for name, duration_ms, description in marks:
        if description:
            segments.append(f'{name};dur={duration_ms};desc="{description}"')
        else:
            segments.append(f"{name};dur={duration_ms}")
    return ", ".join(segments)


class ServerTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        marks: list[tuple[str, float, str | None]] = getattr(request, _REQUEST_ATTR, [])
        marks.append(("app", round(elapsed_ms, 1), None))

        new_value = _format_marks(marks)
        existing = response.get(SERVER_TIMING_HEADER, "")
        if existing:
            new_value = f"{existing}, {new_value}"
        response[SERVER_TIMING_HEADER] = new_value
        return response
