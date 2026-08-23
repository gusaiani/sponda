"""The answer task: where BYOK actually happens.

The events view acks Slack inside its 3-second window and hands the real
work here. This task decrypts the asker's own provider key, rebuilds the
thread's conversation memory from prior SlackQuery rows, runs the
screening agent on the user's dime, and edits the placeholder message
into the final answer. Every outcome — answer or error — lands as a
SlackQuery audit row.
"""
import logging
import re
import time

from celery import shared_task
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.cache import cache

from assistant.history import build_history_messages
from slackbot.crypto import decrypt_api_key
from slackbot.links import linkify_tickers, resolve_known_symbols
from slackbot.markdown import to_mrkdwn
from slackbot.models import SlackLLMKey, SlackQuery
from slackbot.providers import run_agent_for_provider
from slackbot.slack_client import (
    SlackApiError,
    fetch_user_locale,
    post_message,
    update_message,
)

logger = logging.getLogger(__name__)

# Bot mentions ("<@U0BOT>") are Slack plumbing the model should never see.
MENTION_PATTERN = re.compile(r"<@[A-Z0-9]+>\s*")

PLACEHOLDER_TEXT = "🔍 Looking into it…"

NO_KEY_MESSAGE = (
    "I don't have an LLM API key for you yet. Run `/sponda-key` to register "
    "your own OpenAI or Anthropic key — questions run on your key, your cost."
)

CORRUPTED_KEY_MESSAGE = (
    "Your stored API key could no longer be decrypted (it may predate a "
    "server key rotation). Please register it again with `/sponda-key`."
)

ERROR_MESSAGES = {
    "invalid_api_key": (
        "Your API key was rejected by the provider. Re-register a valid key "
        "with `/sponda-key`."
    ),
    "rate_limited": (
        "Your provider account is rate-limited right now. Try again in a "
        "minute."
    ),
    "upstream_timeout": "The model provider timed out. Please try again.",
    "refusal": "The model declined to answer this question.",
    "internal": "Something went wrong while answering. Please try again.",
}

# Slack rejects chat.update payloads near 40k characters; stay comfortably
# under while keeping room for long screening tables.
ANSWER_CHAR_LIMIT = 12000

USER_LOCALE_CACHE_SECONDS = 86400
DEFAULT_LOCALE = "en"


def _user_locale(slack_user_id: str) -> str:
    """The user's Slack locale mapped to a Sponda locale code, cached a day
    so one question costs at most one users.info call."""
    cache_key = f"slackbot:locale:{slack_user_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    slack_locale = fetch_user_locale(slack_user_id)
    locale = slack_locale.split("-")[0].lower() if slack_locale else DEFAULT_LOCALE
    cache.set(cache_key, locale, USER_LOCALE_CACHE_SECONDS)
    return locale


def _thread_history(channel_id: str, thread_ts: str) -> list[dict]:
    """Conversation memory from this thread's prior successful turns —
    server-side rows, so nothing client-resent needs trusting."""
    recent_rows = (
        SlackQuery.objects
        .filter(channel_id=channel_id, thread_ts=thread_ts, status="ok")
        .order_by("-created_at")[: settings.ASSISTANT_MAX_HISTORY_TURNS]
    )
    pairs = [
        {"question": row.question, "answer": row.answer}
        for row in reversed(list(recent_rows))
    ]
    return build_history_messages(
        pairs,
        max_turns=settings.ASSISTANT_MAX_HISTORY_TURNS,
        max_question_chars=settings.ASSISTANT_MAX_QUESTION_CHARS,
        max_answer_chars=settings.ASSISTANT_MAX_HISTORY_ANSWER_CHARS,
    )


def _clean_question(text: str) -> str:
    question = MENTION_PATTERN.sub("", text or "").strip()
    return question[: settings.ASSISTANT_MAX_QUESTION_CHARS]


@shared_task
def answer_slack_question(*, team_id: str, slack_user_id: str, channel_id: str,
                          thread_ts: str, text: str):
    stored_key = SlackLLMKey.objects.filter(
        slack_team_id=team_id, slack_user_id=slack_user_id
    ).first()
    if stored_key is None:
        post_message(channel=channel_id, text=NO_KEY_MESSAGE, thread_ts=thread_ts)
        return

    try:
        api_key = decrypt_api_key(stored_key.encrypted_api_key)
    except InvalidToken:
        post_message(channel=channel_id, text=CORRUPTED_KEY_MESSAGE, thread_ts=thread_ts)
        return

    question = _clean_question(text)
    placeholder = post_message(
        channel=channel_id, text=PLACEHOLDER_TEXT, thread_ts=thread_ts
    )
    placeholder_ts = placeholder.get("ts", "")

    locale = _user_locale(slack_user_id)
    started_at = time.monotonic()
    answer = run_agent_for_provider(
        provider=stored_key.provider,
        api_key=api_key,
        question=question,
        history_messages=_thread_history(channel_id, thread_ts),
        locale=locale,
    )
    latency_ms = int((time.monotonic() - started_at) * 1000)

    if answer.error_code:
        final_text = ERROR_MESSAGES.get(answer.error_code, ERROR_MESSAGES["internal"])
    else:
        # Symbols the screener returned, plus any the asker named that the
        # ticker table confirms — a get_company answer surfaces no rows,
        # so the question is the only place its symbol appears.
        linkable_symbols = answer.symbols | resolve_known_symbols(question)
        # Clamp before linking: clamping after could sever a "<url|SYM>"
        # span and leave Slack rendering raw link syntax. Links only ever
        # add characters, and the result stays far under Slack's own cap.
        final_text = linkify_tickers(
            to_mrkdwn(answer.text)[:ANSWER_CHAR_LIMIT],
            symbols=linkable_symbols,
            locale=locale,
        )

    try:
        update_message(channel=channel_id, ts=placeholder_ts, text=final_text)
    except SlackApiError:
        logger.exception("chat.update failed; answer for %s/%s lost to Slack",
                         channel_id, placeholder_ts)

    SlackQuery.objects.create(
        slack_team_id=team_id,
        slack_user_id=slack_user_id,
        channel_id=channel_id,
        thread_ts=thread_ts,
        provider=stored_key.provider,
        question=question,
        answer=answer.text if not answer.error_code else "",
        status=answer.error_code or "ok",
        input_tokens=answer.input_tokens,
        output_tokens=answer.output_tokens,
        latency_ms=latency_ms,
    )
