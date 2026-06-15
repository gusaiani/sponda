"""Tests for the streaming /api/assistant/ask/ view."""
import pytest

from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model

from assistant.guardrail import GuardrailVerdict

ASK_URL = "/api/assistant/ask/"


@pytest.mark.django_db
class TestAskView:
    @pytest.fixture(autouse=True)
    def _set_openai_key(self, settings):
        """The view 503s when OPENAI_API_KEY is unset (assistant_not_configured).
        CI has no key, so set a dummy one for the whole class; tests that mock
        the OpenAI client need the guard to pass. The missing-key test overrides
        this back to "" in its own body.
        """
        settings.OPENAI_API_KEY = "sk-test-key"

    def test_anonymous_request_is_rejected(self, client):
        """v1 is superuser-only. The gate is server-side, not a UI hide —
        an unauthenticated POST must never reach the OpenAI call.
        """
        response = client.post(
            ASK_URL,
            data={
                "ticker": "PETR4",
                "tab": "metrics",
                "locale": "pt",
                "question": "Is it cheap?",
            },
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_authenticated_non_superuser_is_rejected(self, client):
        """The gate is is_superuser, NOT is_authenticated. A regular
        logged-in user must also be turned away in v1.
        """

        regular_user = get_user_model().objects.create_user(
            username="regular@example.com",
            email="regular@example.com",
            password="pw123456",
        )
        client.force_login(regular_user)

        response = client.post(
            ASK_URL,
            data={
                "ticker": "PETR4",
                "tab": "metrics",
                "locale": "pt",
                "question": "Is it cheap?",
            },
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_superuser_streams_meta_token_done_frames(self, superuser_client):
        """Happy path: superuser asks an on-topic question, the view
        streams `meta → token → token → done` SSE frames in order.

        Every external dependency is mocked so the test is hermetic
        (no DB beyond Django auth, no OpenAI, no real quote computation).
        What this locks:
        - 200 OK with Content-Type: text/event-stream
        - X-Accel-Buffering: no  (nginx bypass - without this header
          the stream is buffered and the whole point is lost)
        - frames are emitted in the order meta → token* → done
        """

        # Fake OpenAI streaming response: two token chunks, then a final
        # chunk that carries the usage numbers (mirrors the real SDK
        # shape when stream_options={"include_usage": True}).
        def make_token_chunk(text: str) -> MagicMock:
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=text))]
            chunk.usage = None
            return chunk

        usage_chunk = MagicMock()
        usage_chunk.choices = [MagicMock(delta=MagicMock(content=None))]
        usage_chunk.usage = MagicMock(prompt_tokens=42, completion_tokens=7)

        fake_stream = iter([
            make_token_chunk("PETR4 "),
            make_token_chunk("is cheap."),
            usage_chunk,
        ])

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_stream

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: PETR4\n</COMPANY_DATA>",
        ), patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="on_topic")
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "PETR4",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "Is PETR4 cheap on a PE10 basis?",
                },
                content_type="application/json",
            )

            # Consume the streamed body inside the `with` so the patched
            # OpenAI client is still active while the generator runs.
            body = b"".join(response.streaming_content).decode()

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/event-stream")
        assert response["X-Accel-Buffering"] == "no"

        # Frame order matters - meta first so the client can render the
        # header, tokens in between, done last so the client knows to
        # stop reading and the server can close cleanly.
        meta_index = body.index("event: meta")
        first_token_index = body.index("event: token")
        done_index = body.index("event: done")
        assert meta_index < first_token_index < done_index

        # The actual token text made it through.
        assert "PETR4" in body
        assert "is cheap." in body

    def test_token_frames_are_json_encoded(self, superuser_client):
        """Every SSE frame's `data` must be JSON — the client JSON.parses all
        of them on one path. Token text is a string, so it must be emitted
        JSON-encoded (`data: "Para "`, not `data: Para `); otherwise the
        browser's JSON.parse throws on the first token and the whole answer is
        silently dropped (surfacing as a generic 'fetch failed').
        """
        def make_token_chunk(text):
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=text))]
            chunk.usage = None
            return chunk

        usage_chunk = MagicMock()
        usage_chunk.choices = [MagicMock(delta=MagicMock(content=None))]
        usage_chunk.usage = MagicMock(prompt_tokens=1, completion_tokens=1)

        fake_stream = iter([make_token_chunk("Para "), usage_chunk])
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_stream

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: PETR4\n</COMPANY_DATA>",
        ), patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="on_topic"),
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={"ticker": "PETR4", "tab": "metrics", "locale": "pt", "question": "Is PETR4 cheap?"},
                content_type="application/json",
            )
            body = b"".join(response.streaming_content).decode()

        assert 'data: "Para "' in body          # JSON-encoded token
        assert "\ndata: Para \n" not in body     # never the raw, unquoted form

    def test_empty_question_is_rejected_with_400(self, superuser_client):
        """An empty question must never reach OpenAI - there's nothing
        to classify or answer, and we'd be paying for the round trip.
        """

        response = superuser_client.post(
            ASK_URL,
            data={
                "ticker": "PETR4",
                "tab": "metrics",
                "locale": "pt",
                "question": "    ",
            },
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_oversized_question_is_rejected_with_400(self, superuser_client, settings):
        """ASSISTANT_MAX_QUESTION_CHARS caps input cost. Beyond the cap
        we reject before the guardrail call - cheap rejection, not cheap-model rejection.
        """
        settings.ASSISTANT_MAX_QUESTION_CHARS = 50

        too_long_question = "x" * (settings.ASSISTANT_MAX_QUESTION_CHARS + 1)

        response = superuser_client.post(
            ASK_URL,
            data={
                "ticker": "PETR4",
                "tab": "metrics",
                "locale": "pt",
                "question": too_long_question,
            },
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_off_topic_question_short_circuits_before_answer_model(self, superuser_client):
        """When the guardrail classifies a question as off_topic we must
        stream the canned localized response and NEVER call the expensive
        answer odel. This is the whole cost-control story for the harness.
        """
        fake_openai_client = MagicMock()

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: PETR4\n</COMPANY_DATA>",
        ), patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="off_topic")
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_openai_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "PETR4",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "What's the weather in Rio?",
                },
                content_type="application/json",
            )
            body = b"".join(response.streaming_content).decode()

        assert response.status_code == 200
        
        assert "event: off_topic" in body
        assert "Só posso responder perguntas" in body
        assert "event: done" in body

        fake_openai_client.chat.completions.create.assert_not_called()

    def test_openai_timeout_midstream_emits_error_frame(self, superuser_client):
        """OpenAI can time out after we've already shipped meta + a token.
        The generator must catch it, emit an `error` frame with a stable
        machine-readable code, and exit cleanly - never let the exception
        bubble out of the StreamingHttpResponse iterator.
        """
        from openai import APITimeoutError

        def exploding_stream():
            good_chunk = MagicMock()
            good_chunk.choices = [MagicMock(delta=MagicMock(content="The "))]
            good_chunk.usage = None
            yield good_chunk
            raise APITimeoutError(request=MagicMock())

        fake_openai_client = MagicMock()
        fake_openai_client.chat.completions.create.return_value = exploding_stream()

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: PETR4\n</COMPANY_DATA>",
        ), patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="on_topic")
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_openai_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "PETR4",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "Is PETR4 cheap?",
                },
                content_type="application/json",
            )
            body = b"".join(response.streaming_content).decode()

        assert response.status_code == 200
        assert "event: token" in body
        assert "event: error" in body
        assert "upstream_timeout" in body

    def test_successful_answer_writes_llmquery_row(self, superuser_client, superuser):
        """Every call - success, off_topic, or error, - must leave one
        LLMQuery row behind. The row is what assistant_quota will count
        against the daily cap and what the cost dashboard reads from, so
        persisting it is non-negotiable, even on the happy path.
        """
        from assistant.models import LLMQuery

        def make_token_chunk(text):
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=text))]
            chunk.usage = None
            return chunk

        usage_chunk = MagicMock()
        usage_chunk.choices = [MagicMock(delta=MagicMock(content=None))]
        usage_chunk.usage = MagicMock(prompt_tokens=42, completion_tokens=7)

        fake_stream = iter([
            make_token_chunk("PETR4"),
            make_token_chunk("is cheap."),
            usage_chunk,
        ])
        fake_openai_client = MagicMock()
        fake_openai_client.chat.completions.create.return_value = fake_stream

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: PETR4\n</COMPANY_DATA>",
        ), patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="on_topic")
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_openai_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "PETR4",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "Is PETR4 cheap?",
                },
                content_type="application/json",
            )
            b"".join(response.streaming_content)

        assert LLMQuery.objects.count() == 1
        row = LLMQuery.objects.get()
        assert row.user == superuser
        assert row.ticker == "PETR4"
        assert row.tab == "metrics"
        assert row.locale == "pt"
        assert row.classification == "on_topic"
        assert row.status == "ok"
        assert row.input_tokens == 42
        assert row.output_tokens == 7
        assert row.cost_usd > 0
        assert row.model

    def test_missing_api_key_returns_503_before_any_model_call(self, superuser_client, settings):
        """With OPENAI_API_KEY unset the assistant cannot reach OpenAI. The
        view must fail fast with a 503 and a machine-readable code BEFORE the
        guardrail runs — never start a 200 stream that dies mid-flight, which
        would leave the client hanging on a dead connection with no frames.
        """
        settings.OPENAI_API_KEY = ""

        with patch("assistant.views.classify_question") as classify, patch(
            "assistant.views.get_openai_client"
        ) as get_client:
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "PETR4",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "Is it cheap?",
                },
                content_type="application/json",
            )

        assert response.status_code == 503
        assert response.json()["code"] == "assistant_not_configured"
        # The whole point is to short-circuit: no guardrail, no client build.
        classify.assert_not_called()
        get_client.assert_not_called()

    def test_window_years_is_threaded_into_context(self, superuser_client):
        """The PRAZO slider window rides the request and must reach
        build_company_context, so the data block reflects the window the user
        is viewing — not the backend's all-history default.
        """
        usage_chunk = MagicMock()
        usage_chunk.choices = [MagicMock(delta=MagicMock(content=None))]
        usage_chunk.usage = MagicMock(prompt_tokens=1, completion_tokens=1)
        token_chunk = MagicMock()
        token_chunk.choices = [MagicMock(delta=MagicMock(content="ok"))]
        token_chunk.usage = None

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = iter([token_chunk, usage_chunk])

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: WEGE3\n</COMPANY_DATA>",
        ) as build_context, patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="on_topic"),
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "WEGE3",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "Is it cheap?",
                    "years": 5,
                },
                content_type="application/json",
            )
            b"".join(response.streaming_content)

        assert build_context.call_args.kwargs["years"] == 5

    def test_out_of_range_window_years_is_ignored(self, superuser_client):
        """Untrusted input: a window outside the slider's 1..20 range degrades
        to None (no windowed recompute), never raises or feeds a garbage
        window into the calc.
        """
        usage_chunk = MagicMock()
        usage_chunk.choices = [MagicMock(delta=MagicMock(content=None))]
        usage_chunk.usage = MagicMock(prompt_tokens=1, completion_tokens=1)
        token_chunk = MagicMock()
        token_chunk.choices = [MagicMock(delta=MagicMock(content="ok"))]
        token_chunk.usage = None
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = iter([token_chunk, usage_chunk])

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: WEGE3\n</COMPANY_DATA>",
        ) as build_context, patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="on_topic"),
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "WEGE3",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "Is it cheap?",
                    "years": 999,
                },
                content_type="application/json",
            )
            b"".join(response.streaming_content)

        assert build_context.call_args.kwargs["years"] is None

    def test_history_is_interleaved_into_answer_messages(self, superuser_client):
        """A follow-up question carries the prior Q&A so the answer model has
        context. The view must interleave the clamped history between the
        system prompt and the current question — the shape OpenAI needs for
        multi-turn memory.
        """
        def make_token_chunk(text):
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=text))]
            chunk.usage = None
            return chunk

        usage_chunk = MagicMock()
        usage_chunk.choices = [MagicMock(delta=MagicMock(content=None))]
        usage_chunk.usage = MagicMock(prompt_tokens=1, completion_tokens=1)

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = iter(
            [make_token_chunk("Sure."), usage_chunk]
        )

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: PETR4\n</COMPANY_DATA>",
        ), patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="on_topic"),
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "PETR4",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "And the year before?",
                    "history": [
                        {"question": "Is it cheap?", "answer": "On PE10, yes."},
                    ],
                },
                content_type="application/json",
            )
            b"".join(response.streaming_content)

        messages = fake_client.chat.completions.create.call_args.kwargs["messages"]
        roles = [message["role"] for message in messages]

        # system, then the prior turn (user/assistant), then the live question.
        assert roles == ["system", "user", "assistant", "user"]
        assert "Is it cheap?" in messages[1]["content"]
        assert messages[2]["content"] == "On PE10, yes."
        assert "And the year before?" in messages[-1]["content"]

    def test_history_is_clamped_to_max_turns(self, superuser_client, settings):
        """The per-session cost ceiling is enforced server-side: even if the
        client sends more turns than allowed, only the most recent survive.
        Never trust the client to bound its own memory.
        """
        settings.ASSISTANT_MAX_HISTORY_TURNS = 1

        usage_chunk = MagicMock()
        usage_chunk.choices = [MagicMock(delta=MagicMock(content=None))]
        usage_chunk.usage = MagicMock(prompt_tokens=1, completion_tokens=1)
        token_chunk = MagicMock()
        token_chunk.choices = [MagicMock(delta=MagicMock(content="ok"))]
        token_chunk.usage = None

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = iter([token_chunk, usage_chunk])

        with patch(
            "assistant.views.build_company_context",
            return_value="<COMPANY_DATA>\nticker: PETR4\n</COMPANY_DATA>",
        ), patch(
            "assistant.views.classify_question",
            return_value=GuardrailVerdict(classification="on_topic"),
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "PETR4",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "Latest?",
                    "history": [
                        {"question": "oldest", "answer": "a0"},
                        {"question": "newest", "answer": "a1"},
                    ],
                },
                content_type="application/json",
            )
            b"".join(response.streaming_content)

        messages = fake_client.chat.completions.create.call_args.kwargs["messages"]
        serialized = " ".join(message["content"] for message in messages)
        assert "newest" in serialized
        assert "oldest" not in serialized

    def test_over_quota_request_is_rejected_with_429(self, superuser_client):
        """A caller already at their daily cap must be turned away with 429
        BEFORE the guardrail or answer model runs. would_exceed_assistant_limit
        is the single seam; we patch it True so this test pins the wiring, not
        the tier match (that's locked in test_assistant_quota.py).
        """
        fake_openai_client = MagicMock()

        with patch(
            "assistant.views.would_exceed_assistant_limit",
            return_value=True,
        ), patch(
            "assistant.views.get_openai_client",
            return_value=fake_openai_client,
        ):
            response = superuser_client.post(
                ASK_URL,
                data={
                    "ticker": "PETR4",
                    "tab": "metrics",
                    "locale": "pt",
                    "question": "Is it cheap?",
                },
                content_type="application/json",
            )
        
        assert response.status_code == 429
        fake_openai_client.chat.completions.create.assert_not_called()
