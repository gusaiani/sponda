"""Base class for management commands invoked outside the HTTP request cycle.

Commands triggered by systemd timers (or any non-request entrypoint) bypass
Django's request middleware, so Sentry's DjangoIntegration never sees their
exceptions. Subclass `MonitoredCommand` and implement `run()` instead of
`handle()`; the base `handle()` captures exceptions to Sentry and re-raises
so systemd still marks the unit as failed.

Subclasses may set `sentry_monitor_slug` to a non-empty string to opt in to
Sentry Crons check-ins (wired up in Phase 3).
"""
from __future__ import annotations

import sentry_sdk
from django.core.management.base import BaseCommand


class MonitoredCommand(BaseCommand):
    sentry_monitor_slug: str | None = None

    def run(self, *args, **options):
        raise NotImplementedError("Subclasses must implement run()")

    def handle(self, *args, **options):
        runner = self._with_cron_monitor(self.run) if self.sentry_monitor_slug else self.run
        try:
            return runner(*args, **options)
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise

    def _with_cron_monitor(self, runner):
        decorator = sentry_sdk.crons.monitor(monitor_slug=self.sentry_monitor_slug)
        return decorator(runner)
