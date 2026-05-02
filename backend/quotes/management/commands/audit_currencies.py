"""Audit currency coverage across the ticker universe.

Reports:
  * Distribution of (listing currency, reported currency) pairs.
  * Tickers whose reported currency has no FX rates yet (PE10/PFCF10 will
    return None until `sync_fx_rates` runs).
  * Tickers whose reported currency has no FRED CPI series mapped (PE10
    will fall back to nominal averages).

Use after the cross-currency rollout to spot gaps before users hit them.
"""
from collections import Counter

from django.core.management.base import BaseCommand

from quotes.fred import CURRENCY_TO_SERIES_ID
from quotes.models import CountryCPIIndex, FxRate, Ticker
from quotes.providers import is_brazilian_ticker


class Command(BaseCommand):
    help = "Print a coverage report for cross-currency indicator data."

    def handle(self, *args, **options):
        tickers = list(
            Ticker.objects.values_list("symbol", "reported_currency")
        )
        pair_counts: Counter[tuple[str, str]] = Counter()
        for symbol, reported in tickers:
            listing = "BRL" if is_brazilian_ticker(symbol) else "USD"
            pair_counts[(listing, reported or "?")] += 1

        self.stdout.write(self.style.MIGRATE_HEADING("Currency pairs (listing → reported):"))
        for (listing, reported), count in sorted(pair_counts.items(), key=lambda x: -x[1]):
            marker = " ⚠ MISMATCH" if listing != reported and reported not in ("", "?") else ""
            self.stdout.write(f"  {listing} → {reported:<5} {count:>6}{marker}")

        # FX coverage
        fx_currencies = set(
            FxRate.objects.values_list("quote_currency", flat=True).distinct()
        )
        reported_set = {r for _, r in tickers if r and r not in ("USD", "BRL")}
        fx_missing = sorted(reported_set - fx_currencies)
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("FX coverage:"))
        if fx_missing:
            self.stdout.write(self.style.WARNING(
                f"  Missing FX history for: {', '.join(fx_missing)}"
            ))
            self.stdout.write("  → Run `sync_fx_rates` to populate.")
        else:
            self.stdout.write(self.style.SUCCESS("  All reported currencies have FX history."))

        # CPI coverage (FRED mapping + actual rows)
        cpi_currencies_with_rows = set(
            CountryCPIIndex.objects.values_list("currency", flat=True).distinct()
        )
        cpi_unmapped = sorted(reported_set - set(CURRENCY_TO_SERIES_ID.keys()))
        cpi_unsynced = sorted(reported_set & set(CURRENCY_TO_SERIES_ID.keys()) - cpi_currencies_with_rows)
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("CPI coverage:"))
        if cpi_unmapped:
            self.stdout.write(self.style.WARNING(
                f"  Reporting currencies with no FRED series mapped: {', '.join(cpi_unmapped)}"
            ))
            self.stdout.write("  → Add them to CURRENCY_TO_SERIES_ID in quotes/fred.py.")
        if cpi_unsynced:
            self.stdout.write(self.style.WARNING(
                f"  Mapped but not yet synced: {', '.join(cpi_unsynced)}"
            ))
            self.stdout.write("  → Run `sync_country_cpi` to populate.")
        if not cpi_unmapped and not cpi_unsynced:
            self.stdout.write(self.style.SUCCESS("  All reporting currencies have CPI data."))
