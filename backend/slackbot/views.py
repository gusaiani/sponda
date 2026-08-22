"""Slack HTTP endpoints: events, the /sponda-key command, interactions.

All three are signature-gated (slackbot.signing) and CSRF-exempt — Slack
is not a browser. The events endpoint must ack inside Slack's 3-second
window, so the only inline work is signature checking, event dedup, and
a Celery enqueue; everything expensive lives in slackbot.tasks.
"""
import json
import logging

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from slackbot.crypto import encrypt_api_key
from slackbot.key_validation import validate_api_key
from slackbot.models import PROVIDER_CHOICES, SlackLLMKey
from slackbot.signing import is_valid_slack_signature
from slackbot.slack_client import SlackApiError, open_view
from slackbot.tasks import answer_slack_question

logger = logging.getLogger(__name__)

# Slack retries an event for up to an hour when it believes delivery
# failed; remembering seen event ids that long makes redelivery a no-op.
EVENT_DEDUP_SECONDS = 3600

KEY_MODAL_CALLBACK_ID = "sponda_key_submit"

INVALID_KEY_MODAL_ERROR = (
    "The provider rejected this key. Check it and try again."
)


def _signature_gate(request) -> HttpResponse | None:
    """503 when the endpoint is unconfigured, 403 on a bad signature,
    None when the request is genuinely from Slack."""
    from django.conf import settings

    if not settings.SLACK_SIGNING_SECRET:
        return HttpResponse(status=503)
    if not is_valid_slack_signature(
        body=request.body,
        timestamp=request.headers.get("X-Slack-Request-Timestamp", ""),
        signature=request.headers.get("X-Slack-Signature", ""),
    ):
        return HttpResponse(status=403)
    return None


def _should_answer(event: dict) -> bool:
    """Mentions anywhere; plain messages only in DMs — and never the
    bot's own posts or message edits, which would loop forever."""
    if event.get("bot_id"):
        return False
    if event.get("type") == "app_mention":
        return True
    return (
        event.get("type") == "message"
        and event.get("channel_type") == "im"
        and not event.get("subtype")
    )


def _enqueue_answer(team_id: str, event: dict) -> None:
    answer_slack_question.delay(
        team_id=team_id,
        slack_user_id=event.get("user", ""),
        channel_id=event.get("channel", ""),
        # Answer inside the thread the question lives in; a top-level
        # question starts its own thread at the question's ts.
        thread_ts=event.get("thread_ts") or event.get("ts", ""),
        text=event.get("text", ""),
    )


@csrf_exempt
@require_POST
def slack_events(request):
    gate_response = _signature_gate(request)
    if gate_response is not None:
        return gate_response

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    if payload.get("type") == "url_verification":
        return JsonResponse({"challenge": payload.get("challenge", "")})

    if payload.get("type") == "event_callback":
        event_id = payload.get("event_id", "")
        # cache.add is atomic: exactly one delivery of a retried event
        # wins, so the user never gets (or pays for) a second answer.
        is_first_delivery = cache.add(
            f"slackbot:event:{event_id}", True, EVENT_DEDUP_SECONDS
        )
        event = payload.get("event", {})
        if is_first_delivery and _should_answer(event):
            _enqueue_answer(payload.get("team_id", ""), event)

    return JsonResponse({"ok": True})


def _build_key_modal() -> dict:
    provider_options = [
        {
            "text": {"type": "plain_text", "text": label},
            "value": value,
        }
        for value, label in PROVIDER_CHOICES
    ]
    return {
        "type": "modal",
        "callback_id": KEY_MODAL_CALLBACK_ID,
        "title": {"type": "plain_text", "text": "Sponda · LLM key"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "provider_block",
                "label": {"type": "plain_text", "text": "Provider"},
                "element": {
                    "type": "static_select",
                    "action_id": "provider_select",
                    "options": provider_options,
                    "initial_option": provider_options[0],
                },
            },
            {
                "type": "input",
                "block_id": "api_key_block",
                "label": {"type": "plain_text", "text": "API key"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "api_key_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "sk-… (stored encrypted; delete anytime with /sponda-key delete)",
                    },
                },
            },
            {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": ("Questions you ask the Sponda bot run on this key — "
                             "your account, your cost. The key is encrypted at "
                             "rest and never logged."),
                }],
            },
        ],
    }


def _ephemeral(text: str) -> JsonResponse:
    return JsonResponse({"response_type": "ephemeral", "text": text})


@csrf_exempt
@require_POST
def slack_commands(request):
    gate_response = _signature_gate(request)
    if gate_response is not None:
        return gate_response

    team_id = request.POST.get("team_id", "")
    slack_user_id = request.POST.get("user_id", "")
    subcommand = request.POST.get("text", "").strip().lower()

    if subcommand in ("delete", "remove"):
        deleted_count, _ = SlackLLMKey.objects.filter(
            slack_team_id=team_id, slack_user_id=slack_user_id
        ).delete()
        if deleted_count:
            return _ephemeral("Your API key was deleted.")
        return _ephemeral("No API key was stored for you.")

    if subcommand == "status":
        stored_key = SlackLLMKey.objects.filter(
            slack_team_id=team_id, slack_user_id=slack_user_id
        ).first()
        if stored_key is None:
            return _ephemeral("No API key registered. Run `/sponda-key` to add one.")
        return _ephemeral(
            f"You have a {stored_key.get_provider_display()} key registered "
            f"(provider: {stored_key.provider})."
        )

    try:
        open_view(request.POST.get("trigger_id", ""), _build_key_modal())
    except SlackApiError:
        logger.exception("views.open failed for /sponda-key")
        return _ephemeral("Could not open the key form. Please try again.")
    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def slack_interactions(request):
    gate_response = _signature_gate(request)
    if gate_response is not None:
        return gate_response

    try:
        payload = json.loads(request.POST.get("payload", ""))
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    is_key_submission = (
        payload.get("type") == "view_submission"
        and payload.get("view", {}).get("callback_id") == KEY_MODAL_CALLBACK_ID
    )
    if not is_key_submission:
        return HttpResponse(status=200)

    values = payload["view"]["state"]["values"]
    provider = (
        values["provider_block"]["provider_select"]
        .get("selected_option", {})
        .get("value", "")
    )
    api_key = (values["api_key_block"]["api_key_input"].get("value") or "").strip()

    if provider not in dict(PROVIDER_CHOICES) or not api_key:
        return JsonResponse({
            "response_action": "errors",
            "errors": {"api_key_block": "Provider and key are both required."},
        })

    # False means the provider explicitly rejected the key; None
    # (indeterminate — provider blip) stores it anyway rather than locking
    # the user out, and a genuinely bad key surfaces on first use.
    if validate_api_key(provider, api_key) is False:
        return JsonResponse({
            "response_action": "errors",
            "errors": {"api_key_block": INVALID_KEY_MODAL_ERROR},
        })

    SlackLLMKey.objects.update_or_create(
        slack_team_id=payload.get("team", {}).get("id", ""),
        slack_user_id=payload.get("user", {}).get("id", ""),
        defaults={
            "provider": provider,
            "encrypted_api_key": encrypt_api_key(api_key),
        },
    )
    return HttpResponse(status=200)
