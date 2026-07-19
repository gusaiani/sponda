"""Tests for the screening agent loop (assistant/agent.py).

The loop is exercised entirely against fake OpenAI streams — the same
MagicMock idiom as test_assistant_view.py — and a patched execute_tool,
so no network and no DB rows are needed except where noted.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from openai import APITimeoutError, RateLimitError

from assistant.agent import (
    AnswerToken,
    Completed,
    Failed,
    InterpretedFilters,
    ScreenResults,
    ToolCallStarted,
    run_screening_agent,
)
from assistant.prompts import SCREENING_SYSTEM_PROMPT


def make_content_chunk(text):
    """One streamed chunk carrying answer text."""
    delta = MagicMock(content=text, tool_calls=None)
    return MagicMock(choices=[MagicMock(delta=delta)], usage=None)


def make_tool_call_chunk(index, call_id, function_name, arguments_fragment):
    """One streamed chunk carrying a tool-call delta.

    function_name/call_id are None on continuation chunks — OpenAI sends
    the name once, then argument fragments.
    """
    function = MagicMock(arguments=arguments_fragment)
    # MagicMock(name=...) sets the mock's own name, so assign explicitly.
    function.name = function_name
    tool_call_delta = MagicMock(index=index, id=call_id, function=function)
    delta = MagicMock(content=None, tool_calls=[tool_call_delta])
    return MagicMock(choices=[MagicMock(delta=delta)], usage=None)


def make_usage_chunk(input_tokens, output_tokens):
    """The final include_usage chunk: no choices, only usage."""
    usage = MagicMock(prompt_tokens=input_tokens, completion_tokens=output_tokens)
    return MagicMock(choices=[], usage=usage)


def make_client(streams):
    """A fake OpenAI client whose create() returns each stream in turn."""
    client = MagicMock()
    client.chat.completions.create.side_effect = [iter(s) for s in streams]
    return client


def run_agent(client, execute_tool=None, question="cheap Brazilian companies",
              history_messages=None, locale="en"):
    execute_tool = execute_tool or MagicMock()
    with patch("assistant.agent.get_openai_client", return_value=client), \
         patch("assistant.agent.execute_tool", execute_tool):
        events = list(
            run_screening_agent(
                question=question,
                history_messages=history_messages or [],
                locale=locale,
            )
        )
    return events, client, execute_tool


SCREEN_ARGUMENTS = {
    "filters": {"pe10": {"max": 8}},
    "countries": ["BR"],
    "sort": "pe10",
    "limit": 20,
}

SCREEN_RESULT = {
    "count": 2,
    "rows_for_model": [{"ticker": "PETR4", "pe10": 4.2}],
    "full_rows": [{"ticker": "PETR4", "pe10": 4.2, "ratings": {"overall": "good"}}],
}


class TestDirectAnswer:
    def test_streams_tokens_and_completes_with_usage(self):
        stream = [
            make_content_chunk("Scre"),
            make_content_chunk("ening: none needed"),
            make_usage_chunk(100, 20),
        ]
        events, _, _ = run_agent(make_client([stream]))

        tokens = [e.text for e in events if isinstance(e, AnswerToken)]
        assert tokens == ["Scre", "ening: none needed"]
        completed = events[-1]
        assert isinstance(completed, Completed)
        assert completed.input_tokens == 100
        assert completed.output_tokens == 20

    def test_system_prompt_history_and_user_message(self):
        history = [
            {"role": "user", "content": "Question: previous"},
            {"role": "assistant", "content": "previous answer"},
        ]
        stream = [make_content_chunk("ok"), make_usage_chunk(1, 1)]
        _, client, _ = run_agent(
            make_client([stream]), history_messages=history, locale="pt",
            question="empresas baratas",
        )

        kwargs = client.chat.completions.create.call_args.kwargs
        messages = kwargs["messages"]
        assert messages[0] == {"role": "system", "content": SCREENING_SYSTEM_PROMPT}
        assert messages[1:3] == history
        assert messages[3]["role"] == "user"
        assert "locale: pt" in messages[3]["content"]
        assert "empresas baratas" in messages[3]["content"]
        assert kwargs["stream"] is True
        assert kwargs["stream_options"] == {"include_usage": True}
        assert kwargs["tools"]  # tool schemas attached


class TestToolCalling:
    def test_screen_round_emits_filters_results_and_answer(self):
        arguments_json = json.dumps(SCREEN_ARGUMENTS)
        first_stream = [
            # Name arrives first, arguments split across two chunks.
            make_tool_call_chunk(0, "call_1", "screen_companies",
                                 arguments_json[:15]),
            make_tool_call_chunk(0, None, None, arguments_json[15:]),
            make_usage_chunk(200, 30),
        ]
        second_stream = [
            make_content_chunk("Screening: country=BR, pe10 < 8"),
            make_usage_chunk(300, 40),
        ]
        execute_tool = MagicMock(return_value=SCREEN_RESULT)
        events, client, execute_tool = run_agent(
            make_client([first_stream, second_stream]), execute_tool,
        )

        started = [e for e in events if isinstance(e, ToolCallStarted)]
        assert [e.name for e in started] == ["screen_companies"]

        interpreted = [e for e in events if isinstance(e, InterpretedFilters)]
        assert len(interpreted) == 1
        assert interpreted[0].arguments == SCREEN_ARGUMENTS

        results = [e for e in events if isinstance(e, ScreenResults)]
        assert len(results) == 1
        assert results[0].count == 2
        assert results[0].rows == SCREEN_RESULT["full_rows"]

        execute_tool.assert_called_once_with("screen_companies", SCREEN_ARGUMENTS)

        # The model sees trimmed rows, never full_rows.
        second_call_messages = (
            client.chat.completions.create.call_args_list[1].kwargs["messages"]
        )
        tool_messages = [m for m in second_call_messages if m["role"] == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0]["tool_call_id"] == "call_1"
        assert "rows_for_model" not in tool_messages[0]["content"]
        assert "full_rows" not in tool_messages[0]["content"]
        assert "PETR4" in tool_messages[0]["content"]

        completed = events[-1]
        assert isinstance(completed, Completed)
        assert completed.input_tokens == 500
        assert completed.output_tokens == 70

    def test_parallel_tool_calls_all_execute(self):
        first_stream = [
            make_tool_call_chunk(0, "call_a", "get_company",
                                 json.dumps({"symbol": "PETR4"})),
            make_tool_call_chunk(1, "call_b", "get_company",
                                 json.dumps({"symbol": "VALE3"})),
            make_usage_chunk(10, 5),
        ]
        second_stream = [make_content_chunk("done"), make_usage_chunk(10, 5)]
        execute_tool = MagicMock(return_value={"ticker": "X"})
        events, client, execute_tool = run_agent(
            make_client([first_stream, second_stream]), execute_tool,
        )

        assert execute_tool.call_count == 2
        second_call_messages = (
            client.chat.completions.create.call_args_list[1].kwargs["messages"]
        )
        tool_call_ids = [
            m["tool_call_id"] for m in second_call_messages if m["role"] == "tool"
        ]
        assert tool_call_ids == ["call_a", "call_b"]

    def test_invalid_tool_arguments_fed_back_as_error(self):
        first_stream = [
            make_tool_call_chunk(0, "call_1", "screen_companies", "{not json"),
            make_usage_chunk(10, 5),
        ]
        second_stream = [make_content_chunk("sorry"), make_usage_chunk(10, 5)]
        execute_tool = MagicMock()
        events, client, execute_tool = run_agent(
            make_client([first_stream, second_stream]), execute_tool,
        )

        execute_tool.assert_not_called()
        second_call_messages = (
            client.chat.completions.create.call_args_list[1].kwargs["messages"]
        )
        tool_messages = [m for m in second_call_messages if m["role"] == "tool"]
        assert "error" in tool_messages[0]["content"]
        # A broken tool call never counts as an interpreted filter set.
        assert not [e for e in events if isinstance(e, InterpretedFilters)]

    def test_round_limit_forces_final_answer_without_tools(self, settings):
        settings.ASSISTANT_MAX_TOOL_ROUNDS = 2
        tool_stream = lambda call_id: [
            make_tool_call_chunk(0, call_id, "get_company",
                                 json.dumps({"symbol": "PETR4"})),
            make_usage_chunk(10, 5),
        ]
        forced_final = [make_content_chunk("from data so far"),
                        make_usage_chunk(10, 5)]
        execute_tool = MagicMock(return_value={"ticker": "PETR4"})
        events, client, _ = run_agent(
            make_client([tool_stream("c1"), tool_stream("c2"), forced_final]),
            execute_tool,
        )

        assert client.chat.completions.create.call_count == 3
        final_kwargs = client.chat.completions.create.call_args_list[2].kwargs
        assert final_kwargs["tool_choice"] == "none"
        assert isinstance(events[-1], Completed)
        tokens = [e.text for e in events if isinstance(e, AnswerToken)]
        assert tokens == ["from data so far"]


class TestFailures:
    def test_timeout_yields_failed_event(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = APITimeoutError(
            request=MagicMock()
        )
        events, _, _ = run_agent(client)
        assert isinstance(events[-1], Failed)
        assert events[-1].code == "upstream_timeout"

    def test_rate_limit_yields_failed_event(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RateLimitError(
            "rate limited", response=MagicMock(status_code=429), body=None
        )
        events, _, _ = run_agent(client)
        assert isinstance(events[-1], Failed)
        assert events[-1].code == "rate_limited"


class TestNetworkFailures:
    def test_mid_stream_httpx_timeout_yields_upstream_timeout(self):
        import httpx

        def broken_stream():
            yield make_content_chunk("partial")
            raise httpx.ReadTimeout("mid-stream read timeout")

        client = MagicMock()
        client.chat.completions.create.return_value = broken_stream()
        with patch("assistant.agent.get_openai_client", return_value=client), \
             patch("assistant.agent.execute_tool", MagicMock()):
            events = list(run_screening_agent(
                question="q", history_messages=[], locale="en",
            ))

        assert isinstance(events[-1], Failed)
        assert events[-1].code == "upstream_timeout"

    def test_mid_stream_httpx_protocol_error_yields_internal(self):
        import httpx

        def broken_stream():
            yield make_content_chunk("partial")
            raise httpx.RemoteProtocolError("connection torn down")

        client = MagicMock()
        client.chat.completions.create.return_value = broken_stream()
        with patch("assistant.agent.get_openai_client", return_value=client), \
             patch("assistant.agent.execute_tool", MagicMock()):
            events = list(run_screening_agent(
                question="q", history_messages=[], locale="en",
            ))

        assert isinstance(events[-1], Failed)
        assert events[-1].code == "internal"
