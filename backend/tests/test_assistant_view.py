"""Tests for the streaming /api/assistant/ask/ view."""
import pytest


ASK_URL = "/api/assistant/ask/"


@pytest.mark.django_db
class TestAskView:
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
        from django.contrib.auth import get_user_model

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

    def test_superuser_streams_meta_token_done_frames(self, client):
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
        from unittest.mock import MagicMock, patch
        from django.contrib.auth import get_user_model

        from assistant.guardrail import GuardrailVerdict

        superuser = get_user_model().objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="pw123456",
        )
        client.force_login(superuser)

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
            response = client.post(
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

    def test_empty_question_is_rejected_with_400(self, client):
        """An empty question must never reach OpenAI - there's nothing
        to classify or answer, and we'd be paying for the round trip.
        """
        from django.contrib.auth import get_user_model

        superuser = get_user_model().objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="pw123456",
        )
        client.force_login(superuser)

        response = client.post(
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

    def test_oversized_question_is_rejected_with_400(self, client, settings):
        """ASSISTANT_MAX_QUESTION_CHARS caps input cost. Beyond the cap
        we reject before the guardrail call - cheap rejection, not cheap-model rejection.
        """
        from django.contrib.auth import get_user_model

        settings.ASSISTANT_MAX_QUESTION_CHARS = 50

        superuser = get_user_model().objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="pw123456",
        )
        client.force_login(superuser)

        too_long_question = "x" * (settings.ASSISTANT_MAX_QUESTION_CHARS + 1)

        response = client.post(
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

    def test_off_topic_question_short_circuits_before_answer_model(self, client):
        """When the guardrail classifies a question as off_topic we must
        stream the canned localized response and NEVER call the expensive
        answer odel. This is the whole cost-control story for the harness.
        """
        from unittest.mock import MagicMock, patch
        from django.contrib.auth import get_user_model

        from assistant.guardrail import GuardrailVerdict

        superuser = get_user_model().objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="pw123456",
        )
        client.force_login(superuser)

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
            response = client.post(
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

    def test_openai_timeout_midstream_emits_error_frame(self, client):
        """OpenAI can time out after we've already shipped meta + a token.
        The generator must catch it, emit an `error` frame with a stable
        machine-readable code, and exit cleanly - never let the exception
        bubble out of the StreamingHttpResponse iterator.
        """
        from unittest.mock import MagicMock, patch
        from django.contrib.auth import get_user_model
        from openai import APITimeoutError

        from assistant.guardrail import GuardrailVerdict

        superuser = get_user_model().objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="pw123456",
        )
        client.force_login(superuser)

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
            response = client.post(
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