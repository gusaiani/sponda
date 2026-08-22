"""The Anthropic screening agent loop (slackbot/anthropic_agent.py).

Mirror of the OpenAI loop in assistant/agent.py: same tool executors,
same event vocabulary, non-streaming rounds (Slack needs a final text,
not tokens). Exercised entirely against a fake Anthropic client.
"""
import json
from unittest.mock import MagicMock, patch

from anthropic import AuthenticationError, RateLimitError

from assistant.agent import AnswerToken, Completed, Failed, ToolCallStarted
from assistant.tools import OPENAI_TOOL_SCHEMAS
from slackbot.anthropic_agent import (
    ANTHROPIC_TOOL_SCHEMAS,
    run_anthropic_screening_agent,
)


def text_block(text):
    return MagicMock(type="text", text=text)


def tool_use_block(block_id, name, arguments):
    # MagicMock(name=...) sets the mock's own name, so assign explicitly.
    block = MagicMock(type="tool_use", id=block_id, input=arguments)
    block.name = name
    return block


def make_response(blocks, stop_reason="end_turn", input_tokens=10, output_tokens=5):
    return MagicMock(
        content=blocks,
        stop_reason=stop_reason,
        usage=MagicMock(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def run_agent(responses, execute_tool=None, question="cheap BR banks?"):
    client = MagicMock()
    if isinstance(responses, list):
        client.messages.create.side_effect = responses
    else:
        client.messages.create.side_effect = responses  # an exception
    execute_tool = execute_tool or MagicMock(return_value={"count": 0})
    with patch("slackbot.anthropic_agent.Anthropic", return_value=client), \
         patch("assistant.agent.execute_tool", execute_tool):
        events = list(
            run_anthropic_screening_agent(
                question=question,
                history_messages=[],
                locale="en",
                api_key="sk-ant-user",
            )
        )
    return events, client, execute_tool


class TestSchemaConversion:
    def test_every_openai_tool_has_an_anthropic_twin(self):
        openai_names = [s["function"]["name"] for s in OPENAI_TOOL_SCHEMAS]
        anthropic_names = [s["name"] for s in ANTHROPIC_TOOL_SCHEMAS]
        assert anthropic_names == openai_names

    def test_parameters_become_input_schema(self):
        for openai_schema, anthropic_schema in zip(
            OPENAI_TOOL_SCHEMAS, ANTHROPIC_TOOL_SCHEMAS
        ):
            assert anthropic_schema["input_schema"] == openai_schema["function"]["parameters"]
            assert anthropic_schema["description"] == openai_schema["function"]["description"]


class TestAgentLoop:
    def test_direct_answer_yields_tokens_then_totals(self):
        events, client, _ = run_agent(
            [make_response([text_block("Cheap: ")], input_tokens=100, output_tokens=30)]
        )
        assert events[0] == AnswerToken("Cheap: ")
        assert events[-1] == Completed(input_tokens=100, output_tokens=30)
        assert client.messages.create.call_count == 1

    def test_tool_round_executes_and_feeds_result_back(self):
        arguments = {"filters": {"pe10": {"max": 8}}}
        execute_tool = MagicMock(return_value={"count": 1, "rows_for_model": [{"symbol": "BBAS3"}]})
        events, client, execute_tool = run_agent(
            [
                make_response(
                    [tool_use_block("tu1", "screen_companies", arguments)],
                    stop_reason="tool_use",
                ),
                make_response([text_block("BBAS3 stands out.")]),
            ],
            execute_tool=execute_tool,
        )

        execute_tool.assert_called_once_with("screen_companies", arguments)
        assert ToolCallStarted("screen_companies") in events
        assert AnswerToken("BBAS3 stands out.") in events
        assert isinstance(events[-1], Completed)
        # Token totals accumulate across rounds.
        assert events[-1].input_tokens == 20

        # The tool result went back to the model as a tool_result block.
        second_call_messages = client.messages.create.call_args.kwargs["messages"]
        tool_result = second_call_messages[-1]["content"][0]
        assert tool_result["type"] == "tool_result"
        assert tool_result["tool_use_id"] == "tu1"
        assert "rows" in json.loads(tool_result["content"]) or "count" in json.loads(tool_result["content"])

    def test_final_round_forbids_further_tool_calls(self, settings):
        settings.ASSISTANT_MAX_TOOL_ROUNDS = 1
        arguments = {"symbol": "PETR4"}
        events, client, _ = run_agent(
            [
                make_response(
                    [tool_use_block("tu1", "get_company", arguments)],
                    stop_reason="tool_use",
                ),
                make_response([text_block("done")]),
            ]
        )
        final_call = client.messages.create.call_args.kwargs
        assert final_call["tool_choice"] == {"type": "none"}

    def test_refusal_stop_reason_fails_cleanly(self):
        events, _, _ = run_agent([make_response([], stop_reason="refusal")])
        assert events[-1] == Failed("refusal")

    def test_invalid_key_fails_with_specific_code(self):
        error = AuthenticationError(
            "bad key", response=MagicMock(status_code=401), body=None
        )
        events, _, _ = run_agent(error)
        assert events == [Failed("invalid_api_key")]

    def test_rate_limit_fails_with_specific_code(self):
        error = RateLimitError(
            "slow down", response=MagicMock(status_code=429), body=None
        )
        events, _, _ = run_agent(error)
        assert events == [Failed("rate_limited")]

    def test_client_is_built_with_the_users_key(self):
        with patch("slackbot.anthropic_agent.Anthropic") as anthropic_class:
            anthropic_class.return_value.messages.create.side_effect = [
                make_response([text_block("hi")])
            ]
            list(
                run_anthropic_screening_agent(
                    question="q", history_messages=[], locale="en",
                    api_key="sk-ant-user",
                )
            )
        assert anthropic_class.call_args.kwargs["api_key"] == "sk-ant-user"
