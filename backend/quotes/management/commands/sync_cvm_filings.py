"""Write newly filed quarters from CVM into the statement tables.

The hourly poll (``snapshot_cvm_filings``) records what CVM has published and
the monthly pass (``map_tickers_to_cvm``) maps tickers onto CVM codes. This is
the step that turns those into rows, and it is the first place in the pipeline
where a parsing mistake reaches a company's page rather than a report.

The defaults are conservative for that reason:

* **BRAPI is never displaced.** Its rows are the ten-year baseline every P/E10
  denominator is built from, so CVM fills gaps rather than competing. A
  quarter already held by another source is left alone, including one whose
  provenance predates the ``source`` column · absence of a label is not
  permission to overwrite.
* **One company failing does not stop the rest.** During earnings season a
  single unparseable filing would otherwise cost the whole batch.
* **Nothing is downloaded when there is no work**, which is the normal state
  between seasons. The work list comes from rows the poll already recorded, so
  deciding there is nothing to do costs one query rather than 12 MB.
"""
import logging
from datetime import date

from django.utils import timezone

from config.monitored_command import MonitoredCommand
from quotes.cvm import (
    QUARTER_END_MONTH_DAYS,
    CvmParseError,
    download_itr_archive,
    extract_quarter_statements,
)
from quotes.cvm_writer import StatementRejected, is_writable, write_quarter
from quotes.models import CvmFiling, Ticker

logger = logging.getLogger(__name__)

# ITR covers the first three quarters; Q4 is filed in the annual DFP.
FOURTH_QUARTER_MONTH = 12
ITR_QUARTER_MONTH_DAYS = {
    (month, day) for month, day in QUARTER_END_MONTH_DAYS
    if month != FOURTH_QUARTER_MONTH
}

REPORTED_ROWS = 40


class Command(MonitoredCommand):
    help = "Write newly filed CVM quarters that no other source already holds"
    sentry_monitor_slug = "sponda-sync-cvm-filings"

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=None)
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report the work without downloading or writing",
        )

    def run(self, *args, **options):
        year = options["year"] or timezone.localdate().year
        pending = self._pending(year)

        if not pending:
            self.stdout.write(f"CVM {year}: 0 quarters to write · nothing downloaded.")
            return

        self.stdout.write(f"CVM {year}: {len(pending)} quarter(s) to write")
        for ticker, quarter, _, _ in pending[:REPORTED_ROWS]:
            self.stdout.write(f"  {ticker} {quarter}")

        if options["dry_run"]:
            self.stdout.write("dry run · nothing downloaded or written.")
            return

        self._ingest(year, pending)

    def _pending(self, year: int) -> list[tuple[str, date, str, date | None]]:
        """Every (ticker, quarter, cvm_code, filed_at) this run should write.

        Derived from what the poll already recorded, so an empty season is one
        query rather than a download.
        """
        tickers_by_code: dict[str, list[str]] = {}
        for ticker in Ticker.objects.exclude(cvm_code=None).exclude(cvm_code=""):
            tickers_by_code.setdefault(ticker.cvm_code, []).append(ticker.symbol)

        filings = CvmFiling.objects.filter(
            reference_date__year=year, cvm_code__in=tickers_by_code,
        ).order_by("cvm_code", "reference_date")

        seen, pending = set(), []
        for filing in filings:
            quarter = filing.reference_date
            if (quarter.month, quarter.day) not in ITR_QUARTER_MONTH_DAYS:
                continue
            for symbol in tickers_by_code[filing.cvm_code]:
                key = (symbol, quarter)
                if key in seen or not is_writable(symbol, quarter, filing.filed_at):
                    continue
                seen.add(key)
                pending.append((symbol, quarter, filing.cvm_code, filing.filed_at))
        return pending

    def _ingest(self, year: int, pending) -> None:
        archive = download_itr_archive(year)
        parsed: dict[tuple[str, date], object] = {}
        written = failed = rejected = 0

        for symbol, quarter, cvm_code, filed_at in pending:
            key = (cvm_code, quarter)
            if key not in parsed:
                parsed[key] = self._parse(archive, cvm_code, quarter)
            statements = parsed[key]
            if isinstance(statements, Exception):
                failed += 1
                continue
            try:
                write_quarter(symbol, statements, filed_at=filed_at)
                written += 1
            except StatementRejected as rejection:
                rejected += 1
                self.stderr.write(f"  rejected {symbol} {quarter}: {rejection}")

        summary = f"wrote {written}, rejected {rejected}, {failed} failed to parse"
        self.stdout.write(self.style.SUCCESS(f"CVM {year}: {summary}."))

    def _parse(self, archive: bytes, cvm_code: str, quarter: date):
        """Parse one company/quarter, keeping a failure local to that company."""
        try:
            return extract_quarter_statements(archive, cvm_code, quarter)
        except CvmParseError as error:
            logger.warning("CVM %s %s could not be read: %s", cvm_code, quarter, error)
            self.stderr.write(f"  could not read CVM {cvm_code} {quarter}: {error}")
            return error
