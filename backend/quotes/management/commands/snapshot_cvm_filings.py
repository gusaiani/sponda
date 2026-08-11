"""Record what the CVM has published, and when it published it.

Runs often and costs almost nothing. The archive is rebuilt in batch and
served with a Last-Modified header, so a HEAD request answers "has anything
changed" without transferring a byte of the 12 MB payload. Only when the
answer is yes does the command read the filing index, and even then it takes
a byte range covering the index alone rather than the whole archive.

The point is evidence. How quickly a filing reaches Sponda is bounded by two
things nobody has measured: how long CVM takes to publish what it receives,
and how often it republishes at all. This command accumulates the observations
that `report_cvm_lag` turns into those two numbers.
"""
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from config.monitored_command import MonitoredCommand
from quotes.cvm import (
    download_itr_index,
    fetch_itr_archive_state,
    parse_itr_index,
)
from quotes.models import CvmArchiveBuild, CvmFiling


class Command(MonitoredCommand):
    help = "Record the CVM ITR archive's publication state and filing index"
    sentry_monitor_slug = "sponda-snapshot-cvm-filings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year", type=int, default=None,
            help="Archive year to poll (defaults to the current year)",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="Read the index even when the archive has not been rebuilt",
        )

    def run(self, *args, **options):
        year = options["year"] or timezone.localdate().year
        state = fetch_itr_archive_state(year)

        if not options["force"] and self._already_recorded(year, state.last_modified):
            self.stdout.write(
                f"ITR {year} unchanged since {state.last_modified:%Y-%m-%d %H:%M} "
                f"· nothing downloaded."
            )
            return

        records = parse_itr_index(download_itr_index(year))
        build, added = self._record(year, state, records)

        built = f"built {build.last_modified:%Y-%m-%d %H:%M}" if build else "build time unknown"
        self.stdout.write(self.style.SUCCESS(
            f"ITR {year} {built} · {len(records)} filings listed · {added} new."
        ))

    def _already_recorded(self, year: int, last_modified: datetime | None) -> bool:
        if last_modified is None:
            return False
        return CvmArchiveBuild.objects.filter(
            year=year, last_modified=last_modified,
        ).exists()

    @transaction.atomic
    def _record(self, year, state, records) -> tuple[CvmArchiveBuild | None, int]:
        build = self._record_build(year, state, len(records))
        added = sum(self._record_filing(record, build) for record in records)
        return build, added

    def _record_build(self, year, state, filing_count) -> CvmArchiveBuild | None:
        """A build without a timestamp cannot be identified, so it is not stored.

        The filings it carried are still worth recording; they simply have no
        publication date to be measured against.
        """
        if state.last_modified is None:
            self.stderr.write(
                "The server reported no Last-Modified for the archive; "
                "filings will be recorded without a publication time."
            )
            return None

        build, _ = CvmArchiveBuild.objects.update_or_create(
            year=year, last_modified=state.last_modified,
            defaults={"etag": state.etag, "filing_count": filing_count},
        )
        return build

    def _record_filing(self, record, build) -> bool:
        """Store a filing once, keeping the build that first carried it.

        Later builds list the same filing again; overwriting `first_seen_in`
        would restate when it appeared and erase the very thing being measured.
        """
        _, created = CvmFiling.objects.get_or_create(
            cvm_code=record.cvm_code,
            reference_date=record.reference_date,
            version=record.version,
            defaults={
                "company_name": record.company_name,
                "cnpj": record.cnpj,
                "filed_at": record.filed_at,
                "document_id": record.document_id,
                "first_seen_in": build,
            },
        )
        return created
