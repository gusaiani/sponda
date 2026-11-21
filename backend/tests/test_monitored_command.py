"""Tests for MonitoredCommand: management-command base class that reports
failures to Sentry. Used by commands invoked from systemd timers (which
bypass Django middleware and would otherwise lose exception context).
"""
from unittest.mock import patch

import pytest
from django.core.cache import cache

from config.monitored_command import MonitoredCommand


class SuccessfulCommand(MonitoredCommand):
    sentry_monitor_slug = None

    def run(self, *args, **options):
        self.stdout.write("ok")


class FailingCommand(MonitoredCommand):
    sentry_monitor_slug = None

    def run(self, *args, **options):
        raise RuntimeError("boom")


class TestMonitoredCommand:
    def test_run_is_called_on_success(self):
        command = SuccessfulCommand()
        with patch("config.monitored_command.sentry_sdk.capture_exception") as mocked_capture:
            command.handle()
        mocked_capture.assert_not_called()

    def test_exception_is_captured_then_reraised(self):
        command = FailingCommand()
        with patch("config.monitored_command.sentry_sdk.capture_exception") as mocked_capture:
            with pytest.raises(RuntimeError, match="boom"):
                command.handle()
        mocked_capture.assert_called_once()
        # The exception object passed to capture_exception should be the RuntimeError
        captured_exc = mocked_capture.call_args.args[0]
        assert isinstance(captured_exc, RuntimeError)

    def test_subclasses_must_implement_run(self):
        class IncompleteCommand(MonitoredCommand):
            sentry_monitor_slug = None

        with pytest.raises(NotImplementedError):
            IncompleteCommand().handle()


class MonitoredWithSlugCommand(MonitoredCommand):
    sentry_monitor_slug = "sponda-test-monitor"

    def run(self, *args, **options):
        self.stdout.write("ok")


class MonitoredWithSlugFailingCommand(MonitoredCommand):
    sentry_monitor_slug = "sponda-test-monitor-fail"

    def run(self, *args, **options):
        raise RuntimeError("boom")


class TestSentryCronsCheckIn:
    def test_wraps_run_in_monitor_when_slug_is_set(self):
        command = MonitoredWithSlugCommand()
        with patch("config.monitored_command.sentry_sdk.crons.monitor") as mocked_monitor:
            mocked_monitor.return_value = lambda fn: fn
            command.handle()
        mocked_monitor.assert_called_once_with(monitor_slug="sponda-test-monitor")

    def test_does_not_wrap_when_slug_is_none(self):
        command = SuccessfulCommand()
        with patch("config.monitored_command.sentry_sdk.crons.monitor") as mocked_monitor:
            command.handle()
        mocked_monitor.assert_not_called()

    def test_monitor_is_applied_even_when_run_raises(self):
        command = MonitoredWithSlugFailingCommand()
        with patch("config.monitored_command.sentry_sdk.crons.monitor") as mocked_monitor, \
             patch("config.monitored_command.sentry_sdk.capture_exception"):
            mocked_monitor.return_value = lambda fn: fn
            with pytest.raises(RuntimeError):
                command.handle()
        mocked_monitor.assert_called_once_with(monitor_slug="sponda-test-monitor-fail")


class _ProviderDown(Exception):
    pass


class FlakyProviderCommand(MonitoredCommand):
    """A command whose provider has outages it recovers from on its own."""

    sentry_monitor_slug = None
    transient_errors = (_ProviderDown,)

    def __init__(self, *args, outcome=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcome = outcome

    def run(self, *args, **options):
        if self.outcome is not None:
            raise self.outcome
        self.stdout.write("ok")


class TestTransientErrors:
    """A provider outage the next run recovers from is not an incident.

    The hourly ENET sync paged Sentry for every run CVM's server was down,
    ten events in a week, each fixed by the next run with no change on our
    side. A transient error is now logged and re-raised (systemd still
    retries it), and reaches Sentry only once the outage has lasted
    `TRANSIENT_OUTAGE_ALERT_AFTER`.
    """

    @pytest.fixture(autouse=True)
    def clear_outage_state(self):
        cache.clear()
        yield
        cache.clear()

    def test_a_fresh_outage_is_logged_not_captured(self, caplog):
        command = FlakyProviderCommand(outcome=_ProviderDown("CVM is down"))
        with patch("config.monitored_command.sentry_sdk.capture_exception") as mocked_capture:
            with pytest.raises(_ProviderDown):
                command.handle()

        mocked_capture.assert_not_called()
        assert "CVM is down" in caplog.text

    def test_an_outage_that_lasts_is_captured(self):
        clock = [1_000_000.0]
        command = FlakyProviderCommand(outcome=_ProviderDown("CVM is down"))
        with patch("config.monitored_command.time.time", side_effect=lambda: clock[0]), \
             patch("config.monitored_command.sentry_sdk.capture_exception") as mocked_capture:
            with pytest.raises(_ProviderDown):
                command.handle()
            clock[0] += MonitoredCommand.TRANSIENT_OUTAGE_ALERT_AFTER.total_seconds()
            with pytest.raises(_ProviderDown):
                command.handle()

        mocked_capture.assert_called_once()

    def test_a_successful_run_ends_the_outage(self):
        clock = [1_000_000.0]
        with patch("config.monitored_command.time.time", side_effect=lambda: clock[0]), \
             patch("config.monitored_command.sentry_sdk.capture_exception") as mocked_capture:
            with pytest.raises(_ProviderDown):
                FlakyProviderCommand(outcome=_ProviderDown("down")).handle()
            FlakyProviderCommand().handle()
            clock[0] += MonitoredCommand.TRANSIENT_OUTAGE_ALERT_AFTER.total_seconds()
            with pytest.raises(_ProviderDown):
                FlakyProviderCommand(outcome=_ProviderDown("down again")).handle()

        mocked_capture.assert_not_called()

    def test_any_other_error_is_still_captured_at_once(self):
        command = FlakyProviderCommand(outcome=RuntimeError("a bug"))
        with patch("config.monitored_command.sentry_sdk.capture_exception") as mocked_capture:
            with pytest.raises(RuntimeError):
                command.handle()

        mocked_capture.assert_called_once()
