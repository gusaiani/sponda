"""Null balance-sheet debt that vanished without the liabilities to match.

The ingestion guard in ``quotes.statement_quality`` stops new ones arriving.
This repairs the rows already stored: when found, 9,716 quarters across
6,307 companies, of which 458 were a company's most recent quarter and so
were driving its live debt/equity, debt/earnings and debt/FCF ratios. Among
them Salesforce at $2.5bn against $71.2bn of liabilities, Honda and BMW at
zero, and Orange at $7.5bn the quarter after $42.7bn.

An understated debt figure is the dangerous direction of wrong: it ranks a
company as unlevered on exactly the screens someone uses to avoid leverage.
Nulling it drops those three indicators from the company's rating rather
than scoring them on a fiction; the rating still forms from whatever
remains, and the next successful sync restores the figure if the provider
has since corrected the filing.

Ratios derived from these rows are cached per ticker, so the derived caches
for every affected company are dropped. Their IndicatorSnapshot rows are
recomputed by the usual refresh jobs; run ``refresh_snapshot_fundamentals``
if you want it sooner.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.core.management.base import BaseCommand

from quotes.derived_data import invalidate_statement_caches
from quotes.models import BalanceSheet
from quotes.statement_quality import is_implausible_debt_collapse

TICKERS_LISTED_IN_THE_REPORT = 20


@dataclass(frozen=True)
class CollapsedQuarter:
    """One balance sheet to null, and whether it is the company's most recent.

    The latest quarter is the one feeding the live debt/equity, debt/EARN10
    and debt/FCF10 on the company page and in the screener, so the report
    counts those separately from the historical rows.
    """

    pk: int
    ticker: str
    end_date: date
    is_latest: bool


class Command(BaseCommand):
    help = "Null total_debt where it collapsed but total liabilities did not."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Stop after this many rows (for a cautious first pass).",
        )
        parser.add_argument(
            "--ticker", default=None,
            help="Repair a single company rather than the whole universe.",
        )

    def handle(self, *args, **options):
        suspect = self._find_collapsed_quarters(options["ticker"])

        limit = options["limit"]
        if limit:
            suspect = suspect[:limit]

        tickers = sorted({row.ticker for row in suspect})
        self._report(suspect, tickers)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry run, nothing written"))
            return

        if not suspect:
            self.stdout.write(self.style.SUCCESS("nothing to repair"))
            return

        BalanceSheet.objects.filter(
            pk__in=[row.pk for row in suspect],
        ).update(total_debt=None)

        for ticker in tickers:
            invalidate_statement_caches(ticker)

        self.stdout.write(self.style.SUCCESS(
            f"nulled {len(suspect)} quarters, "
            f"invalidated caches for {len(tickers)} companies",
        ))

    def _find_collapsed_quarters(self, ticker: str | None) -> list[CollapsedQuarter]:
        """Walk every company's quarters in order, applying the ingestion rule.

        Mirrors ``discard_implausible_debt_collapses``, but reports the rows
        instead of mutating them, and never lets a quarter it has already
        rejected become the baseline for the one that follows.

        Streams the columns it needs rather than whole model instances: the
        table is a million rows wide across the universe, and only five
        fields of each are read.
        """
        quarters = BalanceSheet.objects.all()
        if ticker:
            quarters = quarters.filter(ticker=ticker.upper())
        quarters = quarters.order_by("ticker", "end_date").values_list(
            "pk", "ticker", "end_date", "total_debt", "total_liabilities",
        )

        collapsed: list[CollapsedQuarter] = []
        for company_quarters in self._grouped_by_ticker(quarters.iterator()):
            collapsed.extend(self._collapsed_within(company_quarters))
        return collapsed

    @staticmethod
    def _grouped_by_ticker(quarters):
        """Yield one company's quarters at a time from a ticker-ordered stream."""
        current_ticker = None
        group: list[tuple] = []
        for quarter in quarters:
            if quarter[1] != current_ticker:
                if group:
                    yield group
                current_ticker = quarter[1]
                group = []
            group.append(quarter)
        if group:
            yield group

    @staticmethod
    def _collapsed_within(company_quarters: list[tuple]) -> list[CollapsedQuarter]:
        """Return the quarters of one company whose debt cannot be reconciled."""
        trusted_debt = None
        trusted_total_liabilities = None
        latest_end_date = company_quarters[-1][2]

        collapsed = []
        for pk, ticker, end_date, total_debt, total_liabilities in company_quarters:
            if is_implausible_debt_collapse(
                trusted_debt, trusted_total_liabilities,
                total_debt, total_liabilities,
            ):
                collapsed.append(CollapsedQuarter(
                    pk=pk, ticker=ticker, end_date=end_date,
                    is_latest=end_date == latest_end_date,
                ))
                continue
            if total_debt is not None:
                trusted_debt = total_debt
                trusted_total_liabilities = total_liabilities

        return collapsed

    def _report(self, suspect: list[CollapsedQuarter], tickers: list[str]) -> None:
        driving_live_ratios = sum(1 for row in suspect if row.is_latest)

        self.stdout.write(
            f"{len(suspect)} quarters across {len(tickers)} companies, "
            f"{driving_live_ratios} of them the company's latest quarter"
        )
        for ticker in tickers[:TICKERS_LISTED_IN_THE_REPORT]:
            count = sum(1 for row in suspect if row.ticker == ticker)
            self.stdout.write(f"  {ticker}: {count}")
        if len(tickers) > TICKERS_LISTED_IN_THE_REPORT:
            self.stdout.write(
                f"  ... and {len(tickers) - TICKERS_LISTED_IN_THE_REPORT} more"
            )
