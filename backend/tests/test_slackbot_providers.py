"""Provider dispatch for BYOK agents (slackbot/providers.py).

run_agent_for_provider() turns the event stream either agent loop yields
into one AgentAnswer the Celery task can post. The tests drive it with
hand-built event lists — provider loops are covered by their own suites.
"""
from unittest.mock import MagicMock, patch

import pytest

from assistant.agent import AnswerToken, Completed, Failed, ToolCallStarted
from slackbot.providers import run_agent_for_provider

RUN_KWARGS = {
    "api_key": "sk-user",
    "question": "cheap banks?",
    "history_messages": [],
    "locale": "en",
}


def events_generator(events):
    def fake_run(**kwargs):
        yield from events
    return fake_run


class TestRunAgentForProvider:
    def test_collects_tokens_and_totals(self):
        events = [AnswerToken("Cheap "), AnswerToken("banks."), Completed(50, 10)]
        with patch(
            "slackbot.providers.run_screening_agent", events_generator(events)
        ):
            answer = run_agent_for_provider(provider="openai", **RUN_KWARGS)
        assert answer.text == "Cheap banks."
        assert answer.input_tokens == 50
        assert answer.output_tokens == 10
        assert answer.error_code is None

    def test_preamble_before_a_tool_call_is_dropped(self):
        # "Let me check..." chatter before a tool round is not the answer.
        events = [
            AnswerToken("Let me screen that."),
            ToolCallStarted("screen_companies"),
            AnswerToken("BBAS3 is the cheapest."),
            Completed(1, 1),
        ]
        with patch(
            "slackbot.providers.run_screening_agent", events_generator(events)
        ):
            answer = run_agent_for_provider(provider="openai", **RUN_KWARGS)
        assert answer.text == "BBAS3 is the cheapest."

    def test_failure_surfaces_error_code(self):
        events = [Failed("invalid_api_key")]
        with patch(
            "slackbot.providers.run_screening_agent", events_generator(events)
        ):
            answer = run_agent_for_provider(provider="openai", **RUN_KWARGS)
        assert answer.error_code == "invalid_api_key"
        assert answer.text == ""

    def test_openai_agent_gets_a_client_built_with_the_users_key(self):
        captured = {}

        def fake_run(**kwargs):
            captured.update(kwargs)
            yield Completed(1, 1)

        with patch("slackbot.providers.run_screening_agent", fake_run), \
             patch("slackbot.providers.OpenAI") as openai_class:
            openai_class.return_value = MagicMock()
            run_agent_for_provider(provider="openai", **RUN_KWARGS)

        assert openai_class.call_args.kwargs["api_key"] == "sk-user"
        assert captured["client"] is openai_class.return_value

    def test_anthropic_dispatches_to_anthropic_agent(self):
        events = [AnswerToken("hi"), Completed(1, 1)]
        with patch(
            "slackbot.providers.run_anthropic_screening_agent",
            events_generator(events),
        ):
            answer = run_agent_for_provider(provider="anthropic", **RUN_KWARGS)
        assert answer.text == "hi"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            run_agent_for_provider(provider="grok", **RUN_KWARGS)
