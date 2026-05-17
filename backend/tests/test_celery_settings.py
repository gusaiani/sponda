"""Regression tests: `make dev` must not require a Redis broker.

development.py overrides CACHES to LocMemCache ("no Redis required"),
but the stale-while-revalidate path in quotes/views.py calls
``refresh_provider_data.delay()``. Without CELERY_TASK_ALWAYS_EAGER the
Celery broker + result backend default to redis://127.0.0.1:6379/0, so
a local server with no Redis enters a 20-retry reconnect storm on every
stale quote request. Eager execution runs the task in-process and keeps
local development fully Redis-free, consistent with the LocMemCache
override in the same settings module.
"""
from __future__ import annotations

from config.settings import development as dev_settings


class TestDevelopmentCeleryIsEager:
    def test_tasks_run_eagerly_so_no_broker_is_needed(self):
        assert dev_settings.CELERY_TASK_ALWAYS_EAGER is True, (
            "development.py must set CELERY_TASK_ALWAYS_EAGER = True so "
            ".delay() runs in-process; otherwise `make dev` requires a live "
            "Redis broker (see quotes/views.py refresh_provider_data.delay)."
        )

    def test_eager_tasks_propagate_exceptions(self):
        assert dev_settings.CELERY_TASK_EAGER_PROPAGATES is True, (
            "development.py must set CELERY_TASK_EAGER_PROPAGATES = True so "
            "task failures surface in local dev instead of being swallowed."
        )
