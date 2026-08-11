"""Report how long the CVM takes to publish the filings it receives.

Reads only what `snapshot_cvm_filings` has recorded. Every figure is an
observation; where there is not enough evidence the command says so rather
than printing a number that looks like a measurement.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from quotes.cvm_lag import build_lag_report

UNKNOWN = "not enough observations yet"


class Command(BaseCommand):
    help = "Summarize CVM publication lag and archive rebuild cadence"

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=None)
        parser.add_argument(
            "--reference-date", type=date.fromisoformat, default=None,
            help="Narrow to one reported quarter, e.g. 2026-06-30",
        )

    def handle(self, *args, **options):
        year = options["year"] or timezone.localdate().year
        report = build_lag_report(year, reference_date=options["reference_date"])

        self.stdout.write(f"CVM ITR {year}")
        self._write_cadence(report)
        self._write_lag(report)
        self._write_verdict(report)

    def _write_cadence(self, report):
        self.stdout.write(f"  archive builds observed: {report.build_count}")
        median = report.median_rebuild_interval_days
        if median is None:
            self.stdout.write(f"  rebuild interval: {UNKNOWN}")
            return
        self.stdout.write(
            f"  rebuild interval: median {median:.1f}d, "
            f"max {report.max_rebuild_interval_days:.1f}d"
        )

    def _write_lag(self, report):
        self.stdout.write(
            f"  filings recorded: {report.filing_count} "
            f"({report.measured_filing_count} with a measurable lag, "
            f"{report.backfilled_filing_count} already published when polling began)"
        )
        if report.median_publication_lag_days is None:
            self.stdout.write(f"  publication lag: {UNKNOWN}")
            return
        self.stdout.write(
            f"  publication lag: median {report.median_publication_lag_days}d, "
            f"p90 {report.p90_publication_lag_days}d, "
            f"max {report.max_publication_lag_days}d"
        )

    def _write_verdict(self, report):
        """What caps freshness, stated without double-counting the wait.

        The measured lag runs from receipt to the build that published the
        filing, so the wait for that rebuild is already inside it. Adding the
        rebuild interval on top would count the same wait twice. The interval
        is reported instead as what it is: the ceiling, since a filing landing
        just after a rebuild waits nearly a full one however often we poll.
        """
        if report.max_publication_lag_days is not None:
            self.stdout.write(
                f"  worst observed filing to published: "
                f"{report.max_publication_lag_days}d"
            )
        interval = report.median_rebuild_interval_days
        if interval is not None:
            self.stdout.write(
                f"  ceiling: a filing landing just after a rebuild waits up to "
                f"{interval:.0f}d for the next one"
            )
