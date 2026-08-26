"""Client IP extraction and privacy-preserving hashing.

The app sits behind Cloudflare -> nginx -> gunicorn, and this module decides
who a request belongs to for the anonymous lookup cap. Read the order below as
a preference list, not as a trust boundary: none of these headers is
self-authenticating, and any peer can send all three.

What makes them trustworthy is nginx. ``nginx/sponda.capital.conf`` resolves
``$remote_addr`` from ``CF-Connecting-IP`` only for connections arriving from a
published Cloudflare range, then overwrites all three headers from that value,
so a forged one cannot survive the hop. Change that config and this function
starts reading attacker-supplied data. See "Origin trust" in the README.

IPs are never stored raw, only as a salted SHA-256 matching ``PageView.hash_ip``
so the two subsystems agree on identity.
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
