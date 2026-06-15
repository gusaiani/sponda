"""Tests for bounded conversation memory.

The client resends the running Q&A each turn so follow-ups have context.
`build_history_messages` is the cost guard: it turns that untrusted list
into OpenAI chat messages while clamping turn count and per-message length,
so a long session can never balloon the prompt.
"""
from assistant.history import build_history_messages


class TestBuildHistoryMessages:
    def test_pairs_become_alternating_user_assistant_messages(self):
        """Each {question, answer} pair expands to a user message then an
        assistant message, in order — the shape OpenAI expects for memory.
        """
        history = [
            {"question": "Is it cheap?", "answer": "On PE10, yes."},
            {"question": "And on PFCF10?", "answer": "Also cheap."},
        ]

        messages = build_history_messages(
            history,
            max_turns=4,
            max_question_chars=1000,
            max_answer_chars=2000,
        )

        assert messages == [
            {"role": "user", "content": "Question: Is it cheap?"},
            {"role": "assistant", "content": "On PE10, yes."},
            {"role": "user", "content": "Question: And on PFCF10?"},
            {"role": "assistant", "content": "Also cheap."},
        ]

    def test_drops_oldest_turns_beyond_cap(self):
        """Memory is bounded: only the most recent `max_turns` pairs survive,
        oldest dropped first. This is the per-session cost ceiling.
        """
        history = [
            {"question": f"q{index}", "answer": f"a{index}"}
            for index in range(6)
        ]

        messages = build_history_messages(
            history,
            max_turns=2,
            max_question_chars=1000,
            max_answer_chars=2000,
        )

        # Only the last two pairs (q4/a4, q5/a5) remain.
        assert messages == [
            {"role": "user", "content": "Question: q4"},
            {"role": "assistant", "content": "a4"},
            {"role": "user", "content": "Question: q5"},
            {"role": "assistant", "content": "a5"},
        ]

    def test_clamps_long_question_and_answer(self):
        """A pathological history entry (huge question or answer) is truncated
        per message, so one big turn can't blow the prompt budget.
        """
        history = [{"question": "x" * 50, "answer": "y" * 50}]

        messages = build_history_messages(
            history,
            max_turns=4,
            max_question_chars=10,
            max_answer_chars=5,
        )

        assert messages[0] == {"role": "user", "content": "Question: " + "x" * 10}
        assert messages[1] == {"role": "assistant", "content": "y" * 5}

    def test_skips_incomplete_or_malformed_entries(self):
        """Only complete pairs become memory. A turn missing its answer (e.g.
        the user stopped mid-stream, or an off_topic redirect) carries no
        signal and must not enter the prompt. Non-dict junk is ignored too.
        """
        history = [
            {"question": "Has an answer", "answer": "Yes."},
            {"question": "No answer yet", "answer": ""},
            {"question": "", "answer": "orphan answer"},
            "not a dict",
            {"answer": "missing question key"},
        ]

        messages = build_history_messages(
            history,
            max_turns=4,
            max_question_chars=1000,
            max_answer_chars=2000,
        )

        assert messages == [
            {"role": "user", "content": "Question: Has an answer"},
            {"role": "assistant", "content": "Yes."},
        ]

    def test_non_list_history_yields_no_messages(self):
        """Untrusted input: anything that isn't a list (None, a string, a
        dict) degrades to empty memory rather than raising.
        """
        assert build_history_messages(None, max_turns=4, max_question_chars=10, max_answer_chars=10) == []
        assert build_history_messages("nope", max_turns=4, max_question_chars=10, max_answer_chars=10) == []
        assert build_history_messages({}, max_turns=4, max_question_chars=10, max_answer_chars=10) == []
