"""Write freshly delivered ITR quarters straight from CVM's ENET system.

The archive path (``sync_cvm_filings``) can only ingest what CVM's batch
rebuild has republished, and that rebuild is roughly weekly. ENET is the
system companies file into, and its public search lists a filing within
minutes of delivery, so this command closes the gap between "the company
filed" and "the page shows it" from days to about an hour.

It is a second discovery mechanism, not a second set of rules. Whatever ENET
lists passes through the same gates as the archive path: BRAPI's rows are
never displaced (``is_writable``), the statements face the same account
mapping, label guards and balance validation, and the write is the shared
``write_quarter``. Once the weekly archive catches up it finds these rows
already written, with the same filing date, and leaves them alone.

The one extra step ENET needs: a package's cash flow is year-to-date only
and no earlier filings travel with it, so for second and third quarters the
previous quarter's package is downloaded too and the delta stays pure CVM
arithmetic.
"""
import logging
from datetime import date, timedelta

import requests
from django.utils import timezone

from config.monitored_command import MonitoredCommand
from quotes.cvm import (
    QUARTER_END_MONTH_DAYS,
    CvmParseError,
    previous_quarter_end,
)
from quotes.cvm_enet import (
    EnetFiling,
    download_filing_package,
    extract_quarter_statements_from_package,
    latest_filings,
    open_enet_session,
    search_itr_filings,
)
from quotes.cvm_writer import StatementRejected, is_writable, write_quarter
from quotes.models import Ticker

logger = logging.getLogger(__name__)

# ITR covers the first three quarters; Q4 is filed in the annual DFP.
FOURTH_QUARTER_MONTH = 12
ITR_QUARTER_MONTH_DAYS = {
    (month, day) for month, day in QUARTER_END_MONTH_DAYS
    if month != FOURTH_QUARTER_MONTH
}

# Wide enough that a filing survives a few days of failed runs, narrow enough
# that the search grid stays small. Every run re-derives its work list, so
# overlap between windows costs one is_writable query per filing, not a write.
DEFAULT_WINDOW_DAYS = 7

FIRST_QUARTER_MONTH = 3

REPORTED_ROWS = 40


class Command(MonitoredCommand):
    help = "Write ITR quarters straight from ENET, ahead of the weekly archive"
    sentry_monitor_slug = "sponda-sync-cvm-enet-filings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=DEFAULT_WINDOW_DAYS,
            help="How many days of ENET deliveries to consider",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report the work without downloading packages or writing",
        )

    def run(self, *args, **options):
        today = timezone.localdate()
        window_start = today - timedelta(days=options["days"])

        self._session = open_enet_session()
        self._earlier_filings_cache: dict[date, list[EnetFiling]] = {}

        filings = latest_filings(
            search_itr_filings(window_start, today, self._session),
        )
        pending = self._pending(filings)

        if not pending:
            self.stdout.write(
                f"ENET: 0 quarters to write from the last {options['days']} "
                f"day(s) · nothing downloaded."
            )
            return

        self.stdout.write(f"ENET: {len(pending)} quarter(s) to write")
        for symbols, filing in pending[:REPORTED_ROWS]:
            self.stdout.write(
                f"  {', '.join(symbols)} {filing.reference_date}"
            )

        if options["dry_run"]:
            self.stdout.write("dry run · nothing downloaded or written.")
            return

        self._ingest(pending)

    def _pending(self, filings: list[EnetFiling]) -> list[tuple[list[str], EnetFiling]]:
        """Every (tickers, filing) this run should write.

        Grouped by filing rather than ticker because ON and PN share one
        package; it is downloaded and parsed once and written to both.
        """
        tickers_by_code: dict[str, list[str]] = {}
        for ticker in Ticker.objects.exclude(cvm_code=None).exclude(cvm_code=""):
            tickers_by_code.setdefault(ticker.cvm_code, []).append(ticker.symbol)

        pending = []
        for filing in sorted(
            filings, key=lambda f: (f.reference_date, f.cvm_code),
        ):
            quarter = filing.reference_date
            if (quarter.month, quarter.day) not in ITR_QUARTER_MONTH_DAYS:
                continue
            symbols = [
                symbol for symbol in tickers_by_code.get(filing.cvm_code, [])
                if is_writable(symbol, quarter, filing.filed_at)
            ]
            if symbols:
                pending.append((symbols, filing))
        return pending

    def _ingest(self, pending: list[tuple[list[str], EnetFiling]]) -> None:
        written = failed = rejected = 0

        for symbols, filing in pending:
            statements = self._parse(filing)
            if statements is None:
                failed += 1
                continue
            if statements.is_empty:
                self.stdout.write(self.style.WARNING(
                    f"  {filing.company_name} {filing.reference_date}: no "
                    f"consolidated statements in the filing — skipped."
                ))
                continue
            for symbol in symbols:
                try:
                    write_quarter(symbol, statements, filed_at=filing.filed_at)
                    written += 1
                    self.stdout.write(f"  wrote {symbol} {filing.reference_date}")
                except StatementRejected as rejection:
                    rejected += 1
                    self.stderr.write(
                        f"  rejected {symbol} {filing.reference_date}: {rejection}"
                    )

        summary = f"wrote {written}, rejected {rejected}, {failed} failed"
        self.stdout.write(self.style.SUCCESS(f"ENET: {summary}."))

    def _parse(self, filing: EnetFiling):
        """One filing into statements, keeping any failure local to it."""
        try:
            package = download_filing_package(filing, self._session)
            return extract_quarter_statements_from_package(
                package,
                filing.cvm_code,
                filing.reference_date,
                previous_package_bytes=self._previous_package(filing),
            )
        except (CvmParseError, requests.RequestException) as error:
            logger.warning(
                "ENET %s %s could not be read: %s",
                filing.cvm_code, filing.reference_date, error,
            )
            self.stderr.write(
                f"  could not read {filing.company_name} "
                f"{filing.reference_date}: {error}"
            )
            return None

    def _previous_package(self, filing: EnetFiling) -> bytes | None:
        """The previous quarter's package, for the cash flow delta.

        First quarters need none: their year-to-date is the quarter. When the
        previous filing cannot be found the package is None and the cash flow
        fields stay unsaid rather than wrong.
        """
        if filing.reference_date.month == FIRST_QUARTER_MONTH:
            return None
        previous = self._find_previous_filing(filing)
        if previous is None:
            self.stderr.write(
                f"  no previous filing found for {filing.company_name} "
                f"{filing.reference_date}; the cash flow will be empty."
            )
            return None
        return download_filing_package(previous, self._session)

    def _find_previous_filing(self, filing: EnetFiling) -> EnetFiling | None:
        quarter = previous_quarter_end(filing.reference_date)
        if quarter not in self._earlier_filings_cache:
            self._earlier_filings_cache[quarter] = latest_filings(
                search_itr_filings(quarter, timezone.localdate(), self._session),
            )
        return next(
            (
                candidate for candidate in self._earlier_filings_cache[quarter]
                if candidate.cvm_code == filing.cvm_code
                and candidate.reference_date == quarter
            ),
            None,
        )
