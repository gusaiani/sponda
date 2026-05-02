"""One-shot backfill: stamp Ticker.reported_currency for every FMP ticker.

The cross-currency rollout populates Ticker.reported_currency as a side-
effect of fmp.sync_earnings, but tickers whose earnings were cached fresh
pre-rollout never run that path until either (a) a user visits the page or
(b) the weekly fundamentals refresh runs. Run this command once after
deploying the rollout to close the gap proactively across the entire
universe.

Brazilian tickers are skipped — sync_tickers eagerly stamps "BRL" for
those, and BRAPI's incomeStatementHistory does not expose a reported-
currency field anyway.
"""
from django.core.management.base import BaseCommand

from quotes.models import Ticker
from quotes.providers import ProviderError, is_brazilian_ticker, sync_earnings


class Command(BaseCommand):
    help = "Stamp Ticker.reported_currency for every FMP ticker missing it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Cap how many tickers to process this run (useful for staged rollouts).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="List the tickers that would be touched, but do not call sync_earnings.",
        )

    def handle(self, *args, **options):
        candidates = (
            Ticker.objects
            .filter(reported_currency="")
            .exclude(symbol__regex=r"\d+$")  # Brazilian tickers end in digits
            .order_by("symbol")
        )
        symbols = list(candidates.values_list("symbol", flat=True))
        if options["limit"]:
            symbols = symbols[: options["limit"]]

        self.stdout.write(f"Backfilling reported_currency for {len(symbols)} ticker(s)...")
        if options["dry_run"]:
            for symbol in symbols:
                self.stdout.write(f"  would sync: {symbol}")
            return

        success = 0
        failure = 0
        for index, symbol in enumerate(symbols, start=1):
            if is_brazilian_ticker(symbol):
                continue  # belt-and-suspenders; the regex already excluded these
            try:
                sync_earnings(symbol)
                success += 1
            except ProviderError as error:
                failure += 1
                self.stderr.write(self.style.WARNING(f"{symbol}: {error}"))
            if index % 100 == 0:
                self.stdout.write(f"  ...{index}/{len(symbols)} done ({success} ok, {failure} failed)")

        self.stdout.write(self.style.SUCCESS(
            f"Backfilled {success} ticker(s); {failure} failures."
        ))
