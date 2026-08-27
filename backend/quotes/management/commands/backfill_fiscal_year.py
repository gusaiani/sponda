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

One call per company means 25,000 of them, so it runs in tranches:
``--limit`` sets the size and ``--after`` resumes past the last one done.
The cursor is not a convenience. A company that can never be labelled stays
in the queue, so without one it would head every later tranche and cost a
call each time; each run prints the cursor for the next.

The first production run is why the retry logic exists. Pushed at 2,000
companies with no gap between calls, FMP's circuit breaker opened, every
call for the next minute raised, and each one was recorded as a company
whose closing month could not be learned. 1,611 of 2,000 were "skipped",
American Airlines among them, and the cursor would have stepped past all of
them. A provider that cannot answer says nothing about a company, so
``ProviderUnavailable`` is now separate from a None closing month, a refusal
is waited out rather than counted, and a run that still cannot reach the
provider stops with the cursor at the last company it actually reached.

Grouping changes for every company it touches, so the derived caches are
dropped. ``IndicatorSnapshot`` rows are recomputed by the usual refresh
jobs; run ``refresh_snapshot_fundamentals`` if you want it sooner.
"""
from __future__ import annotations

import time
from datetime import date

from django.core.management.base import BaseCommand

from quotes.derived_data import invalidate_statement_caches
from quotes.fiscal_year import fiscal_year_from_year_end_month
from quotes.fmp import FMPError, fetch_latest_annual_income_statement
from quotes.models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings

STATEMENT_MODELS = (BalanceSheet, QuarterlyEarnings, QuarterlyCashFlow)
PROGRESS_EVERY_TICKERS = 200

# How long to wait out a provider that has started refusing, and how many
# times to try before giving the run back. FMP's breaker opens for 60
# seconds, so the last wait has to outlast a full cool-down.
RETRY_WAITS_SECONDS = (5, 20, 65)

# A small gap between calls, so a long run does not trip the breaker in the
# first place. Overridable with --pause.
DEFAULT_PAUSE_SECONDS = 0.2


class ProviderUnavailable(Exception):
    """The provider could not answer. Says nothing about the company.

    Kept distinct from a None closing month because conflating the two is
    what cost the first production run 1,611 companies: FMP's breaker
    opened, every call for the next minute raised, and each one was recorded
    as a company whose books apparently close in no month at all.
    """


def fetch_year_end_month(ticker: str, _get=None) -> int | None:
    """Which month `ticker` closes its books in.

    Returns None only when a healthy provider says the company has no annual
    statement, which is a fact about the company. Raises
    ``ProviderUnavailable`` when the provider itself could not answer, which
    is not.
    """
    fetch = _get or fetch_latest_annual_income_statement
    try:
        statement = fetch(ticker)
    except FMPError as error:
        raise ProviderUnavailable(str(error)) from error

    if statement is None:
        return None

    end_date_string = (statement.get("date") or "")[:10]
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
            help="Stop after this many companies, one FMP call each.",
        )
        parser.add_argument(
            "--pause", type=float, default=DEFAULT_PAUSE_SECONDS,
            help=(
                "Seconds to wait between companies. A long run with no gap "
                "trips the provider's circuit breaker."
            ),
        )
        parser.add_argument(
            "--after", default=None,
            help=(
                "Resume past this ticker. The queue is in ticker order, and a "
                "company whose closing month cannot be learned stays in it, so "
                "without a cursor it heads every later tranche and costs a call "
                "each time. Each run prints the cursor for the next one."
            ),
        )

    def handle(self, *args, **options):
        tickers, remaining = self._tickers_needing_a_label(
            options["ticker"], options["limit"], options["after"],
        )
        self.stdout.write(
            f"{len(tickers)} companies this run, {remaining} still queued after it"
        )

        labelled_rows = 0
        labelled_tickers = 0
        skipped: list[str] = []
        reached: list[str] = []
        gave_up_on: str | None = None

        for index, ticker in enumerate(tickers, start=1):
            time.sleep(options["pause"])
            try:
                year_end_month = self._year_end_month(ticker)
            except ProviderUnavailable as error:
                # Everything from here on is unreached, not unlabellable.
                # Stopping leaves it in the queue; skipping would step the
                # cursor past companies nobody ever asked about.
                gave_up_on = f"{ticker}: {error}"
                break

            reached.append(ticker)
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

        if gave_up_on:
            self.stdout.write(self.style.ERROR(
                f"stopped: provider unavailable at {gave_up_on}. "
                f"{len(tickers) - len(reached)} companies left unreached and "
                "still queued."
            ))

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
            self._report_cursor(reached, remaining + len(tickers) - len(reached))
            return

        self.stdout.write(self.style.SUCCESS(
            f"labelled {labelled_rows} rows across {labelled_tickers} companies"
        ))
        self._report_cursor(reached, remaining + len(tickers) - len(reached))

    def _report_cursor(self, reached: list[str], remaining: int) -> None:
        """Say how to pick up the next tranche, or that there is none.

        The cursor is the last company actually reached, never the last one
        the tranche intended to reach. A run cut short by the provider must
        leave everything it did not touch in the queue.
        """
        if remaining and reached:
            self.stdout.write(
                f"next tranche: --after {reached[-1]} ({remaining} companies left)"
            )

    def _year_end_month(self, ticker: str) -> int | None:
        """`fetch_year_end_month`, waiting out a provider that is refusing.

        A rate limit should cost a pause, not a company. Only when the
        provider is still refusing after the last wait does this give up,
        and then it gives up on the whole run rather than on this company.
        """
        for wait_seconds in RETRY_WAITS_SECONDS:
            try:
                return fetch_year_end_month(ticker)
            except ProviderUnavailable:
                time.sleep(wait_seconds)
        return fetch_year_end_month(ticker)

    def _tickers_needing_a_label(
        self, ticker: str | None, limit: int | None, after: str | None,
    ) -> tuple[list[str], int]:
        """The tranche to process, and how many companies remain behind it."""
        if ticker:
            return [ticker.upper()], 0

        needing: set[str] = set()
        for model in STATEMENT_MODELS:
            needing.update(
                model.objects
                .filter(fiscal_year__isnull=True)
                .values_list("ticker", flat=True)
                .distinct()
            )

        ordered = sorted(needing)
        if after:
            cursor = after.upper()
            ordered = [symbol for symbol in ordered if symbol > cursor]

        if limit is None:
            return ordered, 0
        return ordered[:limit], max(0, len(ordered) - limit)

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
