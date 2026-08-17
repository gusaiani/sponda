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
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from assistant.models import McpCall
from assistant.tools import (
    OPENAI_TOOL_SCHEMAS,
    execute_tool,
)
from quotes.client_ip import client_ip_hash

logger = logging.getLogger(__name__)

# Newest first. initialize echoes the client's requested version when we
# support it and falls back to the newest otherwise, per the MCP spec's
# version-negotiation rules.
MCP_SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
MCP_LATEST_PROTOCOL_VERSION = MCP_SUPPORTED_PROTOCOL_VERSIONS[0]

# The address users paste into their MCP client. Deliberately absolute rather
# than derived from SITE_BASE_URL: the endpoint is a public fact about the
# deployment, and an announcement email sent from any box must advertise the
# real one, never a localhost URL.
MCP_PUBLIC_ENDPOINT_URL = "https://sponda.capital/api/mcp/"

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
    """Run one tool. Returns (response, the caller could not use it)."""
    tool_name = params.get("name")
    if tool_name not in MCP_TOOL_NAMES:
        return _rpc_error(
            request_id, INVALID_PARAMS, f"Unknown tool: {tool_name!r}"
        ), True

    ip_hash = client_ip_hash(request)
    if _increment_exceeds_cap(
        "calls", ip_hash, settings.MCP_TOOL_CALLS_PER_DAY
    ):
        return HttpResponse(status=429), True
    if tool_name == EXPENSIVE_TOOL_NAME and _increment_exceeds_cap(
        "fundamentals", ip_hash, settings.MCP_FUNDAMENTALS_CALLS_PER_DAY
    ):
        return HttpResponse(status=429), True

    arguments = params.get("arguments")
    if arguments is not None and not isinstance(arguments, dict):
        return _rpc_error(
            request_id, INVALID_PARAMS, "arguments must be an object"
        ), True

    tool_result = _shape_result_for_mcp(
        tool_name, execute_tool(tool_name, arguments or {})
    )
    tool_failed = "error" in tool_result

    # Executor failures ("unknown symbol") are tool results with
    # isError=true, not protocol errors — the calling model is meant to
    # read them and adjust, exactly as the in-house agent loop does.
    return _rpc_result(request_id, {
        "content": [{
            "type": "text",
            "text": json.dumps(tool_result, ensure_ascii=False),
        }],
        "structuredContent": tool_result,
        "isError": tool_failed,
    }), tool_failed


def _dispatch(request, request_id, method: str, params: dict):
    """Route one JSON-RPC request. Returns (response, failed)."""
    if method == "initialize":
        return _handle_initialize(request_id, params), False
    if method == "ping":
        return _rpc_result(request_id, {}), False
    if method == "tools/list":
        return _handle_tools_list(request_id), False
    if method == "tools/call":
        return _handle_tools_call(request, request_id, params)
    return _rpc_error(
        request_id, METHOD_NOT_FOUND, f"Method not supported: {method!r}"
    ), True


def _column_safe(value, field_name: str) -> str:
    """Coerce a client-supplied value to what its column can actually hold.

    Everything recorded below the protocol line is attacker-controlled: a
    client is free to send a 10 KB clientInfo.name, and on PostgreSQL that
    is a write error rather than a truncation.
    """
    max_length = McpCall._meta.get_field(field_name).max_length
    return str(value if value is not None else "")[:max_length]


def _record_call(
    request, *, method, params: dict, failed: bool, latency_ms: int,
    rate_limited: bool = False,
) -> None:
    """Log one answered MCP message for the usage dashboard.

    Best effort by design: a statistic is never worth failing a tool call
    that already succeeded, so every failure here is logged and swallowed,
    and a per-IP daily cap keeps an unauthenticated caller from growing the
    table without bound through the uncapped lifecycle methods.
    """
    is_handshake = method == McpCall.METHOD_INITIALIZE
    client_info = params.get("clientInfo") if is_handshake else None
    if not isinstance(client_info, dict):
        client_info = {}

    try:
        ip_hash = client_ip_hash(request)
        if _increment_exceeds_cap(
            "recorded", ip_hash, settings.MCP_RECORDED_CALLS_PER_DAY
        ):
            return

        McpCall.objects.create(
            method=_column_safe(method, "method"),
            tool_name=(
                _column_safe(params.get("name"), "tool_name")
                if method == McpCall.METHOD_TOOLS_CALL else ""
            ),
            client_name=_column_safe(client_info.get("name"), "client_name"),
            client_version=_column_safe(
                client_info.get("version"), "client_version"
            ),
            protocol_version=(
                _column_safe(params.get("protocolVersion"), "protocol_version")
                if is_handshake else ""
            ),
            user_agent=_column_safe(
                request.META.get("HTTP_USER_AGENT"), "user_agent"
            ),
            ip_hash=ip_hash,
            failed=failed,
            rate_limited=rate_limited,
            latency_ms=latency_ms,
        )
    except Exception:
        logger.warning("Failed to record MCP call", exc_info=True)


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
    params = message.get("params")
    if not isinstance(params, dict):
        # `params` is optional and, per JSON-RPC, may also be an array. No
        # method here takes positional params, so anything that is not an
        # object is treated as absent rather than crashing on .get().
        params = {}

    started_at = time.monotonic()

    if "id" not in message:
        # A notification. Nothing we serve requires acting on any of them
        # (no sessions, no subscriptions), so acknowledge and move on.
        response, failed = HttpResponse(status=202), False
    else:
        response, failed = _dispatch(request, message["id"], method, params)

    _record_call(
        request,
        method=method,
        params=params,
        failed=failed,
        rate_limited=response.status_code == 429,
        latency_ms=round((time.monotonic() - started_at) * 1000),
    )
    return response
