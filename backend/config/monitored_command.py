"""Base class for management commands invoked outside the HTTP request cycle.

Commands triggered by systemd timers (or any non-request entrypoint) bypass
Django's request middleware, so Sentry's DjangoIntegration never sees their
exceptions. Subclass `MonitoredCommand` and implement `run()` instead of
`handle()`; the base `handle()` captures exceptions to Sentry and re-raises
so systemd still marks the unit as failed.

Subclasses may set `sentry_monitor_slug` to a non-empty string to opt in to
Sentry Crons check-ins (wired up in Phase 3).

Subclasses may also name `transient_errors`: provider outages the next run
recovers from on its own. Those are logged and re-raised (systemd still
marks the run failed and retries it) but reach Sentry only once the outage
has outlasted `TRANSIENT_OUTAGE_ALERT_AFTER`, so an hourly job against a
flaky government server pages on a real outage rather than on every run.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta

import sentry_sdk
from django.core.cache import cache
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# How long the outage-start marker survives without a run to refresh or
# clear it. Longer than any alert window, short enough that a retired
# command does not leave it behind for good.
OUTAGE_MARKER_LIFETIME_SECONDS = 7 * 24 * 60 * 60


class MonitoredCommand(BaseCommand):
    sentry_monitor_slug: str | None = None
    transient_errors: tuple[type[BaseException], ...] = ()
    TRANSIENT_OUTAGE_ALERT_AFTER = timedelta(hours=6)

    def run(self, *args, **options):
        raise NotImplementedError("Subclasses must implement run()")

    def handle(self, *args, **options):
        runner = self._with_cron_monitor(self.run) if self.sentry_monitor_slug else self.run
        try:
            result = runner(*args, **options)
        except self.transient_errors as error:
            self._report_transient_error(error)
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise
        if self.transient_errors:
            cache.delete(self._outage_cache_key)
        return result

    @property
    def _outage_cache_key(self) -> str:
        return f"monitored_command:{type(self).__module__}:outage_since"

    def _report_transient_error(self, error: BaseException) -> None:
        """Log a provider outage, and capture it once it has lasted."""
        cache.add(self._outage_cache_key, time.time(), OUTAGE_MARKER_LIFETIME_SECONDS)
        outage_started_at = cache.get(self._outage_cache_key) or time.time()
        outage_seconds = time.time() - outage_started_at
        if outage_seconds >= self.TRANSIENT_OUTAGE_ALERT_AFTER.total_seconds():
            sentry_sdk.capture_exception(error)
            return
        logger.warning(
            "Transient failure (outage %.0f min old, reported after %s): %s",
            outage_seconds / 60,
            self.TRANSIENT_OUTAGE_ALERT_AFTER,
            error,
        )

    def _with_cron_monitor(self, runner):
        decorator = sentry_sdk.crons.monitor(monitor_slug=self.sentry_monitor_slug)
        return decorator(runner)
