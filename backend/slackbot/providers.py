"""Provider dispatch: one screening question on the asker's own key.

Both agent loops speak the same event vocabulary (assistant.agent
dataclasses); this module picks the loop for the stored provider, feeds
it a client built from the user's key, and folds the event stream into
one AgentAnswer the Celery task can post to Slack.
"""
from dataclasses import dataclass, field

from openai import OpenAI

from assistant.agent import (
    AnswerToken,
    Completed,
    Failed,
    ScreenResults,
    ToolCallStarted,
    run_screening_agent,
)
from slackbot.anthropic_agent import run_anthropic_screening_agent

# Same posture as assistant.openai_client, but per-request: BYOK clients
# are built fresh per question (a cached client would pin one user's key
# in the pool) with the same fail-fast timeout.
OPENAI_REQUEST_TIMEOUT_SECONDS = 30
OPENAI_MAX_RETRIES = 1


@dataclass
class AgentAnswer:
    text: str
    input_tokens: int
    output_tokens: int
    error_code: str | None
    # Symbols the screener actually returned this turn — the allowlist for
    # rewriting tickers into links to their Sponda pages.
    symbols: set = field(default_factory=set)


def _events_for_provider(*, provider, api_key, question, history_messages, locale):
    if provider == "openai":
        client = OpenAI(
            api_key=api_key,
            timeout=OPENAI_REQUEST_TIMEOUT_SECONDS,
            max_retries=OPENAI_MAX_RETRIES,
        )
        return run_screening_agent(
            question=question, history_messages=history_messages,
            locale=locale, client=client,
        )
    if provider == "anthropic":
        return run_anthropic_screening_agent(
            question=question, history_messages=history_messages,
            locale=locale, api_key=api_key,
        )
    raise ValueError(f"Unknown provider: {provider}")


def run_agent_for_provider(*, provider: str, api_key: str, question: str,
                           history_messages: list, locale: str) -> AgentAnswer:
    answer_fragments: list[str] = []
    symbols: set[str] = set()
    input_tokens = output_tokens = 0
    error_code = None

    for event in _events_for_provider(
        provider=provider, api_key=api_key, question=question,
        history_messages=history_messages, locale=locale,
    ):
        if isinstance(event, AnswerToken):
            answer_fragments.append(event.text)
        elif isinstance(event, ScreenResults):
            symbols.update(
                row["ticker"] for row in event.rows if row.get("ticker")
            )
        elif isinstance(event, ToolCallStarted):
            # Anything said before a tool round ("let me screen that…")
            # is preamble, not the answer — start over.
            answer_fragments.clear()
        elif isinstance(event, Completed):
            input_tokens = event.input_tokens
            output_tokens = event.output_tokens
        elif isinstance(event, Failed):
            error_code = event.code

    text = "".join(answer_fragments).strip() if error_code is None else ""
    return AgentAnswer(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error_code=error_code,
        symbols=symbols,
    )
