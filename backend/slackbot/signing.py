"""Slack request signature verification (the v0 signing scheme).

Slack signs every request it sends with
HMAC-SHA256(signing_secret, "v0:{timestamp}:{raw_body}"). These endpoints
are unauthenticated HTTP from the open internet, so this signature is the
only line between Slack and an attacker: comparison is constant-time, the
timestamp is bounded to kill replays, and an unconfigured secret fails
closed.
"""
import hashlib
import hmac
import time

from django.conf import settings

SIGNATURE_VERSION = "v0"

# Slack's own recommendation: reject anything older than five minutes to
# close the replay window.
TIMESTAMP_TOLERANCE_SECONDS = 300


def is_valid_slack_signature(*, body: bytes, timestamp: str, signature: str) -> bool:
    signing_secret = settings.SLACK_SIGNING_SECRET
    if not signing_secret or not timestamp or not signature:
        return False

    try:
        request_time = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - request_time) > TIMESTAMP_TOLERANCE_SECONDS:
        return False

    base_string = f"{SIGNATURE_VERSION}:{timestamp}:".encode() + body
    expected = (
        SIGNATURE_VERSION
        + "="
        + hmac.new(signing_secret.encode(), base_string, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature)
