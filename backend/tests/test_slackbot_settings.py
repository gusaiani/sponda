"""Slackbot config lives in Django settings (django-environ).

Same philosophy as the assistant settings tests: everything defaults to
off/empty so a missing .env entry disables the Slack surface (503) rather
than crashing imports or, worse, running unsigned.
"""
from django.conf import settings


class TestSlackbotSettings:
    def test_slack_credentials_default_empty(self):
        # Empty secret → signature check fails closed and endpoints 503.
        assert settings.SLACK_SIGNING_SECRET == ""
        assert settings.SLACK_BOT_TOKEN == ""

    def test_encryption_key_defaults_empty(self):
        # Empty key → crypto raises ImproperlyConfigured on first use;
        # it must never silently fall back to plaintext storage.
        assert settings.SLACKBOT_KEY_ENCRYPTION_KEY == ""

    def test_anthropic_model_default(self):
        assert settings.SLACKBOT_ANTHROPIC_MODEL == "claude-opus-5"
