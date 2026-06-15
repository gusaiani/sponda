"""Topic guardrail: cheap classifier that gates the expensive answer call.

Every question runs through gpt-4o-mini with structured output before any
gpt-4o call. Off-topic and jailbreak attempts are rejected here, so a 
rejected question costs ~1/40th of an answered one and can never reach
the expensive model.
"""
from typing import Literal

from pydantic import BaseModel
from django.conf import settings

from assistant.openai_client import get_openai_client
from assistant.prompts import GUARDRAIL_SYSTEM_PROMPT

# The three buckets the classifier sorts every question into. Only
# `on_topic` advances to the answer model; the other two short-circuit
# to the fixed off-topic copy in promps.OFF_TOPIC_RESPONSE.
Classification = Literal["on_topic", "off_topic", "jailbreak"]

class GuardrailVerdict(BaseModel):
    """Structured output schema for the guardrail call.

    OpenAI's `response_format=GuardrailVerdict` forces the model to emit
    JSON that parses into this exact shape — no free-form text to parse,
    no regex, no failure mode where the verdict is unreadable.
    """

    classification: Classification

def classify_question(question: str, company_context: str) -> GuardrailVerdict:
    """Classify a user question with the cheap model before any expensive call.

    `question` is raw user text - treat as untrusted. `company_context` is
    the assembled <COMPANY_DATA> block; it goes to the classifier too so
    the model can tell "is this question about *this* company" apart
    from "is this question on-topic in the abstract".

    Returns the parsed `GuardrailVerdict` - the caller branches on
    `.classification` and either streams an answer or sends the fixed
    off-topic copy.
    """

    # The classifier sees the same <COMPANY_DATA>...</COMPANY_DATA> block
    # the answer model will see, so "is this about *this* company"
    # decisions are made on the real data, not a guess. The plain-text
    # "Question: " label sits OUTSIDE the data block - user text is never
    # injected inside the delimiters where the system prompt would treat 
    # it as data.
    user_message = (
        f"{company_context}\n"
        f"\n"
        f"Question: {question}"
    )

    # Two-message shape: the harness rules go in the system role, the
    # data + question goes in the user role. Same shape we'll use later
    # for the answer call - keeps the mental model consistent.
    messages = [
        {"role": "system", "content": GUARDRAIL_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # `.beta.chat.completions.parse` is OpenAI's structured-output
    # entrypoint: pass a Pydantic class as response_format and the SDK
    # both forces a schema-conformant JSON reply AND parses it into the
    # model on the way back. No regex, no json.loads, no surprises.
    client = get_openai_client()
    response = client.beta.chat.completions.parse(
        model=settings.ASSISTANT_GUARD_MODEL,
        messages=messages,
        response_format=GuardrailVerdict,
    )

    # The SDK already parsed the JSON into a GuardrailVerdict for us;
    # we just hand it back. Caller branches on .classification
    return response.choices[0].message.parsed