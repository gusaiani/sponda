"""Tests for the cached OpenAI client singleton."""
from openai import OpenAI
from assistant.openai_client import get_openai_client


class TestGetOpenAIClient:
    def setup_method(self):
        # The client is memoized with lru_cache — drop the cache before
        # each test so settings overrides below take effect on a rebuild.
        get_openai_client.cache_clear()

    def test_returns_an_openai_client(self, settings):
        settings.OPENAI_API_KEY = "sk-test-key"
        assert isinstance(get_openai_client(), OpenAI)

    def test_same_instance_on_repeated_calls(self, settings):
        settings.OPENAI_API_KEY = "sk-test-key"
        # Two calls, one object — proof the lru_cache is doing its job
        assert get_openai_client() is get_openai_client()