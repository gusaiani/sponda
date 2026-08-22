"""The Anthropic screening agent loop — the BYOK twin of assistant.agent.

Same system prompt, same tool executors (via execute_named_tool), same
event vocabulary, so a question answered through an Anthropic key cannot
drift from one answered through OpenAI. The rounds are non-streaming:
Slack gets one final message, so per-token streaming would buy nothing
and cost the stream-error handling the SSE path needs.
"""
import json

from anthropic import (
    Anthropic,
    APIError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from django.conf import settings

from assistant.agent import (
    AnswerToken,
    Completed,
    Failed,
    _build_user_message,
    execute_named_tool,
)
from assistant.prompts import SCREENING_SYSTEM_PROMPT
from assistant.tools import OPENAI_TOOL_SCHEMAS

# Same network posture as the OpenAI client singleton: fail fast rather
# than pin a Celery worker on a hung upstream.
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 1

# Screening answers are a few paragraphs plus a small table; 4096 output
# tokens is roomy without letting a runaway answer bill the user's key.
MAX_ANSWER_TOKENS = 4096


def _convert_tool_schema(openai_schema: dict) -> dict:
    """OpenAI function-tool schema → Anthropic tool schema.

    Both wrap the same JSON Schema; only the envelope differs
    (function.parameters → input_schema).
    """
    function = openai_schema["function"]
    return {
        "name": function["name"],
        "description": function["description"],
        "input_schema": function["parameters"],
    }


ANTHROPIC_TOOL_SCHEMAS = [_convert_tool_schema(s) for s in OPENAI_TOOL_SCHEMAS]


def run_anthropic_screening_agent(*, question: str, history_messages: list,
                                  locale: str, api_key: str):
    """Yield agent events for one screening question on the user's key.

    Terminates with exactly one Completed or one Failed, mirroring
    assistant.agent.run_screening_agent.
    """
    client = Anthropic(
        api_key=api_key,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )
    messages = [*history_messages, _build_user_message(question, locale)]
    totals = Completed()

    try:
        for round_index in range(settings.ASSISTANT_MAX_TOOL_ROUNDS + 1):
            # Same round bound as the OpenAI loop: past it the model must
            # answer from the data it already has.
            out_of_rounds = round_index == settings.ASSISTANT_MAX_TOOL_ROUNDS
            response = client.messages.create(
                model=settings.SLACKBOT_ANTHROPIC_MODEL,
                max_tokens=MAX_ANSWER_TOKENS,
                system=SCREENING_SYSTEM_PROMPT,
                messages=messages,
                tools=ANTHROPIC_TOOL_SCHEMAS,
                tool_choice={"type": "none"} if out_of_rounds else {"type": "auto"},
            )
            totals.input_tokens += response.usage.input_tokens
            totals.output_tokens += response.usage.output_tokens

            if response.stop_reason == "refusal":
                # Claude Opus 5-family models can decline a request with a
                # 200 + refusal stop reason; there is no answer to post.
                yield Failed("refusal")
                return

            for block in response.content:
                if block.type == "text" and block.text:
                    yield AnswerToken(block.text)

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            if not tool_use_blocks:
                yield totals
                return

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in tool_use_blocks:
                events, payload_for_model = execute_named_tool(
                    block.name, block.input or {}
                )
                yield from events
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(payload_for_model, ensure_ascii=False),
                })
            messages.append({"role": "user", "content": tool_results})

        # Defensive: the forced-final round returns above; reaching here
        # means the model kept calling tools despite tool_choice none.
        yield totals
    except AuthenticationError:
        yield Failed("invalid_api_key")
    except RateLimitError:
        yield Failed("rate_limited")
    except APITimeoutError:
        yield Failed("upstream_timeout")
    except APIError:
        yield Failed("internal")
