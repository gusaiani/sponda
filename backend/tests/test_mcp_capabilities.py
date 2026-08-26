"""Tool annotations, prompts, and a company count that is not typed by hand.

Annotations are not cosmetic. Anthropic's Connectors Directory rejects any
server whose tools lack a `title` and a read-only or destructive hint, and
clients use `readOnlyHint` to decide whether a call needs the user to confirm
it. Without them, a read-only screener is treated as potentially destructive.
"""
import json

import pytest

from assistant.mcp import MCP_PROMPT_DEFINITIONS, MCP_TOOL_DEFINITIONS
from quotes.models import IndicatorSnapshot, Ticker


def rpc(client, method, params=None, request_id=1):
    response = client.post(
        "/api/mcp",
        data=json.dumps({
            "jsonrpc": "2.0", "id": request_id, "method": method,
            **({"params": params} if params is not None else {}),
        }),
        content_type="application/json",
    )
    return json.loads(response.content)


class TestToolAnnotations:
    def test_every_tool_has_a_title(self):
        for tool in MCP_TOOL_DEFINITIONS:
            assert tool.get("title"), f"{tool['name']} has no title"

    def test_every_tool_declares_read_only_or_destructive(self):
        for tool in MCP_TOOL_DEFINITIONS:
            annotations = tool.get("annotations") or {}
            assert (
                "readOnlyHint" in annotations or "destructiveHint" in annotations
            ), f"{tool['name']} declares neither hint"

    def test_every_tool_is_read_only(self):
        # Sponda's MCP surface only ever reads. If a writing tool is added,
        # this test should fail and force the annotation to be considered.
        for tool in MCP_TOOL_DEFINITIONS:
            assert tool["annotations"]["readOnlyHint"] is True, tool["name"]

    def test_annotations_carry_a_title_too(self):
        # The spec allows the title on the tool and inside annotations;
        # clients differ on which they read.
        for tool in MCP_TOOL_DEFINITIONS:
            assert tool["annotations"].get("title"), tool["name"]

    def test_titles_are_human_readable_not_the_tool_name(self):
        for tool in MCP_TOOL_DEFINITIONS:
            assert tool["title"] != tool["name"], tool["name"]
            assert "_" not in tool["title"], tool["name"]


@pytest.mark.django_db
class TestToolsListOverTheWire:
    def test_annotations_survive_serialisation(self, client):
        tools = rpc(client, "tools/list")["result"]["tools"]
        for tool in tools:
            assert tool["annotations"]["readOnlyHint"] is True
            assert tool["title"]


@pytest.mark.django_db
class TestPrompts:
    def test_initialize_advertises_the_prompts_capability(self, client):
        capabilities = rpc(client, "initialize", {})["result"]["capabilities"]
        assert "prompts" in capabilities

    def test_prompts_list_returns_the_catalogue(self, client):
        prompts = rpc(client, "prompts/list")["result"]["prompts"]
        assert len(prompts) == len(MCP_PROMPT_DEFINITIONS)
        for prompt in prompts:
            assert prompt["name"]
            assert prompt["description"]

    def test_every_prompt_documents_its_arguments(self):
        for prompt in MCP_PROMPT_DEFINITIONS:
            for argument in prompt.get("arguments", []):
                assert argument["name"]
                assert argument["description"]

    def test_prompts_get_returns_a_user_message(self, client):
        name = MCP_PROMPT_DEFINITIONS[0]["name"]
        result = rpc(client, "prompts/get", {"name": name, "arguments": {}})["result"]
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"]["type"] == "text"

    def test_prompts_get_interpolates_arguments(self, client):
        result = rpc(client, "prompts/get", {
            "name": "screen_for_value",
            "arguments": {"country": "BR", "max_pe10": "8"},
        })["result"]
        text = result["messages"][0]["content"]["text"]
        assert "BR" in text
        assert "8" in text

    def test_prompts_get_tolerates_missing_arguments(self, client):
        # A client may call with none; the prompt must still be usable.
        result = rpc(client, "prompts/get", {"name": "screen_for_value"})["result"]
        assert result["messages"][0]["content"]["text"]

    def test_unknown_prompt_is_an_error_not_a_crash(self, client):
        assert "error" in rpc(client, "prompts/get", {"name": "nope"})


@pytest.mark.django_db
class TestInstructionsCount:
    def test_states_the_real_covered_company_count(self, client):
        Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock")
        IndicatorSnapshot.objects.create(ticker="PETR4")

        instructions = rpc(client, "initialize", {})["result"]["instructions"]
        assert "1 listed" in instructions or "1 companies" in instructions

    def test_never_repeats_the_stale_hardcoded_figure(self, client):
        instructions = rpc(client, "initialize", {})["result"]["instructions"]
        assert "23,000" not in instructions
        assert "23000" not in instructions

    def test_survives_an_empty_database(self, client):
        # No companies is not a reason to fail a handshake.
        instructions = rpc(client, "initialize", {})["result"]["instructions"]
        assert "Sponda" in instructions or "indicators" in instructions
