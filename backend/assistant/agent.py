"""The screening agent loop: tool-calling OpenAI rounds, streamed answer.

The loop is transport-agnostic — it yields typed events and never touches
HTTP. The view maps events onto SSE frames; the eval runner consumes the
same events directly. One OpenAI call per round: the model either calls
tools (we execute them and feed the results back as data) or produces the
final answer, whose tokens stream out as they arrive.
"""
import json
from dataclasses import dataclass, field

from django.conf import settings
from openai import APIError, APITimeoutError, RateLimitError

from .openai_client import get_openai_client
from .prompts import SCREENING_SYSTEM_PROMPT
from .tools import OPENAI_TOOL_SCHEMAS, execute_tool


@dataclass
class ToolCallStarted:
    name: str


@dataclass
class InterpretedFilters:
    """The argument set of a screen_companies call — the parsed filter set
    the user must be able to verify at a glance."""
    arguments: dict


@dataclass
class ScreenResults:
    """Full screener rows (ScreenerRow shape, ratings included) for the
    frontend table. The model itself only ever sees the trimmed rows."""
    count: int
    rows: list


@dataclass
class AnswerToken:
    text: str


@dataclass
class Completed:
    """Token totals summed across every round, for cost accounting."""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Failed:
    code: str


@dataclass
class _PendingToolCall:
    """One tool call assembled from streamed deltas: the id and name arrive
    once, the JSON arguments arrive as fragments."""
    call_id: str = ""
    name: str = ""
    argument_fragments: list = field(default_factory=list)

    @property
    def arguments_json(self) -> str:
        return "".join(self.argument_fragments)


def _build_user_message(question: str, locale: str) -> dict:
    # Same delimiting rule as the per-company assistant: user text stays a
    # plain question after the locale line, never inside a data block.
    return {"role": "user", "content": f"locale: {locale}\n\nQuestion: {question}"}


def _accumulate_stream(stream, pending_tool_calls):
    """Drive one response stream: yield AnswerToken for content deltas,
    collect tool-call deltas into pending_tool_calls, return usage."""
    usage = None
    for chunk in stream:
        if chunk.usage is not None:
            usage = chunk.usage
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            yield AnswerToken(delta.content)
        for tool_call_delta in delta.tool_calls or []:
            pending = pending_tool_calls.setdefault(
                tool_call_delta.index, _PendingToolCall()
            )
            if tool_call_delta.id:
                pending.call_id = tool_call_delta.id
            if tool_call_delta.function.name:
                pending.name = tool_call_delta.function.name
            if tool_call_delta.function.arguments:
                pending.argument_fragments.append(
                    tool_call_delta.function.arguments
                )
    return usage


def _execute_pending_tool_call(pending):
    """Run one assembled tool call. Returns (events, payload_for_model).

    Errors — unparseable arguments included — become data the model sees
    and must report honestly, never exceptions that kill the stream.
    """
    try:
        arguments = json.loads(pending.arguments_json)
    except json.JSONDecodeError:
        return [], {"error": f"Invalid JSON arguments for {pending.name}"}

    events = [ToolCallStarted(pending.name)]
    result = execute_tool(pending.name, arguments)

    if pending.name == "screen_companies" and "error" not in result:
        events.append(InterpretedFilters(arguments))
        events.append(
            ScreenResults(
                count=result.get("count", 0),
                rows=result.get("full_rows", []),
            )
        )
        # The model reasons over the trimmed rows; the full rows go to the
        # frontend via ScreenResults and would only waste tokens here.
        payload_for_model = {
            "count": result.get("count", 0),
            "rows": result.get("rows_for_model", []),
        }
    else:
        payload_for_model = result

    return events, payload_for_model


def run_screening_agent(*, question: str, history_messages: list, locale: str):
    """Yield agent events for one screening question.

    Terminates with exactly one Completed (token totals for cost logging)
    or one Failed (mirrors the error codes the ask() view already uses).
    """
    client = get_openai_client()
    messages = [
        {"role": "system", "content": SCREENING_SYSTEM_PROMPT},
        *history_messages,
        _build_user_message(question, locale),
    ]
    totals = Completed()

    try:
        for round_index in range(settings.ASSISTANT_MAX_TOOL_ROUNDS + 1):
            # Past the round bound the model must answer from the data it
            # already has — tool_choice="none" forces the final answer
            # instead of an unbounded tool spiral.
            out_of_rounds = round_index == settings.ASSISTANT_MAX_TOOL_ROUNDS
            stream = client.chat.completions.create(
                model=settings.ASSISTANT_SCREENING_MODEL,
                messages=messages,
                tools=OPENAI_TOOL_SCHEMAS,
                tool_choice="none" if out_of_rounds else "auto",
                stream=True,
                stream_options={"include_usage": True},
            )

            pending_tool_calls = {}
            stream_events = _accumulate_stream(stream, pending_tool_calls)
            while True:
                try:
                    yield next(stream_events)
                except StopIteration as stop:
                    usage = stop.value
                    break
            if usage is not None:
                totals.input_tokens += usage.prompt_tokens
                totals.output_tokens += usage.completion_tokens

            if not pending_tool_calls:
                yield totals
                return

            ordered_calls = [
                pending_tool_calls[index]
                for index in sorted(pending_tool_calls)
            ]
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": pending.call_id,
                        "type": "function",
                        "function": {
                            "name": pending.name,
                            "arguments": pending.arguments_json,
                        },
                    }
                    for pending in ordered_calls
                ],
            })
            for pending in ordered_calls:
                events, payload_for_model = _execute_pending_tool_call(pending)
                yield from events
                messages.append({
                    "role": "tool",
                    "tool_call_id": pending.call_id,
                    "content": json.dumps(payload_for_model, ensure_ascii=False),
                })

        # Defensive: the forced-final round returns above; reaching here
        # means the model somehow kept calling tools with tool_choice="none".
        yield totals
    except APITimeoutError:
        yield Failed("upstream_timeout")
    except RateLimitError:
        yield Failed("rate_limited")
    except APIError:
        yield Failed("internal")
