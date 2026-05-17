"""Client IP extraction and privacy-preserving hashing.

The app sits behind Cloudflare -> nginx -> gunicorn. Cloudflare sets
``CF-Connecting-IP`` to the true client address; trust that first.
``X-Forwarded-For`` is the next-best signal (first hop = client), and
``REMOTE_ADDR`` is the last resort (only the proxy in this topology).

IPs are never stored raw — only a salted SHA-256, matching
``PageView.hash_ip`` so the two subsystems agree on identity.
"""
from __future__ import annotations

import hashlib

from django.conf import settings


def client_ip(request) -> str:
    cf = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf:
        return cf.strip()
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def client_ip_hash(request) -> str:
    salt = getattr(settings, "SECRET_KEY", "")[:16]
    return hashlib.sha256(f"{salt}:{client_ip(request)}".encode()).hexdigest()
