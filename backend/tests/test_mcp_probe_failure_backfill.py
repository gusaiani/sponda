"""Tests the backfill that un-flags capability probes recorded as failures.

Before assistant.mcp learned that "method not found" is a usable answer,
every server/discover or resources/list probe — one per Claude connect —
was written with failed=True and inflated the dashboard's error column.
The rule is exact: no supported method outside tools/call can ever set
failed=True, so every failed row on another method is a probe.
"""
import pytest

from assistant.models import McpCall

MIGRATION = "0005_unflag_capability_probe_failures"
FAKE_IP_HASH = "a" * 64


def run_backfill():
    """Apply just this migration's data function against the current schema.

    The schema editor is unused by the function · it only reads and writes
    rows · and instantiating a real one outside its context manager leaves
    connection state behind that other tests then trip over.
    """
    from importlib import import_module

    from django.apps.registry import apps as global_apps

    module = import_module(f"assistant.migrations.{MIGRATION}")
    module.unflag_capability_probes(global_apps, None)


def record(method, **overrides):
    return McpCall.objects.create(
        method=method, ip_hash=FAKE_IP_HASH, **overrides
    )


@pytest.mark.django_db
def test_a_probe_recorded_as_failed_is_unflagged():
    row = record("server/discover", failed=True)

    run_backfill()

    row.refresh_from_db()
    assert row.failed is False


@pytest.mark.django_db
def test_a_genuine_tool_call_failure_stays_failed():
    row = record("tools/call", tool_name="get_company", failed=True)

    run_backfill()

    row.refresh_from_db()
    assert row.failed is True


@pytest.mark.django_db
def test_rows_that_never_failed_are_left_alone():
    handshake = record("initialize")
    notification = record("notifications/initialized")

    run_backfill()

    handshake.refresh_from_db()
    notification.refresh_from_db()
    assert handshake.failed is False
    assert notification.failed is False
