"""Helpers for pointing Redis clients at separate keyspaces on one server.

A single Redis server holds 16 numbered databases. Two clients on the same
host and port are only isolated from each other when they select different
database indexes, so the split has to happen in the URL.
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def redis_url_with_database(redis_url: str, database_index: int) -> str:
    """Return ``redis_url`` pointed at ``database_index``.

    Scheme, credentials, host, port and query string are preserved; only the
    path, which is where a Redis URL carries its database index, is replaced.
    """
    if database_index < 0:
        raise ValueError(f"Redis database index cannot be negative: {database_index}")

    parts = urlparse(redis_url)
    return urlunparse(parts._replace(path=f"/{database_index}"))
