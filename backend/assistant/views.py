"""HTTP views for the LLM Q&A assistant.

`ask` is the single endpoint: POST a question, get back an SSE stream.
Auth gate runs first so unauthorized callers never reach OpenAI.
"""
import json
import time

from django.conf import settings
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
    StreamingHttpResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from openai import APIError, APITimeoutError, RateLimitError

from assistant.agent import (
    AnswerToken,
    Completed,
    Failed,
    InterpretedFilters,
    ScreenResults,
    ToolCallStarted,
    run_screening_agent,
)
from assistant.context import build_company_context
from assistant.cost import calculate_cost
from assistant.guardrail import classify_question, classify_screening_question
from assistant.history import build_history_messages
from assistant.models import LLMQuery
from assistant.openai_client import get_openai_client
from assistant.prompts import (
    ANSWER_SYSTEM_PROMPT,
    OFF_TOPIC_RESPONSE,
    SCREENING_OFF_TOPIC_RESPONSE,
)
from assistant.tools import execute_list_available_indicators, json_safe
from assistant.assistant_quota import would_exceed_assistant_limit
from quotes.client_ip import client_ip_hash


def _sse_frame(event: str, data: dict | str) -> bytes:
    """Format one Server-Sent Events frame.

    SSE wire spec: each frame is `event: <name>` + `data: <payload>` +
    a blank line. We always serialize `data` as JSON (even for plain
    strings) so the client has one parse path, not two — a raw `data: Para`
    would make the client's JSON.parse throw on the first token. ensure_ascii
    is off so UTF-8 (e.g. accented token text) stays human-readable on the
    wire instead of being escaped to \\uXXXX.
    """
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode()

# The PRAZO slider's valid range, mirrored from the frontend
# (ticker-client.tsx clamps to 1..20). Anything outside is ignored — the
# context falls back to the canonical all-history window.
MIN_WINDOW_YEARS = 1
MAX_WINDOW_YEARS = 20


def _parse_window_years(raw):
    """Coerce the client-sent PRAZO window to a valid int, or None.

    Untrusted input: a non-int or out-of-range value degrades to None (no
    windowed recompute) rather than raising.
    """
    try:
        years = int(raw)
    except (TypeError, ValueError):
        return None
    if MIN_WINDOW_YEARS <= years <= MAX_WINDOW_YEARS:
        return years
    return None


def _event_stream(*, ticker, tab, locale, question, years, history_messages, user):
    """Yield the SSE frames for one assistant response.

    Pulled into its own generator so the view body stays linear and
    Django's StreamingHttpResponse can iterate it lazily - bytes are
    flushed to the client as each `yield` fires, not after the whole
    answer is built.

    `history_messages` is the clamped prior conversation; it threads into
    both the guardrail (so follow-ups classify correctly) and the answer
    call (so the model has memory). The fresh <COMPANY_DATA> block only
    rides the current question — history stays lean text, keeping memory
    cheap and the data always reflecting the page the user is on now.
    """
    started_at = time.monotonic()
    status = "ok"
    classification = ""
    usage = None

    try:
        company_context = build_company_context(ticker, tab, locale, user, years=years)
        verdict = classify_question(
            question=question,
            company_context=company_context,
            history_messages=history_messages,
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
                *history_messages,
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

    if would_exceed_assistant_limit(request.user):
        return HttpResponse(status=429)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid JSON body")

    ticker = (payload.get("ticker") or "").strip().upper()
    tab = (payload.get("tab") or "").strip()
    locale = (payload.get("locale") or "en").strip()
    question = (payload.get("question") or "").strip()
    years = _parse_window_years(payload.get("years"))

    if not question:
        return HttpResponseBadRequest("question is required")
    if len(question) > settings.ASSISTANT_MAX_QUESTION_CHARS:
        return HttpResponseBadRequest("question exceeds max length")

    # Bound the conversation memory server-side — never trust the client to
    # cap its own history. This is the per-session cost ceiling.
    history_messages = build_history_messages(
        payload.get("history"),
        max_turns=settings.ASSISTANT_MAX_HISTORY_TURNS,
        max_question_chars=settings.ASSISTANT_MAX_QUESTION_CHARS,
        max_answer_chars=settings.ASSISTANT_MAX_HISTORY_ANSWER_CHARS,
    )

    # No key configured ⇒ both the guardrail and the answer call would fail
    # the moment they hit OpenAI. That failure would land mid-generator,
    # after StreamingHttpResponse has already committed a 200, leaving the
    # client reading a dead connection with no terminal frame. Fail fast
    # with a real error status the client can render instead.
    if not settings.OPENAI_API_KEY:
        return JsonResponse({"code": "assistant_not_configured"}, status=503)

    response = StreamingHttpResponse(
        _event_stream(
            ticker=ticker,
            tab=tab,
            locale=locale,
            question=question,
            years=years,
            history_messages=history_messages,
            user=request.user,
        ),
        content_type="text/event-stream"
    )

    # nginx bypass - without this header the upstream buffers the
    # whole response and the client sees one big lump at the end.
    response["X-Accel-Buffering"] = "no"
    return response


def _screen_event_stream(*, question, locale, history_messages, user, ip_hash):
    """Yield the SSE frames for one screening request.

    Mirrors _event_stream's shape (guardrail first, then the model work,
    LLMQuery always written in `finally`), but drives assistant.agent's
    tool-calling loop instead of a single chat completion, and maps its
    typed events onto SSE frames one-to-one.
    """
    started_at = time.monotonic()
    status = "ok"
    classification = ""
    interpreted_filters = None
    input_tokens = 0
    output_tokens = 0

    try:
        verdict = classify_screening_question(question, history_messages)
        classification = verdict.classification

        # Meta frame ships first, same rationale as ask(): the client can
        # render its header before any tool call or token arrives.
        yield _sse_frame("meta", {
            "model": settings.ASSISTANT_SCREENING_MODEL,
            "classification": verdict.classification,
        })

        if classification != "on_topic":
            status = "off_topic"
            redirect_text = SCREENING_OFF_TOPIC_RESPONSE.get(
                locale, SCREENING_OFF_TOPIC_RESPONSE["en"]
            )
            yield _sse_frame("off_topic", redirect_text)
            yield _sse_frame("done", {"input_tokens": 0, "output_tokens": 0})
            return

        for event in run_screening_agent(
            question=question,
            history_messages=history_messages,
            locale=locale,
        ):
            if isinstance(event, ToolCallStarted):
                yield _sse_frame("tool", {"name": event.name})
            elif isinstance(event, InterpretedFilters):
                # Keep the LAST filter set seen — a follow-up screen
                # restates the full filter set, so the latest call is the
                # one that reflects what was actually run.
                interpreted_filters = event.arguments
                yield _sse_frame("filters", {"filters": event.arguments})
            elif isinstance(event, ScreenResults):
                yield _sse_frame("results", {
                    "count": event.count,
                    "rows": json_safe(event.rows),
                })
            elif isinstance(event, AnswerToken):
                yield _sse_frame("token", event.text)
            elif isinstance(event, Completed):
                input_tokens = event.input_tokens
                output_tokens = event.output_tokens
                yield _sse_frame("done", {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                })
            elif isinstance(event, Failed):
                # No `done` after an error - matches ask()'s contract so
                # the client's single "did we get a terminal frame" check
                # works the same way for both endpoints.
                status = "error"
                yield _sse_frame("error", {"code": event.code})
    finally:
        latency_ms = int((time.monotonic() - started_at) * 1000)

        cost_usd = calculate_cost(
            model=settings.ASSISTANT_SCREENING_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        LLMQuery.objects.create(
            feature=LLMQuery.FEATURE_SCREEN,
            user=user,
            ip_hash=ip_hash,
            ticker="",
            locale=locale,
            question=question,
            classification=classification,
            model=settings.ASSISTANT_SCREENING_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
            interpreted_filters=interpreted_filters,
        )


@csrf_exempt
# Same CSRF rationale as ask(): JSON POST + fetch, no browser form.
@require_POST
def screen(request):
    """Stream a natural-language screening answer about the whole universe.

    Unlike ask() (superuser-only in v1), screening is the trial-tier entry
    point: anonymous callers are allowed, scoped by ip_hash, up to
    ASSISTANT_FREE_TRIAL_PER_DAY per day. would_exceed_assistant_limit is
    still the single seam enforcing that cap server-side.
    """
    if not settings.ASSISTANT_SCREENING_ENABLED:
        return JsonResponse({"code": "screening_disabled"}, status=404)

    ip_hash = client_ip_hash(request)
    user = request.user if request.user.is_authenticated else None

    if would_exceed_assistant_limit(user, ip_hash=ip_hash):
        return HttpResponse(status=429)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid JSON body")

    locale = (payload.get("locale") or "en").strip()
    question = (payload.get("question") or "").strip()

    if not question:
        return HttpResponseBadRequest("question is required")
    if len(question) > settings.ASSISTANT_MAX_QUESTION_CHARS:
        return HttpResponseBadRequest("question exceeds max length")

    # Same server-side memory ceiling as ask() - never trust the client to
    # cap its own history.
    history_messages = build_history_messages(
        payload.get("history"),
        max_turns=settings.ASSISTANT_MAX_HISTORY_TURNS,
        max_question_chars=settings.ASSISTANT_MAX_QUESTION_CHARS,
        max_answer_chars=settings.ASSISTANT_MAX_HISTORY_ANSWER_CHARS,
    )

    # Same fail-fast rationale as ask(): without a key both the guardrail
    # and the agent loop would fail mid-generator, after the 200 already
    # committed. Fail before streaming starts instead.
    if not settings.OPENAI_API_KEY:
        return JsonResponse({"code": "assistant_not_configured"}, status=503)

    response = StreamingHttpResponse(
        _screen_event_stream(
            question=question,
            locale=locale,
            history_messages=history_messages,
            user=user,
            ip_hash=ip_hash,
        ),
        content_type="text/event-stream"
    )

    response["X-Accel-Buffering"] = "no"
    return response

# The catalogue is a static tuple plus two DISTINCT queries over Ticker. An
# hour is plenty: a new sector or country appears when the universe grows,
# which is a weekly event at most.
INDICATOR_CATALOGUE_CACHE_CONTROL = "public, max-age=3600"


@require_GET
def indicators(request):
    """GET /api/assistant/indicators/ · the indicator glossary, as JSON.

    Same payload the ``list_available_indicators`` MCP tool returns:
    every screenable indicator with its definition, whether higher or
    lower is better, the countries and sectors actually present in the
    data, and an explicit list of metrics Sponda does *not* track.

    It lives here rather than under ``/api/screener/`` because
    ``assistant.tools`` owns ``INDICATOR_CATALOGUE`` and already imports
    from ``quotes``; pointing the dependency the other way would be a
    cycle. The markdown screener page renders straight from this, so the
    glossary has one definition and not two.
    """
    response = JsonResponse(json_safe(execute_list_available_indicators()))
    response["Cache-Control"] = INDICATOR_CATALOGUE_CACHE_CONTROL
    return response
