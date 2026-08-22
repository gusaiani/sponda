"""Slack HTTP endpoints (slackbot/views.py).

Three endpoints, all signature-gated: /api/slack/events/ (Events API),
/api/slack/commands/ (the /sponda-key slash command), and
/api/slack/interactions/ (modal submissions). The events endpoint must
ack within Slack's 3-second window, so the only work it does inline is
signature checking, dedup, and a Celery enqueue.
"""
import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from cryptography.fernet import Fernet
from django.test import Client, override_settings

from slackbot.crypto import decrypt_api_key
from slackbot.models import SlackLLMKey

SIGNING_SECRET = "test-signing-secret"
TEST_FERNET_KEY = Fernet.generate_key().decode()

EVENTS_URL = "/api/slack/events/"
COMMANDS_URL = "/api/slack/commands/"
INTERACTIONS_URL = "/api/slack/interactions/"


def slack_headers(body: bytes, secret: str = SIGNING_SECRET) -> dict:
    timestamp = str(int(time.time()))
    digest = hmac.new(
        secret.encode(), f"v0:{timestamp}:{body.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "HTTP_X_SLACK_REQUEST_TIMESTAMP": timestamp,
        "HTTP_X_SLACK_SIGNATURE": f"v0={digest}",
    }


def post_event(payload: dict, secret: str = SIGNING_SECRET):
    body = json.dumps(payload).encode()
    return Client().post(
        EVENTS_URL, data=body, content_type="application/json",
        **slack_headers(body, secret),
    )


def post_form(url: str, fields: dict, secret: str = SIGNING_SECRET):
    body = urlencode(fields).encode()
    return Client().post(
        url, data=body, content_type="application/x-www-form-urlencoded",
        **slack_headers(body, secret),
    )


def mention_event(*, event_id=None, text="<@U0BOT> cheapest BR banks?", **overrides):
    event = {
        "type": "app_mention",
        "user": "U123",
        "channel": "C456",
        "ts": "1700000000.000100",
        "text": text,
        **overrides,
    }
    return {
        "type": "event_callback",
        "event_id": event_id or f"Ev{uuid.uuid4().hex[:12]}",
        "team_id": "T789",
        "event": event,
    }


class TestEventsEndpoint:
    @pytest.fixture(autouse=True)
    def _signing_secret(self, settings):
        settings.SLACK_SIGNING_SECRET = SIGNING_SECRET

    def test_url_verification_echoes_challenge(self):
        response = post_event({"type": "url_verification", "challenge": "abc123"})
        assert response.status_code == 200
        assert response.json()["challenge"] == "abc123"

    def test_bad_signature_rejected(self):
        response = post_event(
            {"type": "url_verification", "challenge": "abc"}, secret="wrong-secret"
        )
        assert response.status_code == 403

    def test_unsigned_request_rejected(self):
        body = json.dumps({"type": "url_verification", "challenge": "abc"})
        response = Client().post(EVENTS_URL, data=body, content_type="application/json")
        assert response.status_code == 403

    @override_settings(SLACK_SIGNING_SECRET="")
    def test_unconfigured_endpoint_returns_503(self):
        response = post_event({"type": "url_verification", "challenge": "abc"}, secret="")
        assert response.status_code == 503

    @patch("slackbot.views.answer_slack_question")
    def test_app_mention_enqueues_answer_task(self, task):
        response = post_event(mention_event())
        assert response.status_code == 200
        task.delay.assert_called_once_with(
            team_id="T789",
            slack_user_id="U123",
            channel_id="C456",
            thread_ts="1700000000.000100",
            text="<@U0BOT> cheapest BR banks?",
        )

    @patch("slackbot.views.answer_slack_question")
    def test_threaded_mention_answers_in_its_thread(self, task):
        response = post_event(mention_event(thread_ts="1699999999.000001"))
        assert response.status_code == 200
        assert task.delay.call_args.kwargs["thread_ts"] == "1699999999.000001"

    @patch("slackbot.views.answer_slack_question")
    def test_slack_retry_of_same_event_enqueues_once(self, task):
        # Slack redelivers events it thinks failed; the event_id dedup
        # must keep the user from getting (and paying for) two answers.
        payload = mention_event(event_id=f"Ev{uuid.uuid4().hex[:12]}")
        assert post_event(payload).status_code == 200
        assert post_event(payload).status_code == 200
        assert task.delay.call_count == 1

    @patch("slackbot.views.answer_slack_question")
    def test_direct_message_enqueues_answer_task(self, task):
        payload = mention_event()
        payload["event"].update(type="message", channel_type="im", text="hi")
        assert post_event(payload).status_code == 200
        assert task.delay.call_count == 1

    @patch("slackbot.views.answer_slack_question")
    def test_bot_message_ignored(self, task):
        # The bot's own posts come back as message events; answering
        # them would loop forever.
        payload = mention_event()
        payload["event"].update(type="message", channel_type="im", bot_id="B999")
        assert post_event(payload).status_code == 200
        task.delay.assert_not_called()

    @patch("slackbot.views.answer_slack_question")
    def test_channel_chatter_without_mention_ignored(self, task):
        payload = mention_event()
        payload["event"].update(type="message", channel_type="channel")
        assert post_event(payload).status_code == 200
        task.delay.assert_not_called()

    @patch("slackbot.views.answer_slack_question")
    def test_message_edit_subtype_ignored(self, task):
        payload = mention_event()
        payload["event"].update(
            type="message", channel_type="im", subtype="message_changed"
        )
        assert post_event(payload).status_code == 200
        task.delay.assert_not_called()


def command_fields(text=""):
    return {
        "command": "/sponda-key",
        "text": text,
        "trigger_id": "trigger-1",
        "user_id": "U123",
        "team_id": "T789",
    }


class TestSpondaKeyCommand:
    @pytest.fixture(autouse=True)
    def _signing_secret(self, settings):
        settings.SLACK_SIGNING_SECRET = SIGNING_SECRET

    @patch("slackbot.views.open_view")
    def test_bare_command_opens_key_modal(self, open_view):
        response = post_form(COMMANDS_URL, command_fields())
        assert response.status_code == 200
        open_view.assert_called_once()
        trigger_id, view = open_view.call_args.args
        assert trigger_id == "trigger-1"
        assert view["callback_id"] == "sponda_key_submit"

    def test_bad_signature_rejected(self):
        response = post_form(COMMANDS_URL, command_fields(), secret="wrong")
        assert response.status_code == 403

    @pytest.mark.django_db
    @override_settings(SLACKBOT_KEY_ENCRYPTION_KEY=TEST_FERNET_KEY)
    def test_delete_removes_stored_key(self):
        SlackLLMKey.objects.create(
            slack_team_id="T789", slack_user_id="U123",
            provider="openai", encrypted_api_key="x",
        )
        response = post_form(COMMANDS_URL, command_fields("delete"))
        assert response.status_code == 200
        assert response.json()["response_type"] == "ephemeral"
        assert not SlackLLMKey.objects.filter(
            slack_team_id="T789", slack_user_id="U123"
        ).exists()

    @pytest.mark.django_db
    def test_status_reports_configured_provider(self):
        SlackLLMKey.objects.create(
            slack_team_id="T789", slack_user_id="U123",
            provider="anthropic", encrypted_api_key="x",
        )
        response = post_form(COMMANDS_URL, command_fields("status"))
        assert response.status_code == 200
        assert "anthropic" in response.json()["text"].lower()

    @pytest.mark.django_db
    def test_status_without_key_says_none(self):
        response = post_form(COMMANDS_URL, command_fields("status"))
        assert response.status_code == 200
        assert "no " in response.json()["text"].lower()


def submission_payload(provider="openai", api_key="sk-test-123"):
    return {
        "type": "view_submission",
        "team": {"id": "T789"},
        "user": {"id": "U123"},
        "view": {
            "callback_id": "sponda_key_submit",
            "state": {
                "values": {
                    "provider_block": {
                        "provider_select": {
                            "selected_option": {"value": provider}
                        }
                    },
                    "api_key_block": {
                        "api_key_input": {"value": api_key}
                    },
                }
            },
        },
    }


class TestKeySubmission:
    @pytest.fixture(autouse=True)
    def _slack_settings(self, settings):
        settings.SLACK_SIGNING_SECRET = SIGNING_SECRET
        settings.SLACKBOT_KEY_ENCRYPTION_KEY = TEST_FERNET_KEY

    @pytest.mark.django_db
    @patch("slackbot.views.validate_api_key", return_value=True)
    def test_valid_key_stored_encrypted(self, validate):
        payload = submission_payload(provider="anthropic", api_key="sk-ant-secret")
        response = post_form(INTERACTIONS_URL, {"payload": json.dumps(payload)})
        assert response.status_code == 200
        row = SlackLLMKey.objects.get(slack_team_id="T789", slack_user_id="U123")
        assert row.provider == "anthropic"
        assert row.encrypted_api_key != "sk-ant-secret"
        assert decrypt_api_key(row.encrypted_api_key) == "sk-ant-secret"

    @pytest.mark.django_db
    @patch("slackbot.views.validate_api_key", return_value=False)
    def test_rejected_key_surfaces_modal_error(self, validate):
        response = post_form(
            INTERACTIONS_URL, {"payload": json.dumps(submission_payload())}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["response_action"] == "errors"
        assert "api_key_block" in body["errors"]
        assert not SlackLLMKey.objects.exists()

    @pytest.mark.django_db
    @patch("slackbot.views.validate_api_key", return_value=None)
    def test_unreachable_validation_stores_key_anyway(self, validate):
        # A provider outage must not lock users out of registering;
        # a wrong key will surface on first use with a clear message.
        response = post_form(
            INTERACTIONS_URL, {"payload": json.dumps(submission_payload())}
        )
        assert response.status_code == 200
        assert SlackLLMKey.objects.count() == 1

    @pytest.mark.django_db
    @patch("slackbot.views.validate_api_key", return_value=True)
    def test_resubmission_updates_existing_row(self, validate):
        for api_key in ("sk-old", "sk-new"):
            post_form(
                INTERACTIONS_URL,
                {"payload": json.dumps(submission_payload(api_key=api_key))},
            )
        row = SlackLLMKey.objects.get()
        assert decrypt_api_key(row.encrypted_api_key) == "sk-new"

    def test_bad_signature_rejected(self):
        response = post_form(
            INTERACTIONS_URL,
            {"payload": json.dumps(submission_payload())},
            secret="wrong",
        )
        assert response.status_code == 403
