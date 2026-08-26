"""Null out net-income zeros that sit beside real revenue.

The ingestion fix in ``quotes.statement_quality`` stops new ones arriving.
This repairs the rows already stored: when found, 2,801 quarters across 565
companies, including every quarter of BBAS3 from 2013 to 2019.

Every P/E window that covers a repaired quarter changes, so the derived
caches for the affected tickers are dropped. Their IndicatorSnapshot rows are
recomputed by the usual refresh jobs; run ``refresh_snapshot_fundamentals``
if you want it sooner.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from quotes.derived_data import invalidate_statement_caches
from quotes.models import QuarterlyEarnings


class Command(BaseCommand):
    help = "Null net_income where it is 0 alongside positive revenue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Stop after this many rows (for a cautious first pass).",
        )

    def handle(self, *args, **options):
        suspect = QuarterlyEarnings.objects.filter(
            net_income=0, revenue__gt=0,
        ).order_by("ticker", "end_date")

        limit = options["limit"]
        if limit:
            suspect = suspect[:limit]

        rows = list(suspect)
        tickers = sorted({row.ticker for row in rows})

        self.stdout.write(f"{len(rows)} quarters across {len(tickers)} companies")
        for ticker in tickers[:20]:
            count = sum(1 for row in rows if row.ticker == ticker)
            self.stdout.write(f"  {ticker}: {count}")
        if len(tickers) > 20:
            self.stdout.write(f"  ... and {len(tickers) - 20} more")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry run, nothing written"))
            return

        if not rows:
            self.stdout.write(self.style.SUCCESS("nothing to repair"))
            return

        QuarterlyEarnings.objects.filter(
            pk__in=[row.pk for row in rows],
        ).update(net_income=None)

        for ticker in tickers:
            invalidate_statement_caches(ticker)

        self.stdout.write(self.style.SUCCESS(
            f"nulled {len(rows)} quarters, invalidated caches for {len(tickers)} companies",
        ))
