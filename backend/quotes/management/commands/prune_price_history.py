"""Drop stored price and market cap history for companies nobody reads.

Each daily series back to 2000 is roughly 5,000 rows, and two are kept per
company · closes and reported market caps · so about 1.2 MB together.
:mod:`quotes.price_store` and :mod:`quotes.market_cap_store` fill lazily,
so the tables only hold companies someone has opened · but on a 49 GB
droplet, "someone opened it once, last year" is still worth reclaiming.
Dropping a series costs the next visitor one full refetch, which is
exactly what they would have paid before the stores existed.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from quotes.models import DailyClosePrice, DailyMarketCap, LookupLog

DEFAULT_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = (
        "Delete stored daily closes and market caps for companies not "
        "looked up recently."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help=(
                "Keep series for companies looked up within this many days "
                f"(default: {DEFAULT_RETENTION_DAYS})."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would be deleted without deleting it.",
        )

    def handle(self, *args, **options):
        retention_days = options["days"]
        dry_run = options["dry_run"]

        cutoff = timezone.now() - timedelta(days=retention_days)
        recently_read = set(
            LookupLog.objects.filter(timestamp__gte=cutoff)
            .values_list("ticker", flat=True)
            .distinct()
        )
        stored_tickers = set(
            DailyClosePrice.objects.values_list("ticker", flat=True).distinct()
        ) | set(DailyMarketCap.objects.values_list("ticker", flat=True).distinct())
        prunable = sorted(stored_tickers - recently_read)

        if not prunable:
            self.stdout.write("Nothing to prune.")
            return

        row_count = (
            DailyClosePrice.objects.filter(ticker__in=prunable).count()
            + DailyMarketCap.objects.filter(ticker__in=prunable).count()
        )
        if dry_run:
            self.stdout.write(
                f"Would delete {row_count} rows across {len(prunable)} companies: "
                f"{', '.join(prunable[:20])}"
                f"{'…' if len(prunable) > 20 else ''}"
            )
            return

        DailyClosePrice.objects.filter(ticker__in=prunable).delete()
        DailyMarketCap.objects.filter(ticker__in=prunable).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {row_count} rows across {len(prunable)} companies."
            )
        )
