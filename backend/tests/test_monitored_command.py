"""Tests for MonitoredCommand: management-command base class that reports
failures to Sentry. Used by commands invoked from systemd timers (which
bypass Django middleware and would otherwise lose exception context).
"""
from unittest.mock import patch

import pytest

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
