"""Restate quarters BRAPI differenced against the quarter before them.

The ingestion guard in ``quotes.cumulative_quarters`` stops new ones
arriving. This repairs the rows already stored, which is every affected
Brazilian company's 2025 and 2026: BRAPI's pipeline broke during 2025, so
2024 and earlier came through correct and are left alone by the same
reconciliation that condemns the rest.

The defect is far from universal, which is the whole reason this cannot be a
blanket transform. Of the eight largest B3 companies on this path, five are
affected and three are perfectly correct. Petrobras understates 2025 revenue
by 49% and net income by 56%; Embraer, from the same provider and the same
quarters, is exact. So every company is asked its own audited annual, and a
year the annual does not condemn is not touched.

Running it twice is safe and does nothing the second time. A repaired year
sums to the annual as it stands, so the reconciliation then picks the
figures already stored. That is not a nicety: a second restatement would
accumulate the already-accumulated quarters and inflate the year.

Only BRAPI's own rows are restated. A year holding a quarter from anywhere
else is refused rather than mixed, because the accumulation depends on every
step in the run coming from the same pipeline.

One call per company, and it is the same call the ordinary sync makes: BRAPI
returns the quarterly and annual modules from a single request, so the
reconciliation costs no provider budget beyond the fetch itself.

Ratios derived from these rows are cached per ticker, so the derived caches
for every company it touches are dropped. IndicatorSnapshot rows are
recomputed by the usual refresh jobs; run ``refresh_indicator_snapshots`` if
you want it sooner, which makes no provider calls.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from django.core.management.base import BaseCommand

from quotes.brapi import BRAPIError, annual_income_by_year, fetch_income_statements
from quotes.cumulative_quarters import RESTATED_FIELDS, restate_quarterly_earnings
from quotes.derived_data import invalidate_statement_caches
from quotes.models import SOURCE_BRAPI, QuarterlyEarnings

PROGRESS_EVERY_TICKERS = 50
TICKERS_LISTED_IN_THE_REPORT = 20

# How long to wait out a provider that has started refusing, and how many
# times to try before giving the run back. BRAPI's breaker opens for 60
# seconds, so the last wait has to outlast a full cool-down.
RETRY_WAITS_SECONDS = (5, 20, 65)

# A small gap between calls, so a long run does not trip the breaker in the
# first place. Overridable with --pause.
DEFAULT_PAUSE_SECONDS = 0.2


class ProviderUnavailable(Exception):
    """BRAPI could not answer. Says nothing about the company.

    Kept distinct from a company with no annual filing, because conflating
    the two is what cost the fiscal-year backfill 1,611 companies: the
    breaker opened, every call for the next minute raised, and each one was
    recorded as a company that had simply nothing to report.
    """


@dataclass(frozen=True)
class Repair:
    """What one company's restatement changed."""

    ticker: str
    quarters: int


class Command(BaseCommand):
    help = "Restate BRAPI quarters that were differenced against their predecessor."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing.",
        )
        parser.add_argument(
            "--ticker", default=None,
            help="Repair a single company rather than the whole universe.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Stop after this many companies, one BRAPI call each.",
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
                "Resume past this ticker. A company the annual clears stays "
                "in the queue, so without a cursor it heads every later "
                "tranche and costs a call each time."
            ),
        )

    def handle(self, *args, **options):
        tickers, remaining = self._queue(
            options["ticker"], options["limit"], options["after"],
        )
        self.stdout.write(
            f"{len(tickers)} companies this run, {remaining} still queued after it"
        )

        repairs: list[Repair] = []
        reached: list[str] = []
        gave_up_on: str | None = None

        for index, ticker in enumerate(tickers, start=1):
            time.sleep(options["pause"])
            try:
                annual_by_year = self._annual_by_year(ticker)
            except ProviderUnavailable as error:
                # Everything from here on is unreached, not cleared. Stopping
                # leaves it queued; skipping would step the cursor past
                # companies nobody ever asked about.
                gave_up_on = f"{ticker}: {error}"
                break

            reached.append(ticker)
            repair = self._repair(ticker, annual_by_year, options["dry_run"])
            if repair is not None:
                repairs.append(repair)

            if index % PROGRESS_EVERY_TICKERS == 0:
                self.stdout.write(f"  {index}/{len(tickers)} companies")

        self._report(repairs, gave_up_on, len(tickers) - len(reached))

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry run, nothing written"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"restated {sum(r.quarters for r in repairs)} quarters across "
                f"{len(repairs)} companies"
            ))

        self._report_cursor(reached, remaining + len(tickers) - len(reached))

    def _queue(
        self, ticker: str | None, limit: int | None, after: str | None,
    ) -> tuple[list[str], int]:
        """The tranche to process, and how many companies remain behind it."""
        if ticker:
            return [ticker.upper()], 0

        # set(), not .distinct(): the model carries a Meta ordering, and
        # Django adds the ordering column to the SELECT behind a DISTINCT, so
        # the query would return one row per quarter and the queue would hold
        # a company once for every quarter it has. One BRAPI call each, so
        # that is the difference between 363 calls and several thousand.
        ordered = sorted(set(
            QuarterlyEarnings.objects
            .filter(source=SOURCE_BRAPI)
            .values_list("ticker", flat=True)
        ))
        if after:
            cursor = after.upper()
            ordered = [symbol for symbol in ordered if symbol > cursor]

        if limit is None:
            return ordered, 0
        return ordered[:limit], max(0, len(ordered) - limit)

    def _annual_by_year(self, ticker: str) -> dict:
        """The company's audited annual totals, waiting out a refusing provider.

        A rate limit should cost a pause, not a company. Only when BRAPI is
        still refusing after the last wait does this give up, and then it
        gives up on the whole run rather than on this company.
        """
        for wait_seconds in RETRY_WAITS_SECONDS:
            try:
                return self._fetch_annual_by_year(ticker)
            except ProviderUnavailable:
                time.sleep(wait_seconds)
        return self._fetch_annual_by_year(ticker)

    @staticmethod
    def _fetch_annual_by_year(ticker: str) -> dict:
        try:
            statements = fetch_income_statements(ticker)
        except BRAPIError as error:
            raise ProviderUnavailable(str(error)) from error
        return annual_income_by_year(statements.annual)

    def _repair(self, ticker: str, annual_by_year: dict, dry_run: bool) -> Repair | None:
        """Restate one company's stored quarters, writing only what changed.

        Restricted to BRAPI's own rows. A year holding a quarter from another
        source loses a step in the accumulation and is refused rather than
        mixed, which ``running_sum_restatement`` does on its own once the
        run is no longer contiguous.
        """
        quarters = list(
            QuarterlyEarnings.objects.filter(ticker=ticker, source=SOURCE_BRAPI)
        )
        if not quarters:
            return None

        before = {
            quarter.pk: tuple(getattr(quarter, field) for field in RESTATED_FIELDS)
            for quarter in quarters
        }
        restate_quarterly_earnings(quarters, annual_by_year)

        changed = [
            quarter for quarter in quarters
            if before[quarter.pk]
            != tuple(getattr(quarter, field) for field in RESTATED_FIELDS)
        ]
        if not changed:
            return None

        if not dry_run:
            QuarterlyEarnings.objects.bulk_update(
                changed, list(RESTATED_FIELDS), batch_size=1000,
            )
            invalidate_statement_caches(ticker)

        return Repair(ticker=ticker, quarters=len(changed))

    def _report(
        self, repairs: list[Repair], gave_up_on: str | None, unreached: int,
    ) -> None:
        for repair in repairs[:TICKERS_LISTED_IN_THE_REPORT]:
            self.stdout.write(f"  {repair.ticker}: {repair.quarters} quarters")
        if len(repairs) > TICKERS_LISTED_IN_THE_REPORT:
            self.stdout.write(
                f"  ... and {len(repairs) - TICKERS_LISTED_IN_THE_REPORT} more"
            )

        if gave_up_on:
            self.stdout.write(self.style.ERROR(
                f"stopped: provider unavailable at {gave_up_on}. "
                f"{unreached} companies left unreached and still queued."
            ))

    def _report_cursor(self, reached: list[str], remaining: int) -> None:
        """Say how to pick up the next tranche, or that there is none.

        The cursor is the last company actually reached, never the last one
        the tranche intended to reach.
        """
        if remaining and reached:
            self.stdout.write(
                f"next tranche: --after {reached[-1]} ({remaining} companies left)"
            )
