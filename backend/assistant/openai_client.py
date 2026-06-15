"""Cached OpenAI client for the assistant.

The OpenAI SDK wraps a pooled httpx connection. Build it once and reuse it
so the TLS connection stays warm across requests instead of paying a fresh
handshake per question — lru_cache on a zero-arg function is that "build
once" lazy singleton.
"""
from functools import lru_cache

from django.conf import settings
from openai import OpenAI

# Network budget for one OpenAI call. The view streams to the user on a sync
# gunicorn worker, so a hung upstream call must fail fast, not pin the worker.
REQUEST_TIMEOUT_SECONDS = 30

# Retry once on a transient failure, then give up — the caller surfaces a
# clean error frame rather than making the user wait through a retry storm.
MAX_RETRIES = 1


@lru_cache
def get_openai_client() -> OpenAI:
    """Return the process-wide OpenAI client, building it on first use."""
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )