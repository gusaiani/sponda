"""Per-endpoint accounting of what we spend at each data provider.

FMP bills on a rolling 30-day data volume and only warns once usage passes
90% of the plan. That warning names no endpoint, so without local numbers
the next step is reading nginx logs and guessing. Every outbound call
records its endpoint, its response size and whether it was rejected, which
turns "what is eating the quota" into a query.

Accounting is best-effort by design: a failure here must never take down a
data fetch that is otherwise working.
"""
from __future__ import annotations

import logging

from django.db.models import F
from django.utils import timezone

from .models import ProviderUsageDay

logger = logging.getLogger(__name__)


def record_provider_call(provider: str, endpoint: str, response_bytes: int) -> None:
    """Add one call and `response_bytes` to today's row for this endpoint."""
    today = timezone.localdate()
    try:
        updated_rows = ProviderUsageDay.objects.filter(
            provider=provider, date=today, endpoint=endpoint
        ).update(
            call_count=F("call_count") + 1,
            bytes_downloaded=F("bytes_downloaded") + response_bytes,
        )
        if updated_rows:
            return

        ProviderUsageDay.objects.create(
            provider=provider,
            date=today,
            endpoint=endpoint,
            call_count=1,
            bytes_downloaded=response_bytes,
        )
    except Exception:
        # Two processes can race to create the same row, and the loser's
        # IntegrityError lands here along with every other storage failure.
        # Retrying the update covers the race; anything else is logged and
        # dropped rather than raised into the caller's data fetch.
        try:
            ProviderUsageDay.objects.filter(
                provider=provider, date=today, endpoint=endpoint
            ).update(
                call_count=F("call_count") + 1,
                bytes_downloaded=F("bytes_downloaded") + response_bytes,
            )
        except Exception:
            logger.warning(
                "Could not record %s usage for %s", provider, endpoint, exc_info=True
            )
