"""Warm Redis cache for the most popular tickers.

Queries LookupLog for the top N most-queried tickers in the last 7 days
and hits each API endpoint to populate the cache. Run on a schedule
(e.g. every 4 hours) so users never hit cold-cache latency.
"""
import logging
import time

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.test import RequestFactory
from django.utils import timezone

from quotes.models import LookupLog
from quotes.views import FundamentalsView, MultiplesHistoryView, PE10View

logger = logging.getLogger(__name__)

DELAY_BETWEEN_REQUESTS = 0.5  # seconds, to avoid hammering external APIs


class Command(BaseCommand):
    help = "Warm Redis cache for the most popular tickers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Number of top tickers to warm (default: 50)",
        )

    def handle(self, *args, **options):
        batch_limit = options["limit"]
        cutoff = timezone.now() - timezone.timedelta(days=7)

        top_tickers = (
            LookupLog.objects.filter(timestamp__gte=cutoff)
            .values("ticker")
            .annotate(count=Count("id"))
            .order_by("-count")[:batch_limit]
        )

        tickers = [entry["ticker"] for entry in top_tickers]
        self.stdout.write(f"Warming cache for {len(tickers)} tickers...")

        factory = RequestFactory()
        successes = 0
        failures = 0

        for ticker in tickers:
            request = factory.get(f"/api/quote/{ticker}/")
            request.session = type("Session", (), {"session_key": "warm_cache"})()

            for view_class, label in [
                (PE10View, "pe10"),
                (FundamentalsView, "fundamentals"),
                (MultiplesHistoryView, "multiples-history"),
            ]:
                try:
                    view = view_class.as_view()
                    response = view(request, ticker=ticker)
                    if response.status_code == 200:
                        successes += 1
                    else:
                        failures += 1
                        logger.warning(
                            "warm_cache: %s/%s returned %d",
                            ticker, label, response.status_code,
                        )
                except Exception:
                    failures += 1
                    logger.exception("warm_cache: %s/%s failed", ticker, label)

            time.sleep(DELAY_BETWEEN_REQUESTS)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {successes} cached, {failures} failed."
            )
        )
