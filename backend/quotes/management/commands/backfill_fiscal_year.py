"""Label the statement rows stored before the fiscal year was being kept.

FMP reports a fiscal year on every statement; ``fmp.py`` now stores it, so
newly synced rows arrive labelled. The 3.3 million rows already in the
database do not, and until they are labelled every off-calendar filer's
history still groups by calendar year.

Re-pulling twenty years of quarterly statements for the whole universe would
be three endpoints times twenty-five thousand tickers to learn one number per
company. Instead this asks each company's annual statement which month it
closes its books in, once, and derives the label for every row it already
has: a period ending after the closing month belongs to the fiscal year that
ends in the following calendar year.

Rows the provider has already labelled are left alone, so this is safe to
re-run and safe to run alongside the ordinary sync. Companies whose closing
month cannot be learned are skipped and reported rather than guessed at:
the calendar-year fallback in ``fiscal_year_of`` is a known quantity.

Grouping changes for every company it touches, so the derived caches are
dropped. ``IndicatorSnapshot`` rows are recomputed by the usual refresh
jobs; run ``refresh_snapshot_fundamentals`` if you want it sooner.
"""
from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from quotes.derived_data import invalidate_statement_caches
from quotes.fiscal_year import fiscal_year_from_year_end_month
from quotes.fmp import FMPError, _get
from quotes.models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings

STATEMENT_MODELS = (BalanceSheet, QuarterlyEarnings, QuarterlyCashFlow)
PROGRESS_EVERY_TICKERS = 200


def fetch_year_end_month(ticker: str) -> int | None:
    """Which month `ticker` closes its books in, or None if unknown.

    One annual income statement is enough: its period end date is the
    company's year end. Isolated here so the backfill can be tested without
    reaching the network, and so a provider failure on one company is a skip
    rather than an aborted run.
    """
    try:
        statements = _get(
            "/stable/income-statement",
            params={"symbol": ticker, "period": "annual", "limit": 1},
        )
    except FMPError:
        return None

    if not isinstance(statements, list) or not statements:
        return None

    end_date_string = (statements[0].get("date") or "")[:10]
    if not end_date_string:
        return None
    return date.fromisoformat(end_date_string).month


class Command(BaseCommand):
    help = "Derive fiscal_year for statement rows the provider never labelled."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing.",
        )
        parser.add_argument(
            "--ticker", default=None,
            help="Backfill a single company rather than the whole universe.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Stop after this many companies (for a cautious first pass).",
        )

    def handle(self, *args, **options):
        tickers = self._tickers_needing_a_label(options["ticker"], options["limit"])
        self.stdout.write(f"{len(tickers)} companies with unlabelled rows")

        labelled_rows = 0
        labelled_tickers = 0
        skipped: list[str] = []

        for index, ticker in enumerate(tickers, start=1):
            year_end_month = fetch_year_end_month(ticker)
            if year_end_month is None:
                skipped.append(ticker)
                continue

            written = self._label(ticker, year_end_month, options["dry_run"])
            if written:
                labelled_rows += written
                labelled_tickers += 1
                if not options["dry_run"]:
                    invalidate_statement_caches(ticker)

            if index % PROGRESS_EVERY_TICKERS == 0:
                self.stdout.write(f"  {index}/{len(tickers)} companies")

        if skipped:
            self.stdout.write(self.style.WARNING(
                f"{len(skipped)} companies skipped, closing month unknown: "
                f"{', '.join(skipped[:10])}"
                f"{' ...' if len(skipped) > 10 else ''}"
            ))

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"dry run: {labelled_rows} rows across {labelled_tickers} "
                "companies would be labelled, nothing written"
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f"labelled {labelled_rows} rows across {labelled_tickers} companies"
        ))

    def _tickers_needing_a_label(self, ticker: str | None, limit: int | None) -> list[str]:
        if ticker:
            return [ticker.upper()]

        needing: set[str] = set()
        for model in STATEMENT_MODELS:
            needing.update(
                model.objects
                .filter(fiscal_year__isnull=True)
                .values_list("ticker", flat=True)
                .distinct()
            )

        ordered = sorted(needing)
        return ordered[:limit] if limit else ordered

    def _label(self, ticker: str, year_end_month: int, dry_run: bool) -> int:
        """Write the derived fiscal year onto one company's unlabelled rows."""
        written = 0
        for model in STATEMENT_MODELS:
            rows = list(
                model.objects.filter(ticker=ticker, fiscal_year__isnull=True)
            )
            if not rows:
                continue

            for row in rows:
                row.fiscal_year = fiscal_year_from_year_end_month(
                    row.end_date, year_end_month,
                )
            written += len(rows)

            if not dry_run:
                model.objects.bulk_update(rows, ["fiscal_year"], batch_size=1000)

        return written
