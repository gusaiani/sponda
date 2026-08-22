"""Encryption at rest for BYOK LLM API keys.

Users paste billable provider credentials into the /sponda-key modal;
those must never reach the database in plaintext. Fernet (AES-128-CBC +
HMAC) gives authenticated encryption: a tampered or wrong-key ciphertext
raises InvalidToken instead of decrypting to garbage that would then be
sent to a provider as if it were a key.

The Fernet key lives in the SLACKBOT_KEY_ENCRYPTION_KEY env var —
deliberately separate from DJANGO_SECRET_KEY so rotating one never
silently invalidates the other's ciphertexts. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet() -> Fernet:
    key = settings.SLACKBOT_KEY_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured(
            "SLACKBOT_KEY_ENCRYPTION_KEY is not set; refusing to handle "
            "user API keys without encryption at rest."
        )
    return Fernet(key.encode())


def encrypt_api_key(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_api_key(token: str) -> str:
    """Raises cryptography.fernet.InvalidToken on a tampered or
    wrong-key ciphertext — callers treat that as "key needs re-registering"."""
    return _fernet().decrypt(token.encode()).decode()
