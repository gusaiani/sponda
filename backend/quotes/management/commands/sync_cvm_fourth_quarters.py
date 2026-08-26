"""Write the fourth quarter, which only the annual DFP can supply.

ITR covers Q1 to Q3. Nobody files Q4 as a standalone period, so it is derived
as the audited year minus the nine months already reported · see
``quotes.cvm_fourth_quarter`` for why the difference is charged to Q4 rather
than spread back over the earlier quarters.

Same posture as the quarterly sync. BRAPI is never displaced; one company
failing does not stop the rest; nothing is downloaded when there is no work.
What differs is that a company missing any of Q1 to Q3 cannot be done at all,
because there is no nine months to subtract.

Validated against 2025: of 279 companies where a Q4 could be derived, 277
(99.3%) matched the Q4 BRAPI eventually published, to within 1%. Three were
refused by the gate. The two that differed are the pair whose audited year
disagrees with its own quarters, which nothing available here can detect.
"""
import io
import logging
import zipfile
from datetime import date

from django.utils import timezone

from config.monitored_command import MonitoredCommand
from quotes.cvm import (
    CvmParseError,
    DfpArchiveNotPublished,
    download_dfp_archive,
    extract_annual_statements,
    parse_itr_index,
)
from quotes.cvm_fourth_quarter import FourthQuarterUnavailable, derive_fourth_quarter
from quotes.cvm_writer import StatementRejected, is_writable, write_quarter
from quotes.models import QuarterlyCashFlow, QuarterlyEarnings, Ticker

logger = logging.getLogger(__name__)

FIRST_THREE_QUARTER_ENDS = ((3, 31), (6, 30), (9, 30))
REPORTED_ROWS = 40

# The index shares the ITR's columns, so the same reader serves both.
DFP_INDEX_FILENAME_TEMPLATE = "dfp_cia_aberta_{year}.csv"


class Command(MonitoredCommand):
    help = "Derive and write Q4 from the annual DFP for companies lacking it"
    sentry_monitor_slug = "sponda-sync-cvm-fourth-quarters"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year", type=int, default=None,
            help="Reporting year (defaults to the year just ended)",
        )
        parser.add_argument("--dry-run", action="store_true")

    def run(self, *args, **options):
        year = options["year"] or timezone.localdate().year - 1
        pending = self._pending(year)

        if not pending:
            self.stdout.write(
                f"CVM {year}: no fourth quarter to write · nothing downloaded."
            )
            return

        self.stdout.write(f"CVM {year}: {len(pending)} fourth quarter(s) to write")
        for symbol, _, _ in pending[:REPORTED_ROWS]:
            self.stdout.write(f"  {symbol}")

        if options["dry_run"]:
            self.stdout.write("dry run · nothing downloaded or written.")
            return

        self._ingest(year, pending)

    def _pending(self, year: int):
        """Companies lacking Q4 but holding all three quarters it needs."""
        year_end = date(year, 12, 31)
        needed = {date(year, month, day) for month, day in FIRST_THREE_QUARTER_ENDS}

        pending = []
        for ticker in Ticker.objects.exclude(cvm_code=None).exclude(cvm_code=""):
            if not is_writable(ticker.symbol, year_end):
                continue
            reported = dict(
                QuarterlyEarnings.objects
                .filter(ticker=ticker.symbol, end_date__in=needed)
                .exclude(net_income=None)
                .values_list("end_date", "net_income")
            )
            if set(reported) != needed:
                continue
            pending.append((ticker.symbol, ticker.cvm_code, reported))
        return pending

    def _ingest(self, year: int, pending) -> None:
        try:
            archive = download_dfp_archive(year)
        except DfpArchiveNotPublished as absent:
            # Expected for part of every year: the job runs for a reporting
            # year before the CVM puts the archive online. Say so and stop,
            # rather than raising into Sentry as though something broke.
            self.stdout.write(f"CVM {year}: {absent} · nothing to ingest yet.")
            return
        filed = self._filing_dates(archive, year)
        annuals: dict[str, object] = {}
        written = refused = failed = 0

        for symbol, cvm_code, reported in pending:
            if cvm_code not in annuals:
                annuals[cvm_code] = self._annual(archive, cvm_code, year)
            annual = annuals[cvm_code]
            if annual is None:
                failed += 1
                continue

            try:
                fourth = derive_fourth_quarter(
                    annual, self._nine_months(symbol, year, reported),
                )
                write_quarter(symbol, fourth, filed_at=filed.get(cvm_code))
                written += 1
            except (FourthQuarterUnavailable, StatementRejected) as refusal:
                refused += 1
                self.stderr.write(f"  refused {symbol}: {refusal}")

        self.stdout.write(self.style.SUCCESS(
            f"CVM {year}: wrote {written}, refused {refused}, "
            f"{failed} without a usable annual."
        ))

    def _annual(self, archive: bytes, cvm_code: str, year: int):
        try:
            annual = extract_annual_statements(archive, cvm_code, year)
        except CvmParseError as error:
            logger.warning("DFP %s %s unreadable: %s", cvm_code, year, error)
            self.stderr.write(f"  could not read DFP {cvm_code}: {error}")
            return None
        return None if annual.is_empty else annual

    def _nine_months(self, symbol: str, year: int, reported: dict) -> dict:
        """The flows already reported for Q1 to Q3, summed.

        Earnings are known from the pending scan; cash flows are read here so
        a company with statements but no cash-flow rows still yields a quarter
        with its other figures rather than none at all.
        """
        needed = {date(year, month, day) for month, day in FIRST_THREE_QUARTER_ENDS}
        summed = {"net_income": sum(reported.values())}

        flows = list(
            QuarterlyCashFlow.objects
            .filter(ticker=symbol, end_date__in=needed)
            .values_list("operating_cash_flow", "investment_cash_flow")
        )
        if len(flows) == len(needed):
            for index, field in enumerate(
                ("operating_cash_flow", "investment_cash_flow")
            ):
                values = [row[index] for row in flows]
                summed[field] = None if any(v is None for v in values) else sum(values)
        return summed

    def _filing_dates(self, archive: bytes, year: int) -> dict[str, date]:
        """When CVM received each annual filing, from the archive's own index."""
        with zipfile.ZipFile(io.BytesIO(archive)) as opened:
            try:
                raw = opened.read(DFP_INDEX_FILENAME_TEMPLATE.format(year=year))
            except KeyError:
                return {}

        earliest: dict[str, date] = {}
        for record in parse_itr_index(raw):
            if record.filed_at is None:
                continue
            current = earliest.get(record.cvm_code)
            if current is None or record.filed_at < current:
                earliest[record.cvm_code] = record.filed_at
        return earliest
