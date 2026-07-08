"""Assistant config lives in Django settings (django-environ).

Asserts safe defaults so a missing .env entry can never silently disable a
guardrail or remove the cost ceiling — it should degrade, not run unbounded.
"""
from django.conf import settings


class TestAssistantSettings:
    def test_openai_api_key_present_and_defaults_empty(self):
        # Absent key must not crash import; the endpoint will 503 instead
        assert hasattr(settings, "OPENAI_API_KEY")
        assert isinstance(settings.OPENAI_API_KEY, str)

    def test_model_defaults(self):
        assert settings.ASSISTANT_ANSWER_MODEL == "gpt-4o"
        assert settings.ASSISTANT_GUARD_MODEL == "gpt-4o-mini"

    def test_quota_defaults(self):
        assert settings.ASSISTANT_PAYING_PER_DAY == 200
        # 0 => free trial OFF in v1 (superuser-only); enabling it is one env var
        assert settings.ASSISTANT_FREE_TRIAL_PER_DAY == 0

    def test_input_and_cost_guards(self):
        assert settings.ASSISTANT_MAX_QUESTION_CHARS == 1000
        # Global per-day USD kill-switch; a low default is the safe one
        assert settings.ASSISTANT_GLOBAL_DAILY_USD_CAP == 10.0

    def test_history_caps(self):
        # Conversation memory must be bounded so a long session can't balloon
        # prompt size (and cost). A few turns is enough for natural follow-ups.
        assert settings.ASSISTANT_MAX_HISTORY_TURNS == 4
        assert settings.ASSISTANT_MAX_HISTORY_ANSWER_CHARS == 2000

    def test_screening_defaults(self):
        # Feature-flagged off by default; the flag is enforced server-side
        # in assistant.views.screen, so a missing .env entry can never
        # accidentally expose the trial-tier screening endpoint.
        assert settings.ASSISTANT_SCREENING_ENABLED is False
        assert settings.ASSISTANT_SCREENING_MODEL == "gpt-4o"
        # Bounds worst-case latency/cost per screening question - each
        # tool-calling round is one OpenAI call.
        assert settings.ASSISTANT_MAX_TOOL_ROUNDS == 6