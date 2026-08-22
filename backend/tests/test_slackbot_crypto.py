"""Encryption at rest for BYOK Slack LLM keys (slackbot/crypto.py).

The keys users paste into the /sponda-key modal are billable credentials;
they must never touch the database in plaintext. Fernet gives authenticated
encryption, so a tampered ciphertext fails loudly instead of decrypting to
garbage that would then be sent to a provider.
"""
import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from slackbot.crypto import decrypt_api_key, encrypt_api_key

TEST_FERNET_KEY = Fernet.generate_key().decode()


class TestApiKeyEncryption:
    @pytest.fixture(autouse=True)
    def _encryption_key(self, settings):
        settings.SLACKBOT_KEY_ENCRYPTION_KEY = TEST_FERNET_KEY

    def test_roundtrip(self):
        plaintext = "sk-ant-api03-secret"
        token = encrypt_api_key(plaintext)
        assert token != plaintext
        assert decrypt_api_key(token) == plaintext

    def test_ciphertext_is_randomized(self):
        # Fernet embeds a random IV — identical keys must not produce
        # identical rows, or the database would leak key equality.
        assert encrypt_api_key("same-key") != encrypt_api_key("same-key")

    def test_tampered_token_fails_loudly(self):
        token = encrypt_api_key("sk-secret")
        tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        with pytest.raises(InvalidToken):
            decrypt_api_key(tampered)


@override_settings(SLACKBOT_KEY_ENCRYPTION_KEY="")
def test_missing_encryption_key_raises_improperly_configured():
    with pytest.raises(ImproperlyConfigured):
        encrypt_api_key("sk-secret")
