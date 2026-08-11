"""Seed a single quarter of statements from CVM open data.

BRAPI is the sole provider of Brazilian quarterly statements, and it lags the
filing by one to three weeks. During earnings season that lag is exactly when
the Fundamentos tab matters most, so this command backfills a just-filed
quarter from the CVM's own ITR archive, which publishes within days.

The write is deliberately compatible with BRAPI rather than a replacement for
it: the account mapping reproduces BRAPI's values exactly (calibrated on
2026-03-31), and BRAPI's own sync overwrites these rows on ``(ticker,
end_date)`` once it catches up. Nothing here needs undoing later.

Usage::

    python manage.py seed_quarter_from_cvm --quarter 2026-06-30 \
        --ticker GGBR3 --ticker GGBR4 --ticker PETR3 --ticker PETR4

Add ``--dry-run`` to print the parsed figures without touching the database.
"""
import logging
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from quotes.cvm import CvmParseError, download_itr_archive, extract_quarter_statements
from quotes.derived_data import refresh_derived_data
from quotes.models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings

logger = logging.getLogger(__name__)

# Ticker to CVM registrant code. Share classes of one company (ON/PN) file a
# single set of statements, so they share a code. Extend as needed — this is a
# manual seeding tool, not the steady-state ingestion path.
TICKER_TO_CVM_CODE = {
    "GGBR3": "3980",   # Gerdau S.A.
    "GGBR4": "3980",   # Gerdau S.A.
    "GOAU3": "8656",   # Metalúrgica Gerdau S.A.
    "GOAU4": "8656",   # Metalúrgica Gerdau S.A.
    "PETR3": "9512",   # Petróleo Brasileiro S.A. (Petrobras)
    "PETR4": "9512",   # Petróleo Brasileiro S.A. (Petrobras)
}

# QuarterlyCashFlow.free_cash_flow stays unset: BRAPI never reports it, and
# fundamentals.py derives FCF as operating + investing for exactly that case.
# Writing a value here would make this quarter inconsistent with its siblings.
# Equity may legitimately swing on a large write-down, a rights issue or a
# spin-off, so the band is wide: it guards against reading the wrong line, not
# against unusual quarters. The bounds are exclusive, so a move of exactly an
# order of magnitude is refused rather than admitted.
EQUITY_CONTINUITY_MIN_RATIO = 0.1
EQUITY_CONTINUITY_MAX_RATIO = 10.0

FREE_CASH_FLOW_IS_DERIVED_DOWNSTREAM = None

# QuarterlyEarnings.eps is written by the providers but read nowhere, and a
# differenced year-to-date EPS would misstate the quarter's weighted share
# count. Left unset rather than approximated.
EPS_IS_UNUSED = None


class Command(BaseCommand):
    help = "Seed one quarter of statements for given tickers from CVM ITR open data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--quarter",
            required=True,
            help="Quarter end date, ISO format (e.g. 2026-06-30)",
        )
        parser.add_argument(
            "--ticker",
            action="append",
            dest="tickers",
            required=True,
            help="Ticker to seed; repeat the flag for several",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report without writing to the database",
        )

    def handle(self, *args, **options):
        quarter_end = self._parse_quarter(options["quarter"])
        tickers = [ticker.upper() for ticker in options["tickers"]]
        dry_run = options["dry_run"]

        unknown = [ticker for ticker in tickers if ticker not in TICKER_TO_CVM_CODE]
        if unknown:
            raise CommandError(
                f"No CVM code registered for {', '.join(unknown)}. "
                f"Add it to TICKER_TO_CVM_CODE."
            )

        self.stdout.write(f"Downloading CVM ITR archive for {quarter_end.year}...")
        archive_bytes = download_itr_archive(quarter_end.year)

        seeded_count = 0
        skipped_count = 0
        for ticker in tickers:
            statements = self._extract(archive_bytes, ticker, quarter_end)
            if statements.is_empty:
                self.stdout.write(
                    self.style.WARNING(
                        f"{ticker}: no {quarter_end} filing in the archive — skipped."
                    )
                )
                skipped_count += 1
                continue

            self._report(ticker, statements)
            if not dry_run:
                self._write(ticker, statements)
            seeded_count += 1

        verb = "Would seed" if dry_run else "Seeded"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {seeded_count} ticker(s) for {quarter_end}, "
                f"{skipped_count} skipped."
            )
        )

    def _parse_quarter(self, raw_quarter: str) -> date:
        try:
            return date.fromisoformat(raw_quarter)
        except ValueError as error:
            raise CommandError(f"--quarter must be an ISO date: {error}") from error

    def _extract(self, archive_bytes: bytes, ticker: str, quarter_end: date):
        try:
            return extract_quarter_statements(
                archive_bytes, TICKER_TO_CVM_CODE[ticker], quarter_end,
            )
        except CvmParseError as error:
            raise CommandError(str(error)) from error

    def _report(self, ticker: str, statements) -> None:
        self.stdout.write(
            f"  {ticker}: receita={_billions(statements.revenue)} "
            f"lucro={_billions(statements.net_income)} "
            f"FCO={_billions(statements.operating_cash_flow)} "
            f"investimento={_billions(statements.investment_cash_flow)} "
            f"PL={_billions(statements.stockholders_equity)}"
        )

    def _check_equity_continuity(self, ticker: str, statements) -> None:
        """Refuse equity that moved by an order of magnitude in one quarter.

        The parser's own gate already establishes that the figures are
        internally consistent, so what survives to here is a plausible wrong
        value · the kind that reaches a page and stays there. A company's
        equity does not move tenfold in three months; a parse that says it did
        has read the wrong line.
        """
        equity = statements.stockholders_equity
        if equity is None:
            return

        previous = (
            BalanceSheet.objects
            .filter(ticker=ticker, end_date__lt=statements.quarter_end)
            .exclude(stockholders_equity=None)
            .order_by("-end_date")
            .first()
        )
        if previous is None or not previous.stockholders_equity:
            return

        ratio = abs(equity) / abs(previous.stockholders_equity)
        if not EQUITY_CONTINUITY_MIN_RATIO < ratio < EQUITY_CONTINUITY_MAX_RATIO:
            raise CommandError(
                f"{ticker}: equity moved from {previous.stockholders_equity:,} at "
                f"{previous.end_date} to {equity:,} at {statements.quarter_end} "
                f"({ratio:.2f}x). Refusing to write · this is a parse fault, not "
                f"a corporate event."
            )

    def _write(self, ticker: str, statements) -> None:
        self._check_equity_continuity(ticker, statements)
        QuarterlyEarnings.objects.update_or_create(
            ticker=ticker,
            end_date=statements.quarter_end,
            defaults={
                "revenue": statements.revenue,
                "net_income": statements.net_income,
                "eps": EPS_IS_UNUSED,
            },
        )
        QuarterlyCashFlow.objects.update_or_create(
            ticker=ticker,
            end_date=statements.quarter_end,
            defaults={
                "operating_cash_flow": statements.operating_cash_flow,
                "investment_cash_flow": statements.investment_cash_flow,
                "free_cash_flow": FREE_CASH_FLOW_IS_DERIVED_DOWNSTREAM,
                "dividends_paid": statements.dividends_paid,
            },
        )
        BalanceSheet.objects.update_or_create(
            ticker=ticker,
            end_date=statements.quarter_end,
            defaults={
                "total_debt": statements.total_debt,
                "total_lease": statements.total_lease,
                "total_liabilities": statements.total_liabilities,
                "stockholders_equity": statements.stockholders_equity,
                "current_assets": statements.current_assets,
                "current_liabilities": statements.current_liabilities,
            },
        )
        refresh_derived_data(ticker)
        logger.info("Seeded %s %s from CVM ITR", ticker, statements.quarter_end)


def _billions(amount: int | None) -> str:
    if amount is None:
        return "n/a"
    return f"{amount / 1_000_000_000:,.2f}bn"
