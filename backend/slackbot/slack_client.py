"""Thin Slack Web API client (bot-token calls).

Deliberately not the slack-sdk package: the bot needs four methods, all
plain JSON POST/GET against slack.com, and `requests` is already a
dependency. Every function raises SlackApiError on a non-ok payload so
callers decide whether a failure is fatal (opening a modal) or ignorable
(fetching a locale).
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SLACK_API_BASE_URL = "https://slack.com/api"

# One Slack call must never pin a Celery worker: Slack answers in well
# under a second when healthy, so ten seconds is already generous.
REQUEST_TIMEOUT_SECONDS = 10


class SlackApiError(Exception):
    """Slack answered, but with ok=false (or not at all)."""


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    }


def _call(method: str, payload: dict) -> dict:
    try:
        response = requests.post(
            f"{SLACK_API_BASE_URL}/{method}",
            json=payload,
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise SlackApiError(f"{method} failed: {exc}") from exc
    if not body.get("ok"):
        raise SlackApiError(f"{method} failed: {body.get('error', 'unknown')}")
    return body


def post_message(*, channel: str, text: str, thread_ts: str | None = None) -> dict:
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    return _call("chat.postMessage", payload)


def update_message(*, channel: str, ts: str, text: str) -> dict:
    return _call("chat.update", {"channel": channel, "ts": ts, "text": text})


def open_view(trigger_id: str, view: dict) -> dict:
    return _call("views.open", {"trigger_id": trigger_id, "view": view})


def fetch_user_locale(slack_user_id: str) -> str:
    """The user's Slack locale ("pt-BR", "en-US", …), or "" when
    unavailable — locale is a nicety, never worth failing an answer over."""
    try:
        body = _call("users.info", {"user": slack_user_id, "include_locale": True})
    except SlackApiError as exc:
        logger.warning("users.info failed for %s: %s", slack_user_id, exc)
        return ""
    return body.get("user", {}).get("locale", "")
