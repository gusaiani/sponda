"""The Celery answer task (slackbot/tasks.py) and Slack formatting.

The task is where BYOK actually happens: it loads the asker's own
encrypted key, runs the screening agent on their dime, and edits the
placeholder message into the final answer. Slack clients and the agent
are always mocked — the tests assert the orchestration, not the network.
"""
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from slackbot.crypto import encrypt_api_key
from slackbot.markdown import to_mrkdwn
from slackbot.models import SlackLLMKey, SlackQuery
from slackbot.providers import AgentAnswer
from slackbot.tasks import answer_slack_question

TEST_FERNET_KEY = Fernet.generate_key().decode()

TASK_KWARGS = {
    "team_id": "T789",
    "slack_user_id": "U123",
    "channel_id": "C456",
    "thread_ts": "1700000000.000100",
    "text": "<@U0BOT> cheapest BR banks?",
}


def make_key(provider="openai", api_key="sk-user-key"):
    return SlackLLMKey.objects.create(
        slack_team_id="T789",
        slack_user_id="U123",
        provider=provider,
        encrypted_api_key=encrypt_api_key(api_key),
    )


@pytest.mark.django_db
@patch("slackbot.tasks.fetch_user_locale", return_value="pt-BR")
@patch("slackbot.tasks.update_message")
@patch("slackbot.tasks.post_message", return_value={"ok": True, "ts": "1700000001.000200"})
class TestAnswerSlackQuestion:
    @pytest.fixture(autouse=True)
    def _encryption_key(self, settings):
        settings.SLACKBOT_KEY_ENCRYPTION_KEY = TEST_FERNET_KEY
    @patch("slackbot.tasks.run_agent_for_provider")
    def test_happy_path_posts_placeholder_then_edits_in_answer(
        self, run_agent, post_message, update_message, fetch_locale
    ):
        make_key()
        run_agent.return_value = AgentAnswer(
            text="PETR4 looks cheap.", input_tokens=100, output_tokens=20,
            error_code=None,
        )

        answer_slack_question(**TASK_KWARGS)

        placeholder_kwargs = post_message.call_args.kwargs
        assert placeholder_kwargs["channel"] == "C456"
        assert placeholder_kwargs["thread_ts"] == "1700000000.000100"
        update_kwargs = update_message.call_args.kwargs
        assert update_kwargs["ts"] == "1700000001.000200"
        assert "PETR4 looks cheap." in update_kwargs["text"]

    @patch("slackbot.tasks.run_agent_for_provider")
    def test_agent_receives_users_own_key_and_locale(
        self, run_agent, post_message, update_message, fetch_locale
    ):
        make_key(provider="anthropic", api_key="sk-ant-user")
        run_agent.return_value = AgentAnswer("ok", 1, 1, None)

        answer_slack_question(**TASK_KWARGS)

        kwargs = run_agent.call_args.kwargs
        assert kwargs["provider"] == "anthropic"
        assert kwargs["api_key"] == "sk-ant-user"
        assert kwargs["locale"] == "pt"
        # The bot mention is noise the model should never see.
        assert "<@" not in kwargs["question"]
        assert "cheapest BR banks?" in kwargs["question"]

    @patch("slackbot.tasks.run_agent_for_provider")
    def test_logs_query_row_with_token_totals(
        self, run_agent, post_message, update_message, fetch_locale
    ):
        make_key()
        run_agent.return_value = AgentAnswer("answer", 111, 22, None)

        answer_slack_question(**TASK_KWARGS)

        row = SlackQuery.objects.get()
        assert row.slack_team_id == "T789"
        assert row.channel_id == "C456"
        assert row.thread_ts == "1700000000.000100"
        assert row.status == "ok"
        assert row.input_tokens == 111
        assert row.output_tokens == 22
        assert row.answer == "answer"

    @patch("slackbot.tasks.run_agent_for_provider")
    def test_thread_history_reaches_the_agent(
        self, run_agent, post_message, update_message, fetch_locale
    ):
        make_key()
        SlackQuery.objects.create(
            slack_team_id="T789", slack_user_id="U123", channel_id="C456",
            thread_ts="1700000000.000100", provider="openai",
            question="what is PE10?", answer="An inflation-adjusted P/E.",
            status="ok",
        )
        run_agent.return_value = AgentAnswer("follow-up answer", 1, 1, None)

        answer_slack_question(**TASK_KWARGS)

        history = run_agent.call_args.kwargs["history_messages"]
        assert any("what is PE10?" in message["content"] for message in history)
        assert any(
            "inflation-adjusted" in message["content"] for message in history
        )

    @patch("slackbot.tasks.run_agent_for_provider")
    def test_failed_rows_stay_out_of_history(
        self, run_agent, post_message, update_message, fetch_locale
    ):
        make_key()
        SlackQuery.objects.create(
            slack_team_id="T789", slack_user_id="U123", channel_id="C456",
            thread_ts="1700000000.000100", provider="openai",
            question="broken turn", answer="", status="upstream_timeout",
        )
        run_agent.return_value = AgentAnswer("answer", 1, 1, None)

        answer_slack_question(**TASK_KWARGS)

        history = run_agent.call_args.kwargs["history_messages"]
        assert history == []

    def test_no_registered_key_prompts_for_sponda_key(
        self, post_message, update_message, fetch_locale
    ):
        answer_slack_question(**TASK_KWARGS)

        text = post_message.call_args.kwargs["text"]
        assert "/sponda-key" in text
        update_message.assert_not_called()
        assert not SlackQuery.objects.exists()

    @patch("slackbot.tasks.run_agent_for_provider")
    def test_invalid_key_error_tells_user_to_reregister(
        self, run_agent, post_message, update_message, fetch_locale
    ):
        make_key()
        run_agent.return_value = AgentAnswer("", 0, 0, "invalid_api_key")

        answer_slack_question(**TASK_KWARGS)

        text = update_message.call_args.kwargs["text"]
        assert "/sponda-key" in text
        assert SlackQuery.objects.get().status == "invalid_api_key"

    @patch("slackbot.tasks.run_agent_for_provider")
    def test_upstream_timeout_reported_gracefully(
        self, run_agent, post_message, update_message, fetch_locale
    ):
        make_key()
        run_agent.return_value = AgentAnswer("", 0, 0, "upstream_timeout")

        answer_slack_question(**TASK_KWARGS)

        assert update_message.called
        assert SlackQuery.objects.get().status == "upstream_timeout"


class TestToMrkdwn:
    def test_bold_converts_to_slack_bold(self):
        assert to_mrkdwn("**PETR4** is cheap") == "*PETR4* is cheap"

    def test_links_convert_to_slack_links(self):
        assert (
            to_mrkdwn("See [PETR4](https://sponda.capital/PETR4).")
            == "See <https://sponda.capital/PETR4|PETR4>."
        )

    def test_headings_become_bold_lines(self):
        assert to_mrkdwn("### Results\ntext") == "*Results*\ntext"

    def test_plain_text_untouched(self):
        assert to_mrkdwn("a * b = c") == "a * b = c"
