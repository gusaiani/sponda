"""Show what each provider endpoint has cost over a rolling window.

FMP's plan is a rolling 30-day data volume and their only warning arrives
by email at 90%, naming no endpoint. This command answers the question
that email raises: which endpoint is spending the quota, and did last
week's change actually move it.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from quotes.models import ProviderUsageDay

DEFAULT_WINDOW_DAYS = 30
BYTES_PER_GIGABYTE = 1024 ** 3


class Command(BaseCommand):
    help = "Report provider API calls and bytes per endpoint over a rolling window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_WINDOW_DAYS,
            help=f"Size of the rolling window (default: {DEFAULT_WINDOW_DAYS}).",
        )
        parser.add_argument(
            "--provider",
            type=str,
            default=None,
            help="Only report this provider (default: all).",
        )

    def handle(self, *args, **options):
        window_days = options["days"]
        provider_filter = options["provider"]

        window_start = timezone.localdate() - timedelta(days=window_days - 1)
        usage = ProviderUsageDay.objects.filter(date__gte=window_start)
        if provider_filter:
            usage = usage.filter(provider=provider_filter)

        rows = (
            usage.values("provider", "endpoint")
            .annotate(
                calls=Sum("call_count"),
                total_bytes=Sum("bytes_downloaded"),
            )
            .order_by("-total_bytes")
        )

        if not rows:
            self.stdout.write(f"No provider usage recorded since {window_start}.")
            return

        self.stdout.write(f"Provider usage since {window_start} ({window_days} days):")
        self.stdout.write("")
        self.stdout.write(
            f"{'PROVIDER':<10} {'ENDPOINT':<48} {'CALLS':>12} {'BYTES':>18} {'GB':>8}"
        )

        for row in rows:
            gigabytes = row["total_bytes"] / BYTES_PER_GIGABYTE
            self.stdout.write(
                f"{row['provider']:<10} {row['endpoint']:<48} "
                f"{row['calls']:>12,} {row['total_bytes']:>18,} {gigabytes:>8.2f}"
            )

        totals = usage.aggregate(
            calls=Sum("call_count"), total_bytes=Sum("bytes_downloaded")
        )
        total_gigabytes = totals["total_bytes"] / BYTES_PER_GIGABYTE
        self.stdout.write("")
        self.stdout.write(
            f"{'TOTAL':<10} {'':<48} {totals['calls']:>12,} "
            f"{totals['total_bytes']:>18,} {total_gigabytes:>8.2f}"
        )
