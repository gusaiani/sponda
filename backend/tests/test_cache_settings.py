"""Regression tests for production CACHES configuration.

The development settings override CACHES to LocMemCache, so a broken
Redis OPTIONS dict in base.py would never trip a normal test run.
These tests exercise the base.py Redis cache config directly and
assert it does not raise TypeError on first use — which is what
django-redis-style ``CONNECTION_POOL_KWARGS`` would do under the
built-in ``django.core.cache.backends.redis.RedisCache``.
"""
from __future__ import annotations

import inspect

import pytest

from config.settings import base as base_settings


class TestProductionCacheOptions:
    def test_options_keys_are_accepted_by_redis_connection_pool(self):
        """Every OPTIONS key must be a kwarg redis.ConnectionPool.from_url accepts.

        Django's built-in RedisCache forwards leftover OPTIONS (anything
        other than ``db``, ``pool_class``, ``parser_class``, ``serializer``)
        to ``redis.ConnectionPool.from_url(**kwargs)``. Unknown keys are
        propagated further into AbstractConnection.__init__ and raise
        TypeError at first cache.get.
        """
        import redis

        cache_options = base_settings.CACHES["default"]["OPTIONS"]
        known_django_keys = {"db", "pool_class", "parser_class", "serializer"}
        leftover = {k: v for k, v in cache_options.items() if k not in known_django_keys}

        pool_signature = inspect.signature(redis.ConnectionPool.__init__)
        connection_signature = inspect.signature(redis.Connection.__init__)
        accepted = set(pool_signature.parameters) | set(connection_signature.parameters)

        unknown = [key for key in leftover if key not in accepted]
        assert not unknown, (
            f"OPTIONS contains keys that neither redis.ConnectionPool nor "
            f"redis.Connection accept: {unknown}. These will raise TypeError "
            f"at first cache.get."
        )

    def test_cache_get_does_not_raise_typeerror_on_options(self):
        """Exercising the production CACHES dict must not raise TypeError.

        ConnectionError is acceptable (Redis may be unreachable in CI),
        but TypeError means an OPTIONS key leaked into the connection.
        """
        from django.core.cache.backends.redis import RedisCache

        entry = base_settings.CACHES["default"]
        cache = RedisCache(entry["LOCATION"], entry)

        try:
            cache.get("__regression_probe__")
        except TypeError as exc:
            pytest.fail(
                f"CACHES OPTIONS leaked into redis connection layer: {exc}"
            )
        except Exception:
            pass
