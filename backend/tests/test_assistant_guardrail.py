"""Tests for the cheap-classifier guardrail."""
from unittest.mock import MagicMock, patch

from django.conf import settings

from assistant.guardrail import GuardrailVerdict, classify_question
from assistant.prompts import GUARDRAIL_SYSTEM_PROMPT


class TestClassifyQuestion:
    def test_calls_guard_model_with_structured_output_and_threads_verdict(self):
        """One test, every safety knob.

        Verifies that classify_question:
        - calls the cheap ASSISTANT_GUARD_MODEL (not the expensive one)
        - hands the SDK GuardrailVerdict as response_format (without
          this, structured-output silently degrades to free-form text)
        - sends GUARDRAIL_SYSTEM_PROMPT in the system role
        - sends BOTH the <COMPANY_DATA> block and the raw question in the
          user role (user text never sits inside the data delimiters)
        - threads the SDK's parsed verdict back to the caller unchanged
        """
        question = "Is PETR4 cheap on a PE10 basis?"
        company_context = "<COMPANY_DATA>\nticker:PETR4\n</COMPANY_DATA>"

        fake_verdict = GuardrailVerdict(classification="on_topic")
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=MagicMock(parsed=fake_verdict))]

        fake_client = MagicMock()
        fake_client.beta.chat.completions.parse.return_value = fake_response

        with patch(
            "assistant.guardrail.get_openai_client",
            return_value=fake_client,
        ):
            verdict = classify_question(
                question=question,
                company_context=company_context,
            )

        # Threaded through unchanged - caller branches on this
        assert verdict is fake_verdict

        # Now the wiring assertions: every kwarg that matters for safety
        # or cost is locked. Renaming the setting, swapping the schema,
        # or moving the company context into the system role all break
        # this test loudly instead of silently shipping a broken guard.
        call_kwargs = fake_client.beta.chat.completions.parse.call_args.kwargs

        assert call_kwargs["model"] == settings.ASSISTANT_GUARD_MODEL
        assert call_kwargs["response_format"] is GuardrailVerdict

        system_message, user_message = call_kwargs["messages"]
        assert system_message == {
            "role": "system",
            "content": GUARDRAIL_SYSTEM_PROMPT,
        }
        assert user_message["role"] == "user"
        assert company_context in user_message["content"]
        assert question in user_message["content"]