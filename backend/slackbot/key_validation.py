"""Cheap liveness check for a pasted provider API key.

Runs inline in the modal submission handler, which Slack gives three
seconds — hence the tight timeout and the tri-state result:

  True  → the key authenticated against the provider's models endpoint
  False → the provider explicitly rejected it (401/403); show the modal error
  None  → indeterminate (timeout, outage); store the key anyway rather
          than locking users out because a provider blipped
"""
import logging

import requests

logger = logging.getLogger(__name__)

VALIDATION_TIMEOUT_SECONDS = 2.5

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
ANTHROPIC_API_VERSION = "2023-06-01"


def _validation_request(provider: str, api_key: str) -> requests.Response:
    if provider == "openai":
        return requests.get(
            OPENAI_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=VALIDATION_TIMEOUT_SECONDS,
        )
    if provider == "anthropic":
        return requests.get(
            ANTHROPIC_MODELS_URL,
            headers={"x-api-key": api_key, "anthropic-version": ANTHROPIC_API_VERSION},
            timeout=VALIDATION_TIMEOUT_SECONDS,
        )
    raise ValueError(f"Unknown provider: {provider}")


def validate_api_key(provider: str, api_key: str) -> bool | None:
    try:
        response = _validation_request(provider, api_key)
    except requests.RequestException as exc:
        logger.warning("Key validation indeterminate for %s: %s", provider, exc)
        return None
    if response.status_code in (401, 403):
        return False
    if response.ok:
        return True
    # 429s, 5xx: says nothing about the key itself.
    return None
