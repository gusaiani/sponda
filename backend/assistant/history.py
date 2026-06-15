"""Bounded conversation memory for the assistant.

The client resends the running Q&A each turn so a follow-up like "and the
year before?" has the context it needs. This module is the cost guard: it
turns that untrusted list into OpenAI chat messages while clamping turn
count and per-message length, so a long session can never balloon the
prompt. Newest turns win — anything past the cap is dropped oldest-first.
"""
from __future__ import annotations


def build_history_messages(
    raw_history,
    *,
    max_turns: int,
    max_question_chars: int,
    max_answer_chars: int,
) -> list[dict]:
    """Clamp an untrusted history list into alternating chat messages.

    Each `{"question", "answer"}` pair becomes a user message followed by an
    assistant message. Incomplete pairs (missing either side) and non-dict
    junk are dropped — only complete turns carry signal. A non-list input
    degrades to empty memory rather than raising.
    """
    if not isinstance(raw_history, list):
        return []

    # Collect complete pairs first, so the turn cap counts *real* remembered
    # turns — malformed junk between two good turns can't push a valid turn
    # out of the window.
    valid_pairs = []
    for pair in raw_history:
        if not isinstance(pair, dict):
            continue
        question = (pair.get("question") or "").strip()
        answer = (pair.get("answer") or "").strip()
        if not question or not answer:
            continue
        valid_pairs.append((question, answer))

    # Keep only the most recent `max_turns` pairs — oldest dropped first.
    recent_pairs = valid_pairs[-max_turns:] if max_turns > 0 else []

    messages: list[dict] = []
    for question, answer in recent_pairs:
        messages.append({
            "role": "user",
            "content": f"Question: {question[:max_question_chars]}",
        })
        messages.append({
            "role": "assistant",
            "content": answer[:max_answer_chars],
        })
    return messages
