"""Tests for MCP usage analytics.

Two halves, both new: the ``McpCall`` audit row the public MCP endpoint
writes for every JSON-RPC message it answers, and the ``mcp`` section the
admin dashboard builds out of those rows.

This is the only record of MCP traffic that exists. PostHog is a browser
snippet and MCP clients never load a page, so nothing upstream counts these
calls; the rate-limit counters in ``assistant.mcp`` are per-IP cache keys
that expire at midnight and can't answer "how many queries last month".
"""
import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.utils import timezone

from assistant.models import McpCall

MCP_URL = "/api/mcp/"
DASHBOARD_URL = "/api/auth/admin/dashboard/"
FAKE_IP_HASH = "f" * 64


def rpc_post(client, body, **extra):
    """POST one raw JSON-RPC payload to the MCP endpoint."""
    data = body if isinstance(body, str) else json.dumps(body)
    return client.post(
        MCP_URL, data=data, content_type="application/json", **extra
    )


def rpc_call(client, method, params=None, request_id=1, **extra):
    body = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    return rpc_post(client, body, **extra)


def tool_call(client, name, arguments=None, **extra):
    return rpc_call(
        client, "tools/call", {"name": name, "arguments": arguments or {}}, **extra
    )


@pytest.mark.django_db
class TestMcpCallRecording:
    """Every answered JSON-RPC message leaves exactly one row."""

    @pytest.fixture(autouse=True)
    def _default_settings(self, settings):
        settings.MCP_ENABLED = True
        cache.clear()

    def test_tool_call_is_recorded_with_its_tool_name(self, client):
        with patch("assistant.mcp.client_ip_hash", return_value=FAKE_IP_HASH):
            tool_call(client, "list_available_indicators")

        call = McpCall.objects.get()
        assert call.method == "tools/call"
        assert call.tool_name == "list_available_indicators"
        assert call.ip_hash == FAKE_IP_HASH
        assert call.failed is False
        assert call.rate_limited is False

    def test_latency_is_recorded(self, client):
        tool_call(client, "list_available_indicators")
        assert McpCall.objects.get().latency_ms >= 0

    def test_initialize_records_the_client_identity(self, client):
        rpc_call(client, "initialize", {
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "claude-code", "version": "2.1.0"},
            "capabilities": {},
        })

        call = McpCall.objects.get()
        assert call.method == "initialize"
        assert call.client_name == "claude-code"
        assert call.client_version == "2.1.0"
        assert call.protocol_version == "2025-06-18"

    def test_initialize_without_client_info_records_blanks_not_nulls(self, client):
        rpc_call(client, "initialize", {"protocolVersion": "2025-06-18"})

        call = McpCall.objects.get()
        assert call.client_name == ""
        assert call.client_version == ""

    def test_user_agent_is_recorded(self, client):
        rpc_call(client, "ping", HTTP_USER_AGENT="Cursor/0.42 (mcp)")
        assert McpCall.objects.get().user_agent == "Cursor/0.42 (mcp)"

    def test_lifecycle_methods_are_recorded(self, client):
        rpc_call(client, "ping")
        rpc_call(client, "tools/list")

        methods = set(McpCall.objects.values_list("method", flat=True))
        assert methods == {"ping", "tools/list"}

    def test_notifications_are_recorded(self, client):
        response = rpc_post(client, {
            "jsonrpc": "2.0", "method": "notifications/initialized",
        })
        assert response.status_code == 202
        assert McpCall.objects.get().method == "notifications/initialized"

    def test_tool_executor_error_is_recorded_as_failed(self, client):
        tool_call(client, "get_company", {"symbol": "NOSUCH9"})

        call = McpCall.objects.get()
        assert call.tool_name == "get_company"
        assert call.failed is True

    def test_unknown_tool_is_recorded_as_failed(self, client):
        tool_call(client, "not_a_tool")

        call = McpCall.objects.get()
        assert call.method == "tools/call"
        assert call.failed is True

    def test_unsupported_method_is_recorded_as_failed(self, client):
        rpc_call(client, "resources/list")

        call = McpCall.objects.get()
        assert call.method == "resources/list"
        assert call.failed is True

    def test_rate_limited_call_is_recorded_and_flagged(self, client, settings):
        settings.MCP_TOOL_CALLS_PER_DAY = 1
        with patch("assistant.mcp.client_ip_hash", return_value=FAKE_IP_HASH):
            tool_call(client, "list_available_indicators")
            blocked = tool_call(client, "list_available_indicators")

        assert blocked.status_code == 429
        assert McpCall.objects.count() == 2
        rejected = McpCall.objects.order_by("timestamp").last()
        assert rejected.rate_limited is True
        assert rejected.failed is True
        assert rejected.tool_name == "list_available_indicators"

    def test_malformed_json_is_not_recorded(self, client):
        rpc_post(client, "{not json")
        assert McpCall.objects.count() == 0

    def test_non_post_requests_are_not_recorded(self, client):
        client.get(MCP_URL)
        assert McpCall.objects.count() == 0

    def test_disabled_server_records_nothing(self, client, settings):
        settings.MCP_ENABLED = False
        rpc_call(client, "ping")
        assert McpCall.objects.count() == 0

    def test_recording_stops_at_the_daily_cap_per_ip(self, client, settings):
        """Lifecycle methods are deliberately uncapped, so without a cap of
        its own the audit table is an unauthenticated write amplifier."""
        settings.MCP_RECORDED_CALLS_PER_DAY = 2
        with patch("assistant.mcp.client_ip_hash", return_value=FAKE_IP_HASH):
            rpc_call(client, "ping")
            rpc_call(client, "ping")
            beyond_cap = rpc_call(client, "ping")

        assert McpCall.objects.count() == 2
        # The cap bounds the bookkeeping, never the service.
        assert beyond_cap.status_code == 200

    def test_recording_cap_is_per_ip(self, client, settings):
        settings.MCP_RECORDED_CALLS_PER_DAY = 1
        with patch("assistant.mcp.client_ip_hash", return_value="a" * 64):
            rpc_call(client, "ping")
            rpc_call(client, "ping")
        with patch("assistant.mcp.client_ip_hash", return_value="b" * 64):
            rpc_call(client, "ping")

        assert McpCall.objects.count() == 2

    def test_recording_failure_never_breaks_the_response(self, client):
        """Analytics is a side channel: if the write blows up, the client
        must still get its answer."""
        with patch(
            "assistant.mcp.McpCall.objects.create",
            side_effect=RuntimeError("database is on fire"),
        ):
            response = rpc_call(client, "ping")

        assert response.status_code == 200
        assert json.loads(response.content)["result"] == {}


@pytest.mark.django_db
class TestAdminDashboardMcpStats:
    """The dashboard's `mcp` section, built from McpCall rows."""

    def _record(self, *, method="tools/call", tool_name="screen_companies",
                ip_hash="a" * 64, client_name="", failed=False,
                rate_limited=False, days_ago=0):
        call = McpCall.objects.create(
            method=method,
            tool_name=tool_name,
            ip_hash=ip_hash,
            client_name=client_name,
            failed=failed,
            rate_limited=rate_limited,
        )
        if days_ago:
            # timestamp is auto_now_add, so back-date it after the fact.
            McpCall.objects.filter(pk=call.pk).update(
                timestamp=timezone.now() - timezone.timedelta(days=days_ago)
            )
        return call

    def test_dashboard_exposes_an_mcp_section(self, superuser_client):
        response = superuser_client.get(DASHBOARD_URL)
        assert response.status_code == 200
        mcp_stats = response.json()["mcp"]
        assert set(mcp_stats) == {
            "periods", "top_tools", "top_clients", "daily_calls"
        }

    def test_period_totals_count_only_calls_inside_the_window(
        self, superuser_client
    ):
        self._record()
        self._record(days_ago=3)
        self._record(days_ago=200)
        self._record(days_ago=400)

        periods = superuser_client.get(DASHBOARD_URL).json()["mcp"]["periods"]
        assert periods["day"]["total_calls"] == 1
        assert periods["week"]["total_calls"] == 2
        assert periods["month"]["total_calls"] == 2
        assert periods["year"]["total_calls"] == 3
        assert periods["all_time"]["total_calls"] == 4

    def test_tool_calls_are_counted_apart_from_protocol_chatter(
        self, superuser_client
    ):
        self._record(method="tools/call")
        self._record(method="initialize", tool_name="")
        self._record(method="ping", tool_name="")

        periods = superuser_client.get(DASHBOARD_URL).json()["mcp"]["periods"]
        assert periods["day"]["total_calls"] == 3
        assert periods["day"]["tool_calls"] == 1

    def test_unique_clients_counts_distinct_ip_hashes(self, superuser_client):
        self._record(ip_hash="a" * 64)
        self._record(ip_hash="a" * 64)
        self._record(ip_hash="b" * 64)

        periods = superuser_client.get(DASHBOARD_URL).json()["mcp"]["periods"]
        assert periods["day"]["unique_clients"] == 2

    def test_failed_and_rate_limited_calls_are_counted(self, superuser_client):
        self._record()
        self._record(failed=True)
        self._record(failed=True, rate_limited=True)

        periods = superuser_client.get(DASHBOARD_URL).json()["mcp"]["periods"]
        assert periods["day"]["failed_calls"] == 2
        assert periods["day"]["rate_limited_calls"] == 1

    def test_top_tools_ranks_by_call_count(self, superuser_client):
        for _ in range(3):
            self._record(tool_name="screen_companies")
        self._record(tool_name="get_company")

        top_tools = superuser_client.get(DASHBOARD_URL).json()["mcp"]["top_tools"]
        assert top_tools[0] == {"tool_name": "screen_companies", "call_count": 3}
        assert top_tools[1] == {"tool_name": "get_company", "call_count": 1}

    def test_top_tools_ignores_rows_that_are_not_tool_calls(
        self, superuser_client
    ):
        self._record(method="ping", tool_name="")
        self._record(tool_name="get_company")

        top_tools = superuser_client.get(DASHBOARD_URL).json()["mcp"]["top_tools"]
        assert top_tools == [{"tool_name": "get_company", "call_count": 1}]

    def test_top_clients_ranks_named_clients_from_initialize(
        self, superuser_client
    ):
        self._record(method="initialize", tool_name="", client_name="claude-code")
        self._record(method="initialize", tool_name="", client_name="claude-code")
        self._record(method="initialize", tool_name="", client_name="cursor-vscode")
        self._record(method="initialize", tool_name="", client_name="")

        top_clients = superuser_client.get(DASHBOARD_URL).json()["mcp"]["top_clients"]
        assert top_clients == [
            {"client_name": "claude-code", "connection_count": 2},
            {"client_name": "cursor-vscode", "connection_count": 1},
        ]

    def test_daily_calls_series_covers_the_last_thirty_days(
        self, superuser_client
    ):
        self._record()
        self._record()
        self._record(days_ago=2)
        self._record(days_ago=90)

        daily_calls = superuser_client.get(DASHBOARD_URL).json()["mcp"]["daily_calls"]
        assert len(daily_calls) == 30
        assert daily_calls[-1]["call_count"] == 2
        assert daily_calls[-3]["call_count"] == 1
        assert sum(day["call_count"] for day in daily_calls) == 3

    def test_daily_calls_series_is_chronological_and_dated(
        self, superuser_client
    ):
        daily_calls = superuser_client.get(DASHBOARD_URL).json()["mcp"]["daily_calls"]
        dates = [day["date"] for day in daily_calls]
        assert dates == sorted(dates)
        assert dates[-1] == timezone.localdate().isoformat()

    def test_empty_history_returns_zeroes_not_errors(self, superuser_client):
        mcp_stats = superuser_client.get(DASHBOARD_URL).json()["mcp"]
        assert mcp_stats["periods"]["all_time"]["total_calls"] == 0
        assert mcp_stats["top_tools"] == []
        assert mcp_stats["top_clients"] == []

    def test_regular_user_cannot_read_mcp_stats(self, client, django_user_model):
        django_user_model.objects.create_user(
            username="plain@example.com", email="plain@example.com", password="pw123456"
        )
        client.login(username="plain@example.com", password="pw123456")
        assert client.get(DASHBOARD_URL).status_code == 403

    def test_query_count_does_not_grow_with_mcp_traffic(self, superuser_client):
        """The section must aggregate in SQL, not iterate rows in Python.

        Volume and variety both grow over time (distinct tools, distinct
        client names, distinct days) and none of them may add a query.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._record()
        with CaptureQueriesContext(connection) as quiet:
            superuser_client.get(DASHBOARD_URL)

        for index in range(20):
            self._record(tool_name=f"tool_{index}", ip_hash=f"{index:064d}")
            self._record(
                method="initialize", tool_name="",
                client_name=f"client_{index}", days_ago=index,
            )
        with CaptureQueriesContext(connection) as busy:
            response = superuser_client.get(DASHBOARD_URL)

        assert response.status_code == 200
        assert len(busy) == len(quiet)
