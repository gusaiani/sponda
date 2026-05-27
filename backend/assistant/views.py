"""HTTP views for the LLM Q&A assistant.

`ask` is the single endpoint: POST a question, get back an SSE stream.
Auth gate runs first so unauthorized callers never reach OpenAI.
"""
import json
import time

from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseForbidden, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from openai import APIError, APITimeoutError, RateLimitError

from assistant.context import build_company_context
from assistant.cost import calculate_cost
from assistant.guardrail import classify_question
from assistant.models import LLMQuery
from assistant.openai_client import get_openai_client
from assistant.prompts import ANSWER_SYSTEM_PROMPT, OFF_TOPIC_RESPONSE


def _sse_frame(event: str, data: dict | str) -> bytes:
    """Format one Server-Sent Events frame.

    SSE wire spec: each frame is `event: <name>` + `data: <payload>` +
    a blank line. We always serialize `data` as JSON (even for plain
    strings) so the client has one parse path, not two.
    """
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n".encode()

def _event_stream(*, ticker, tab, locale, question, user):
    """Yield the SSE frames for one assistant response.

    Pulled into its own generator so the view body stays linear and
    Django's StreamingHttpResponse can iterate it lazily - bytes are
    flushed to the client as each `yield` fires, not after the whole
    answer is built.
    """
    started_at = time.monotonic()
    status = "ok"
    classification = ""
    usage = None

    try:
        company_context = build_company_context(ticker, tab, locale, user)
        verdict = classify_question(
            question=question,
            company_context=company_context,
        )

        classification = verdict.classification

        # Meta frame ships first so the client can render the header
        # (which model, which classification) before tokens start arriving.
        yield _sse_frame("meta", {
            "model": settings.ASSISTANT_ANSWER_MODEL,
            "ticker": ticker,
            "classification": verdict.classification,
        })

        if classification != "on_topic":
            status = "off_topic"
            redirect_text = OFF_TOPIC_RESPONSE.get(locale, OFF_TOPIC_RESPONSE["en"])
            yield _sse_frame("off_topic", redirect_text)
            yield _sse_frame("done", {"input_tokens": 0, "output_tokens": 0})
            return

        user_message = (
            f"locale: {locale}\n"
            f"\n"
            f"{company_context}\n"
            f"\n"
            f"Question: {question}"
        )

        client = get_openai_client()
        stream = client.chat.completions.create(
            model=settings.ASSISTANT_ANSWER_MODEL,
            messages=[
                {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            stream=True,
            # include_usage=True makes OpenAI emit a final no-content chunk
            # whose .usage holds prompt_tokens / completion_tokens. We need
            # those for cost logging in the next baby step.
            stream_options={"include_usage": True},
        )

        try:
            for chunk in stream:
                if chunk.usage is not None:
                    # The include_usage chunk arrives last and has no choices;
                    # stash it and let the loop fall through to the next chunk
                    # (there won't be one, but guarding `choices` keeps both
                    # branches independent).
                    usage = chunk.usage
                if not chunk.choices:
                    continue
                token_text = chunk.choices[0].delta.content
                if token_text:
                    yield _sse_frame("token", token_text)
        except APITimeoutError:
            status = "error"
            yield _sse_frame("error", {"code": "upstream_timeout"})
            return
        except RateLimitError:
            status = "error"
            yield _sse_frame("error", {"code": "rate_limited"})
            return
        except APIError:
            status = "error"
            yield _sse_frame("error", {"code": "internal"})
            return

        done_payload = {
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
        }
        yield _sse_frame("done", done_payload)
    finally:
        latency_ms = int((time.monotonic() - started_at) * 1000)
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        cost_usd = calculate_cost(
            model=settings.ASSISTANT_ANSWER_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        LLMQuery.objects.create(
            user=user,
            ticker=ticker,
            tab=tab,
            locale=locale,
            question=question,
            classification=classification,
            model=settings.ASSISTANT_ANSWER_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
        )

@csrf_exempt
# CSRF off because the client posts JSON with an explicit fetch + auth
# cookie; same pattern as the other JSON POST endpoints in this project.
@require_POST
def ask(request):
    """Stream an answer to a question about the company in context."""
    # v1: superuser-only. is_authenticated alone is not enough - the gate
    # is is_superuser, enforced server-side so a UI bypass cannot grant
    # access. Later tiers (paying, trial) plug in via assistant_quota.
    if not request.user.is_authenticated or not request.user.is_superuser:
        return HttpResponseForbidden()

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid JSON body")

    ticker = (payload.get("ticker") or "").strip().upper()
    tab = (payload.get("tab") or "").strip()
    locale = (payload.get("locale") or "en").strip()
    question = (payload.get("question") or "").strip()

    if not question:
        return HttpResponseBadRequest("question is required")
    if len(question) > settings.ASSISTANT_MAX_QUESTION_CHARS:
        return HttpResponseBadRequest("question exceeds max length")

    response = StreamingHttpResponse(
        _event_stream(
            ticker=ticker,
            tab=tab,
            locale=locale,
            question=question,
            user=request.user,
        ),
        content_type="text/event-stream"
    )

    # nginx bypass - without this header the upstream buffers the
    # whole response and the client sees one big lump at the end.
    response["X-Accel-Buffering"] = "no"
    return response