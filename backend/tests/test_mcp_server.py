"""Tests for the public MCP server endpoint (/api/mcp/).

The endpoint is a stateless Streamable-HTTP MCP server: JSON-RPC 2.0 over a
single POST route, no sessions, no SSE. It exposes the assistant's existing
tool layer (assistant.tools) to any MCP client — Claude, Cursor, custom
agents — so the tool schemas and executors are shared with the screening
agent by construction and can never drift.

Seeding style mirrors tests/test_assistant_tools.py: real Ticker +
IndicatorSnapshot rows, because the tools are thin wrappers over real ORM
queries. get_fundamentals goes through an external-fetch dependency, so that
one is patched.
"""
import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache

from assistant.mcp import MCP_LATEST_PROTOCOL_VERSION, MCP_SUPPORTED_PROTOCOL_VERSIONS

MCP_URL = "/api/mcp/"
FAKE_IP_HASH = "f" * 64

EXPECTED_TOOL_NAMES = {
    "list_available_indicators",
    "screen_companies",
    "get_company",
    "get_fundamentals",
}


def rpc_post(client, body: dict | list | str):
    """POST one raw JSON-RPC payload to the MCP endpoint."""
    data = body if isinstance(body, str) else json.dumps(body)
    return client.post(MCP_URL, data=data, content_type="application/json")


def rpc_call(client, method: str, params: dict | None = None, request_id=1):
    """POST one JSON-RPC request and return the HTTP response."""
    body = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    return rpc_post(client, body)


def tool_call(client, name: str, arguments: dict | None = None):
    """POST one tools/call request for `name` and return the HTTP response."""
    return rpc_call(
        client,
        "tools/call",
        {"name": name, "arguments": arguments or {}},
    )


def result_of(response) -> dict:
    """Assert a successful JSON-RPC response and return its `result`."""
    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["jsonrpc"] == "2.0"
    assert "error" not in payload
    return payload["result"]


def error_of(response) -> dict:
    """Assert a JSON-RPC error response and return its `error`."""
    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["jsonrpc"] == "2.0"
    assert "result" not in payload
    return payload["error"]


def structured_content_of(response) -> dict:
    """Return a tools/call result's structuredContent, cross-checked against
    the serialized text content — the two must always agree."""
    result = result_of(response)
    text_payload = json.loads(result["content"][0]["text"])
    assert result["structuredContent"] == text_payload
    return result["structuredContent"]


@pytest.fixture
def snapshot_universe(db):
    """Two companies with distinct indicator profiles — same shape as
    tests/test_assistant_tools.snapshot_universe so tools/call results can
    be checked against known rows."""
    from quotes.models import IndicatorSnapshot, Ticker

    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", display_name="Petrobras",
        sector="Oil", type="stock", logo="https://example.com/petr4.png",
        market_cap=400_000_000_000, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="PETR4",
        pe10=Decimal("6.5"), pfcf10=Decimal("8.0"), peg=Decimal("0.5"),
        pfcf_peg=Decimal("0.7"),
        debt_to_equity=Decimal("1.2"), debt_ex_lease_to_equity=Decimal("1.0"),
        liabilities_to_equity=Decimal("2.0"),
        current_ratio=Decimal("1.4"),
        debt_to_avg_earnings=Decimal("3.0"), debt_to_avg_fcf=Decimal("4.5"),
        market_cap=400_000_000_000, current_price=Decimal("35.75"),
    )

    Ticker.objects.create(
        symbol="WEGE3", name="Weg", display_name="WEG",
        sector="Industrial", type="stock", logo="https://example.com/wege3.png",
        market_cap=200_000_000_000, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="WEGE3",
        pe10=Decimal("35.0"), pfcf10=Decimal("40.0"), peg=Decimal("2.5"),
        pfcf_peg=Decimal("3.0"),
        debt_to_equity=Decimal("0.3"), debt_ex_lease_to_equity=Decimal("0.2"),
        liabilities_to_equity=Decimal("0.8"),
        current_ratio=Decimal("2.5"),
        debt_to_avg_earnings=Decimal("1.0"), debt_to_avg_fcf=Decimal("1.5"),
        market_cap=200_000_000_000, current_price=Decimal("42.00"),
    )


@pytest.mark.django_db
class TestMCPTransport:
    @pytest.fixture(autouse=True)
    def _default_settings(self, settings):
        settings.MCP_ENABLED = True
        cache.clear()

    def test_post_without_trailing_slash_is_served_not_redirected(self, client):
        # claude.ai POSTs to the exact URL users paste (no trailing slash);
        # an APPEND_SLASH 301 turns that POST into a body-less GET and the
        # connector falls back to a doomed OAuth registration attempt.
        response = client.post(
            "/api/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert json.loads(response.content)["result"] == {}

    def test_get_returns_405_with_allow_header(self, client):
        response = client.get(MCP_URL)
        assert response.status_code == 405
        assert response["Allow"] == "POST"

    def test_delete_returns_405(self, client):
        response = client.delete(MCP_URL)
        assert response.status_code == 405

    def test_flag_off_returns_404(self, client, settings):
        settings.MCP_ENABLED = False
        response = rpc_call(client, "ping")
        assert response.status_code == 404
        assert json.loads(response.content) == {"code": "mcp_disabled"}

    def test_invalid_json_returns_parse_error(self, client):
        response = rpc_post(client, "this is not json{")
        error = error_of(response)
        assert error["code"] == -32700

    def test_batch_request_is_rejected_as_invalid(self, client):
        response = rpc_post(
            client,
            [{"jsonrpc": "2.0", "id": 1, "method": "ping"}],
        )
        error = error_of(response)
        assert error["code"] == -32600

    def test_non_object_body_is_rejected_as_invalid(self, client):
        response = rpc_post(client, json.dumps("ping"))
        error = error_of(response)
        assert error["code"] == -32600

    def test_unknown_method_returns_method_not_found(self, client):
        response = rpc_call(client, "resources/list")
        error = error_of(response)
        assert error["code"] == -32601

    def test_notification_returns_202_with_empty_body(self, client):
        response = rpc_post(
            client,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        assert response.status_code == 202
        assert response.content == b""

    def test_string_request_id_is_echoed_back(self, client):
        response = rpc_call(client, "ping", request_id="req-abc")
        payload = json.loads(response.content)
        assert payload["id"] == "req-abc"

    def test_response_content_type_is_json(self, client):
        response = rpc_call(client, "ping")
        assert response["Content-Type"].startswith("application/json")


@pytest.mark.django_db
class TestMCPLifecycle:
    @pytest.fixture(autouse=True)
    def _default_settings(self, settings):
        settings.MCP_ENABLED = True
        cache.clear()

    def test_initialize_echoes_a_supported_protocol_version(self, client):
        requested = MCP_SUPPORTED_PROTOCOL_VERSIONS[-1]
        response = rpc_call(
            client,
            "initialize",
            {
                "protocolVersion": requested,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.0.1"},
            },
        )
        result = result_of(response)
        assert result["protocolVersion"] == requested
        assert result["capabilities"] == {"tools": {}}
        assert result["serverInfo"]["name"] == "sponda"
        assert "sponda.capital" in result["instructions"]

    def test_initialize_with_unsupported_version_falls_back_to_latest(self, client):
        response = rpc_call(
            client,
            "initialize",
            {"protocolVersion": "1999-01-01", "capabilities": {}},
        )
        result = result_of(response)
        assert result["protocolVersion"] == MCP_LATEST_PROTOCOL_VERSION

    def test_ping_returns_empty_result(self, client):
        result = result_of(rpc_call(client, "ping"))
        assert result == {}


@pytest.mark.django_db
class TestMCPToolsList:
    @pytest.fixture(autouse=True)
    def _default_settings(self, settings):
        settings.MCP_ENABLED = True
        cache.clear()

    def test_lists_the_four_agent_tools(self, client):
        result = result_of(rpc_call(client, "tools/list"))
        names = {tool["name"] for tool in result["tools"]}
        assert names == EXPECTED_TOOL_NAMES

    def test_every_tool_has_description_and_object_input_schema(self, client):
        result = result_of(rpc_call(client, "tools/list"))
        for tool in result["tools"]:
            assert tool["description"]
            assert tool["inputSchema"]["type"] == "object"

    def test_schemas_are_shared_with_the_screening_agent(self, client):
        """The MCP input schemas must be the same objects the OpenAI agent
        uses — shared source, so the two surfaces can never drift."""
        from assistant.tools import OPENAI_TOOL_SCHEMAS

        result = result_of(rpc_call(client, "tools/list"))
        schemas_by_name = {
            tool["function"]["name"]: tool["function"]["parameters"]
            for tool in OPENAI_TOOL_SCHEMAS
        }
        for tool in result["tools"]:
            assert tool["inputSchema"] == schemas_by_name[tool["name"]]


@pytest.mark.django_db
class TestMCPToolsCall:
    @pytest.fixture(autouse=True)
    def _default_settings(self, settings):
        settings.MCP_ENABLED = True
        cache.clear()

    def test_list_available_indicators_returns_catalogue_and_universe(
        self, client, snapshot_universe
    ):
        structured = structured_content_of(
            tool_call(client, "list_available_indicators")
        )
        indicator_keys = {entry["key"] for entry in structured["indicators"]}
        assert "pe10" in indicator_keys
        assert structured["countries"] == ["BR"]
        assert set(structured["sectors"]) == {"Oil", "Industrial"}
        assert structured["unsupported_examples"]

    def test_screen_companies_filters_and_returns_lean_rows(
        self, client, snapshot_universe
    ):
        response = tool_call(
            client,
            "screen_companies",
            {"filters": {"pe10": {"max": 10}}},
        )
        result = result_of(response)
        assert result["isError"] is False

        structured = structured_content_of(response)
        assert structured["count"] == 1
        assert structured["rows"][0]["ticker"] == "PETR4"
        # The agent-loop-only split must not leak to MCP clients.
        assert "full_rows" not in structured
        assert "rows_for_model" not in structured

    def test_get_company_returns_indicator_values(self, client, snapshot_universe):
        structured = structured_content_of(
            tool_call(client, "get_company", {"symbol": "wege3"})
        )
        assert structured["symbol"] == "WEGE3"
        assert structured["pe10"] == 35.0

    def test_get_company_unknown_symbol_is_a_tool_error_not_a_protocol_error(
        self, client, snapshot_universe
    ):
        response = tool_call(client, "get_company", {"symbol": "NOPE11"})
        result = result_of(response)
        assert result["isError"] is True
        assert "NOPE11" in result["content"][0]["text"]

    def test_get_fundamentals_delegates_to_quote_payload(
        self, client, snapshot_universe
    ):
        payload = {"symbol": "PETR4", "pe10": 6.5, "pe10AnnualData": [1, 2, 3]}
        with patch(
            "assistant.tools._compute_quote_payload", return_value=payload
        ) as compute:
            structured = structured_content_of(
                tool_call(client, "get_fundamentals", {"symbol": "petr4"})
            )
        compute.assert_called_once_with("PETR4", request=None)
        assert structured["symbol"] == "PETR4"
        # Heavy year-by-year series stay stripped, same as the agent path.
        assert "pe10AnnualData" not in structured

    def test_unknown_tool_returns_invalid_params(self, client):
        response = tool_call(client, "drop_all_tables")
        error = error_of(response)
        assert error["code"] == -32602

    def test_missing_tool_name_returns_invalid_params(self, client):
        response = rpc_call(client, "tools/call", {"arguments": {}})
        error = error_of(response)
        assert error["code"] == -32602


@pytest.mark.django_db
class TestMCPRateLimit:
    @pytest.fixture(autouse=True)
    def _default_settings(self, settings):
        settings.MCP_ENABLED = True
        cache.clear()

    def test_tool_calls_over_daily_cap_return_429(self, client, settings):
        settings.MCP_TOOL_CALLS_PER_DAY = 2
        with patch("assistant.mcp.client_ip_hash", return_value=FAKE_IP_HASH):
            first = tool_call(client, "list_available_indicators")
            second = tool_call(client, "list_available_indicators")
            third = tool_call(client, "list_available_indicators")
        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429

    def test_lifecycle_methods_are_not_rate_limited(self, client, settings):
        settings.MCP_TOOL_CALLS_PER_DAY = 1
        with patch("assistant.mcp.client_ip_hash", return_value=FAKE_IP_HASH):
            tool_call(client, "list_available_indicators")
            ping = rpc_call(client, "ping")
            listing = rpc_call(client, "tools/list")
        assert ping.status_code == 200
        assert listing.status_code == 200

    def test_fundamentals_has_its_own_tighter_cap(
        self, client, settings, snapshot_universe
    ):
        settings.MCP_TOOL_CALLS_PER_DAY = 100
        settings.MCP_FUNDAMENTALS_CALLS_PER_DAY = 1
        payload = {"symbol": "PETR4", "pe10": 6.5}
        with (
            patch("assistant.tools._compute_quote_payload", return_value=payload),
            patch("assistant.mcp.client_ip_hash", return_value=FAKE_IP_HASH),
        ):
            first = tool_call(client, "get_fundamentals", {"symbol": "PETR4"})
            second = tool_call(client, "get_fundamentals", {"symbol": "PETR4"})
            cheap = tool_call(client, "get_company", {"symbol": "PETR4"})
        assert first.status_code == 200
        assert second.status_code == 429
        # The tighter cap must not block the cheap tools.
        assert cheap.status_code == 200

    def test_distinct_ips_have_independent_budgets(self, client, settings):
        settings.MCP_TOOL_CALLS_PER_DAY = 1
        with patch("assistant.mcp.client_ip_hash", return_value="a" * 64):
            tool_call(client, "list_available_indicators")
            blocked = tool_call(client, "list_available_indicators")
        with patch("assistant.mcp.client_ip_hash", return_value="b" * 64):
            fresh = tool_call(client, "list_available_indicators")
        assert blocked.status_code == 429
        assert fresh.status_code == 200
