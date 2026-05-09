"""Warm Redis cache for tickers users actually look at.

Sources tickers from three places, in order:

1. Every active user's favorites (``accounts.FavoriteCompany``).
2. Every active user's saved lists (``accounts.SavedList.tickers``).
3. The most-queried tickers in the last 7 days (``LookupLog``), as a
   fallback that picks up popular anonymous-session usage.

Tickers whose ``pe10:<T>`` cache entry is still warm are skipped, so
running the command frequently is cheap. The remainder are warmed in
parallel via ``ThreadPoolExecutor`` because nearly all of the per-ticker
wall-clock is I/O (DB + provider) — sequential was self-imposed
serialization that made the command useless once the wishlist grew past
50 tickers.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.models import Count
from django.utils import timezone

from accounts.models import FavoriteCompany, SavedList
from quotes.models import LookupLog
from quotes.views import _compute_quote_payload

logger = logging.getLogger(__name__)

DEFAULT_BATCH_LIMIT = 100
DEFAULT_THREAD_POOL_SIZE = 8
LOOKUP_LOG_LOOKBACK_DAYS = 7


class Command(BaseCommand):
    help = "Warm Redis cache for tickers users care about (favorites, lists, popular)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_BATCH_LIMIT,
            help=(
                "Maximum number of tickers to warm in this run "
                f"(default: {DEFAULT_BATCH_LIMIT})."
            ),
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=DEFAULT_THREAD_POOL_SIZE,
            help=f"Thread pool size (default: {DEFAULT_THREAD_POOL_SIZE}).",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        workers = options["workers"]

        candidates = self._gather_candidate_tickers(limit)
        cold = [t for t in candidates if cache.get(f"pe10:{t}") is None]

        self.stdout.write(
            f"Warming cache for {len(cold)} tickers "
            f"(skipped {len(candidates) - len(cold)} already warm)..."
        )
        successes, failures = self._warm_in_parallel(cold, workers)
        self.stdout.write(
            self.style.SUCCESS(f"Done. {successes} cached, {failures} failed.")
        )

    def _gather_candidate_tickers(self, limit: int) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        def _add(ticker: str) -> None:
            normalized = ticker.upper()
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)

        for symbol in FavoriteCompany.objects.values_list("ticker", flat=True):
            _add(symbol)

        for tickers_list in SavedList.objects.values_list("tickers", flat=True):
            if isinstance(tickers_list, list):
                for symbol in tickers_list:
                    if isinstance(symbol, str):
                        _add(symbol)

        cutoff = timezone.now() - timezone.timedelta(days=LOOKUP_LOG_LOOKBACK_DAYS)
        popular = (
            LookupLog.objects.filter(timestamp__gte=cutoff)
            .values("ticker")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        for row in popular:
            _add(row["ticker"])
            if len(ordered) >= limit:
                break

        return ordered[:limit]

    def _warm_in_parallel(
        self, tickers: list[str], workers: int
    ) -> tuple[int, int]:
        if not tickers:
            return 0, 0

        def _warm_one(ticker: str) -> None:
            try:
                _compute_quote_payload(ticker)
            finally:
                connections.close_all()

        successes = 0
        failures = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_warm_one, ticker): ticker
                for ticker in tickers
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    future.result()
                    successes += 1
                except Exception as error:  # noqa: BLE001 — per-ticker failures must not abort the whole run
                    failures += 1
                    logger.warning("warm_cache: %s failed: %s", ticker, error)
        return successes, failures
