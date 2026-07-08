"""Public MCP server: Sponda's screening tools for any agent, not just ours.

One stateless Streamable-HTTP endpoint (POST /api/mcp/) speaking JSON-RPC
2.0. No sessions, no SSE, no server-initiated messages — every request is a
single POST answered with a single JSON body, which is the simplest shape
the MCP spec allows and all major clients (Claude, Cursor, the inspector)
handle.

The tool surface is assistant.tools verbatim: the same JSON Schemas the
OpenAI screening agent binds are served from tools/list, and tools/call
dispatches into the same executors. Shared source means the two surfaces —
in-house agent and public MCP — can never drift apart.

Cost posture: these tools call no LLM, so the only spend is database work
plus, for get_fundamentals, a live market-data provider fetch. Both are
bounded by per-IP daily caps (cache-backed counters), with a tighter
sub-cap on get_fundamentals since it is the one expensive executor.
"""
from __future__ import annotations

import json

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from assistant.tools import (
    OPENAI_TOOL_SCHEMAS,
    execute_tool,
)
from quotes.client_ip import client_ip_hash

# Newest first. initialize echoes the client's requested version when we
# support it and falls back to the newest otherwise, per the MCP spec's
# version-negotiation rules.
MCP_SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
MCP_LATEST_PROTOCOL_VERSION = MCP_SUPPORTED_PROTOCOL_VERSIONS[0]

MCP_SERVER_INFO = {
    "name": "sponda",
    "title": "Sponda — fundamental analysis for value investors",
    "version": "1.0.0",
}

MCP_INSTRUCTIONS = (
    "Screen ~23,000 listed companies by Sponda's inflation-adjusted value "
    "indicators (P/E10, P/FCF10, PEG, leverage and liquidity ratios). Call "
    "list_available_indicators first to learn the exact indicator keys, "
    "countries, and sectors; screen_companies to filter and rank; "
    "get_company for one company's current values; get_fundamentals only "
    "for a deep follow-up on a single company — it is expensive and "
    "rate-limited. All data is served from sponda.capital."
)

# JSON-RPC 2.0 error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602

EXPENSIVE_TOOL_NAME = "get_fundamentals"

# The agent loop's screen result carries a token-trimmed copy for the model
# plus untrimmed rows for the frontend table. An MCP client is the model, so
# it gets one lean list under a plain name and never the duplicated payload.
SCREEN_AGENT_ONLY_KEYS = ("rows_for_model", "full_rows")

MCP_TOOL_DEFINITIONS = [
    {
        "name": schema["function"]["name"],
        "description": schema["function"]["description"],
        "inputSchema": schema["function"]["parameters"],
    }
    for schema in OPENAI_TOOL_SCHEMAS
]

MCP_TOOL_NAMES = frozenset(
    definition["name"] for definition in MCP_TOOL_DEFINITIONS
)


def _rpc_result(request_id, result: dict) -> JsonResponse:
    return JsonResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _rpc_error(request_id, code: int, message: str) -> JsonResponse:
    return JsonResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    })


def _daily_counter_key(scope: str, ip_hash: str) -> str:
    day = timezone.now().strftime("%Y%m%d")
    return f"mcp:{scope}:{ip_hash}:{day}"


# Counter TTL outlives its calendar-day key by a wide margin; the date in
# the key is what actually rolls the window over at midnight.
COUNTER_TTL_SECONDS = 2 * 24 * 60 * 60


def _increment_exceeds_cap(scope: str, ip_hash: str, cap: int) -> bool:
    """Count one call against `scope` for this IP and report if it went over.

    cache.add is a no-op when the key exists, so add-then-incr is safe under
    concurrency: worst case two racing first calls both incr and the counter
    starts at 2, which only ever under-serves by one call — never over.
    """
    key = _daily_counter_key(scope, ip_hash)
    cache.add(key, 0, timeout=COUNTER_TTL_SECONDS)
    calls_today = cache.incr(key)
    return calls_today > cap


def _negotiated_protocol_version(params: dict) -> str:
    requested = params.get("protocolVersion")
    if requested in MCP_SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return MCP_LATEST_PROTOCOL_VERSION


def _handle_initialize(request_id, params: dict) -> JsonResponse:
    return _rpc_result(request_id, {
        "protocolVersion": _negotiated_protocol_version(params),
        "capabilities": {"tools": {}},
        "serverInfo": MCP_SERVER_INFO,
        "instructions": MCP_INSTRUCTIONS,
    })


def _handle_tools_list(request_id) -> JsonResponse:
    return _rpc_result(request_id, {"tools": MCP_TOOL_DEFINITIONS})


def _shape_result_for_mcp(tool_name: str, tool_result: dict) -> dict:
    """Adapt one executor result to what an MCP client should receive."""
    if tool_name == "screen_companies" and "error" not in tool_result:
        shaped = {
            key: value
            for key, value in tool_result.items()
            if key not in SCREEN_AGENT_ONLY_KEYS
        }
        shaped["rows"] = tool_result["rows_for_model"]
        return shaped
    return tool_result


def _handle_tools_call(request, request_id, params: dict):
    tool_name = params.get("name")
    if tool_name not in MCP_TOOL_NAMES:
        return _rpc_error(
            request_id, INVALID_PARAMS, f"Unknown tool: {tool_name!r}"
        )

    ip_hash = client_ip_hash(request)
    if _increment_exceeds_cap(
        "calls", ip_hash, settings.MCP_TOOL_CALLS_PER_DAY
    ):
        return HttpResponse(status=429)
    if tool_name == EXPENSIVE_TOOL_NAME and _increment_exceeds_cap(
        "fundamentals", ip_hash, settings.MCP_FUNDAMENTALS_CALLS_PER_DAY
    ):
        return HttpResponse(status=429)

    arguments = params.get("arguments")
    if arguments is not None and not isinstance(arguments, dict):
        return _rpc_error(
            request_id, INVALID_PARAMS, "arguments must be an object"
        )

    tool_result = _shape_result_for_mcp(
        tool_name, execute_tool(tool_name, arguments or {})
    )

    # Executor failures ("unknown symbol") are tool results with
    # isError=true, not protocol errors — the calling model is meant to
    # read them and adjust, exactly as the in-house agent loop does.
    return _rpc_result(request_id, {
        "content": [{
            "type": "text",
            "text": json.dumps(tool_result, ensure_ascii=False),
        }],
        "structuredContent": tool_result,
        "isError": "error" in tool_result,
    })


@csrf_exempt
# CSRF off for the same reason as the assistant endpoints: MCP clients are
# programmatic JSON POSTers, not browser forms.
def mcp_endpoint(request):
    """Single stateless MCP route: parse one JSON-RPC message, answer it."""
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})

    if not settings.MCP_ENABLED:
        return JsonResponse({"code": "mcp_disabled"}, status=404)

    try:
        message = json.loads(request.body or b"")
    except json.JSONDecodeError:
        return _rpc_error(None, PARSE_ERROR, "Invalid JSON")

    if not isinstance(message, dict):
        # Also rejects batches: JSON-RPC batching was dropped from MCP in
        # 2025-06-18, and a stateless single-message server never needs it.
        return _rpc_error(
            None, INVALID_REQUEST, "Expected a single JSON-RPC request object"
        )

    method = message.get("method")
    params = message.get("params") or {}

    if "id" not in message:
        # A notification. Nothing we serve requires acting on any of them
        # (no sessions, no subscriptions), so acknowledge and move on.
        return HttpResponse(status=202)

    request_id = message["id"]

    if method == "initialize":
        return _handle_initialize(request_id, params)
    if method == "ping":
        return _rpc_result(request_id, {})
    if method == "tools/list":
        return _handle_tools_list(request_id)
    if method == "tools/call":
        return _handle_tools_call(request, request_id, params)

    return _rpc_error(
        request_id, METHOD_NOT_FOUND, f"Method not supported: {method!r}"
    )
