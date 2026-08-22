"""Slack request signature verification (slackbot/signing.py).

Every Slack-facing endpoint is unauthenticated HTTP from the open
internet; the v0 HMAC signature is the only thing separating Slack from
an attacker, so verification must be constant-time, timestamp-bounded
(replay protection), and fail closed when the secret is unconfigured.
"""
import hashlib
import hmac
import time

import pytest
from django.test import override_settings

from slackbot.signing import is_valid_slack_signature

SIGNING_SECRET = "8f742231b10e8888abcd99yyyzzz85a5"


def sign(body: bytes, timestamp: str, secret: str = SIGNING_SECRET) -> str:
    digest = hmac.new(
        secret.encode(), f"v0:{timestamp}:{body.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return f"v0={digest}"


class TestSlackSignature:
    @pytest.fixture(autouse=True)
    def _signing_secret(self, settings):
        settings.SLACK_SIGNING_SECRET = SIGNING_SECRET

    def test_valid_signature_accepted(self):
        body = b'{"type":"url_verification"}'
        timestamp = str(int(time.time()))
        assert is_valid_slack_signature(
            body=body, timestamp=timestamp, signature=sign(body, timestamp)
        )

    def test_wrong_signature_rejected(self):
        body = b'{"type":"url_verification"}'
        timestamp = str(int(time.time()))
        assert not is_valid_slack_signature(
            body=body, timestamp=timestamp, signature="v0=" + "0" * 64
        )

    def test_signature_over_different_body_rejected(self):
        timestamp = str(int(time.time()))
        signature = sign(b'{"a":1}', timestamp)
        assert not is_valid_slack_signature(
            body=b'{"a":2}', timestamp=timestamp, signature=signature
        )

    def test_stale_timestamp_rejected(self):
        # Replay protection: Slack recommends rejecting anything older
        # than five minutes.
        body = b"{}"
        stale = str(int(time.time()) - 600)
        assert not is_valid_slack_signature(
            body=body, timestamp=stale, signature=sign(body, stale)
        )

    def test_garbage_timestamp_rejected(self):
        body = b"{}"
        assert not is_valid_slack_signature(
            body=body, timestamp="not-a-number", signature=sign(body, "not-a-number")
        )


@override_settings(SLACK_SIGNING_SECRET="")
def test_unconfigured_secret_fails_closed():
    body = b"{}"
    timestamp = str(int(time.time()))
    assert not is_valid_slack_signature(
        body=body, timestamp=timestamp, signature=sign(body, timestamp, "")
    )
