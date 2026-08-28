"""The Django cache and the Celery broker must not share a Redis keyspace.

Django's RedisCache.clear() issues FLUSHDB, which erases every key in the
selected database. While the cache and the broker both pointed at db 0, a
single cache.clear() also deleted every queued Celery task and every stored
result. Splitting them across databases makes that impossible: a FLUSHDB on
the cache database cannot reach the broker's queues.

The second half of the danger, an unbounded cache filling the box, is a
maxmemory policy on the Redis server itself and is documented in the README
rather than enforced here.
"""
from __future__ import annotations

from urllib.parse import urlparse

import pytest

from config.redis_urls import redis_url_with_database


class TestRedisUrlWithDatabase:
    def test_replaces_the_database_index(self):
        assert (
            redis_url_with_database("redis://127.0.0.1:6379/0", 1)
            == "redis://127.0.0.1:6379/1"
        )

    def test_adds_a_database_index_when_the_url_has_no_path(self):
        assert (
            redis_url_with_database("redis://127.0.0.1:6379", 1)
            == "redis://127.0.0.1:6379/1"
        )

    def test_preserves_credentials_and_scheme(self):
        assert (
            redis_url_with_database("rediss://:secret@cache.example:6380/0", 3)
            == "rediss://:secret@cache.example:6380/3"
        )

    def test_preserves_the_query_string(self):
        assert (
            redis_url_with_database("redis://127.0.0.1:6379/0?ssl_cert_reqs=none", 1)
            == "redis://127.0.0.1:6379/1?ssl_cert_reqs=none"
        )

    def test_rejects_a_negative_database_index(self):
        with pytest.raises(ValueError):
            redis_url_with_database("redis://127.0.0.1:6379/0", -1)


def _database_index(redis_url: str) -> str:
    return urlparse(redis_url).path.lstrip("/")


class TestCacheAndBrokerAreIsolated:
    """development.py swaps in LocMemCache, so assert against base.py itself.

    base.py is what production runs: production.py does not override CACHES.
    """

    def test_cache_does_not_share_a_database_with_the_broker(self):
        from config.settings import base as base_settings

        cache_database = _database_index(base_settings.CACHES["default"]["LOCATION"])
        broker_database = _database_index(base_settings.CELERY_BROKER_URL)
        assert cache_database != broker_database, (
            "cache.clear() calls FLUSHDB; sharing a database with the Celery "
            "broker means clearing the cache also drops every queued task."
        )

    def test_broker_keeps_database_zero(self):
        from config.settings import base as base_settings

        assert _database_index(base_settings.CELERY_BROKER_URL) == "0"

    def test_result_backend_follows_the_broker(self):
        from config.settings import base as base_settings

        assert base_settings.CELERY_RESULT_BACKEND == base_settings.CELERY_BROKER_URL


class TestBaseSettingsDefaults:
    def test_cache_defaults_to_database_one(self):
        from config.settings import base as base_settings

        assert base_settings.CACHES["default"]["LOCATION"].endswith("/1")

    def test_cache_url_is_overridable_on_its_own(self, monkeypatch):
        import importlib

        from config.settings import base as base_settings

        monkeypatch.setenv("REDIS_CACHE_URL", "redis://elsewhere:6379/7")
        reloaded = importlib.reload(base_settings)
        try:
            assert reloaded.CACHES["default"]["LOCATION"] == "redis://elsewhere:6379/7"
        finally:
            monkeypatch.delenv("REDIS_CACHE_URL")
            importlib.reload(base_settings)
