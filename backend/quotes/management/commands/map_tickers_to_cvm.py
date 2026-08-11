"""Map Brazilian tickers onto the CVM codes their filings are keyed by.

CVM identifies companies by CD_CVM and CNPJ and never by ticker, so nothing can
be read from CVM for a given company until this bridge exists.

Runs monthly and is idempotent. The monthly cadence is what surfaces a new
listing: an IPO arrives with no mapping, and without a recurring pass it would
simply never be ingested, which looks identical to the company having filed
nothing.

A mapping set by hand is never overwritten. A few tickers cannot be resolved
from published data at all, and an automated run that undid their corrections
every month would make them unfixable.
"""
from django.core.management.base import CommandError
from django.utils import timezone

from config.monitored_command import MonitoredCommand
from quotes.cvm_registry import (
    download_company_registry,
    load_security_listings,
    parse_company_registry,
)
from quotes.cvm_ticker_map import MATCH_MANUAL, TickerResolver, is_b3_ticker
from quotes.models import Ticker

# The FCA is an annual form, so one year lists only who filed in it. Four years
# back reaches companies that last filed some time ago while staying small
# (~350 KB per archive).
FCA_YEARS_BACK = 3

UNMAPPED_REPORTED = 40


class Command(MonitoredCommand):
    help = "Resolve Brazilian tickers to their CVM codes from published data"
    sentry_monitor_slug = "sponda-map-tickers-to-cvm"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year", type=int, default=None,
            help="Most recent FCA year to read (defaults to the current year)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing",
        )
        parser.add_argument(
            "--set", action="append", default=[], metavar="SYMBOL=CVM_CODE",
            dest="assignments",
            help=(
                "Record a mapping by hand, for the few tickers CVM's own data "
                "cannot resolve. Repeatable. Marked 'manual' and never "
                "overwritten by the automated pass."
            ),
        )

    def run(self, *args, **options):
        if options["assignments"]:
            self._assign_by_hand(options["assignments"])
            return

        latest_year = options["year"] or timezone.localdate().year
        years = list(range(latest_year - FCA_YEARS_BACK, latest_year + 1))

        resolver = TickerResolver(
            listings=load_security_listings(years),
            companies=parse_company_registry(download_company_registry()),
        )

        resolved, unmapped = self._apply(resolver, dry_run=options["dry_run"])
        self._report(resolved, unmapped, dry_run=options["dry_run"])

    def _assign_by_hand(self, assignments: list[str]) -> None:
        """Record mappings CVM's published data cannot produce.

        Only the registry is fetched, not the FCA archives: a correction should
        not wait on four downloads it makes no use of.

        The code is checked against the registry before anything is written. A
        hand-typed code that belongs to no company, or to the wrong one, is how
        a real company's page ends up showing another company's accounts · and
        unlike a missing mapping, that failure looks entirely plausible.
        """
        companies = {
            company.cvm_code: company
            for company in parse_company_registry(download_company_registry())
        }

        for assignment in assignments:
            symbol, _, cvm_code = assignment.partition("=")
            symbol, cvm_code = symbol.strip().upper(), cvm_code.strip().lstrip("0")
            if not symbol or not cvm_code:
                raise CommandError(
                    f"Expected SYMBOL=CVM_CODE, got {assignment!r}."
                )

            company = companies.get(cvm_code)
            if company is None:
                raise CommandError(
                    f"No registered company holds CVM code {cvm_code!r}; "
                    f"refusing to map {symbol} to it."
                )
            if not Ticker.objects.filter(symbol=symbol).exists():
                raise CommandError(f"{symbol} is not a known ticker.")

            Ticker.objects.filter(symbol=symbol).update(
                cvm_code=cvm_code, cnpj=company.cnpj, cvm_match_method=MATCH_MANUAL,
            )
            self.stdout.write(self.style.SUCCESS(
                f"{symbol} -> CVM {cvm_code} ({company.social_name}) · manual"
            ))

    def _candidates(self):
        """Brazilian tickers whose mapping is not hand-maintained."""
        return [
            ticker for ticker in Ticker.objects.exclude(
                cvm_match_method=MATCH_MANUAL,
            )
            if is_b3_ticker(ticker.symbol)
        ]

    def _apply(self, resolver, *, dry_run):
        resolved: dict[str, list[str]] = {}
        unmapped: list[Ticker] = []

        for ticker in self._candidates():
            match = resolver.resolve(ticker.symbol, company_name=ticker.name)
            if match is None:
                if not ticker.cvm_code:
                    unmapped.append(ticker)
                continue

            resolved.setdefault(match.method, []).append(ticker.symbol)
            if dry_run:
                continue
            Ticker.objects.filter(pk=ticker.pk).update(
                cvm_code=match.cvm_code,
                cnpj=match.cnpj,
                cvm_match_method=match.method,
            )
        return resolved, unmapped

    def _report(self, resolved, unmapped, *, dry_run):
        total = sum(len(symbols) for symbols in resolved.values())
        prefix = "would map" if dry_run else "mapped"
        self.stdout.write(f"{prefix} {total} tickers to a CVM code")
        for method, symbols in sorted(resolved.items()):
            self.stdout.write(f"  {method}: {len(symbols)}")

        if not unmapped:
            self.stdout.write(self.style.SUCCESS("  every Brazilian ticker is mapped"))
            return

        # Only a ticker with a market cap is actionable. BDRs (XPBR31, PRXB31
        # and a dozen others) match the B3 shape but are receipts over foreign
        # issuers that CVM never registers, so they can never be mapped and
        # would otherwise bury a genuinely new listing under permanent noise.
        actionable = [ticker for ticker in unmapped if ticker.market_cap]
        ignorable = len(unmapped) - len(actionable)

        self.stdout.write(
            f"  unmapped: {len(unmapped)} "
            f"({ignorable} without a market cap, not actionable)"
        )
        if not actionable:
            return

        # Largest first: a listed company missing is a live problem, a dormant
        # shell missing is housekeeping.
        by_weight = sorted(
            actionable, key=lambda ticker: ticker.market_cap, reverse=True,
        )
        for ticker in by_weight[:UNMAPPED_REPORTED]:
            self.stdout.write(
                f"    {ticker.symbol}  {ticker.market_cap:>18,}  {ticker.name}"
            )
        if len(by_weight) > UNMAPPED_REPORTED:
            self.stdout.write(
                f"    ... and {len(by_weight) - UNMAPPED_REPORTED} more"
            )
