"""Tests for the poll that records what the CVM has published, and when.

The command exists to answer two questions with evidence rather than
assumption: how often the CVM rebuilds its archive, and how far behind the
filings that rebuild runs. Both bound how fresh Sponda can be, so both have to
be measured before anything is built on top of them.
"""
from datetime import date, datetime, timezone
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.cvm import ArchiveState, FilingRecord
from quotes.models import CvmArchiveBuild, CvmFiling

COMMAND = "snapshot_cvm_filings"
COMMAND_MODULE = "quotes.management.commands.snapshot_cvm_filings"

SUNDAY_BUILD = datetime(2026, 8, 9, 10, 39, 17, tzinfo=timezone.utc)
NEXT_SUNDAY_BUILD = datetime(2026, 8, 16, 10, 41, 3, tzinfo=timezone.utc)

GERDAU = FilingRecord(
    cvm_code="3980", company_name="GERDAU S.A.", cnpj="33.611.500/0001-19",
    reference_date=date(2026, 6, 30), filed_at=date(2026, 8, 4),
    version=1, document_id="160130",
)
PETROBRAS = FilingRecord(
    cvm_code="9512", company_name="PETROLEO BRASILEIRO S.A. PETROBRAS",
    cnpj="33.000.167/0001-01", reference_date=date(2026, 6, 30),
    filed_at=date(2026, 8, 7), version=1, document_id="160188",
)


def run(state=ArchiveState(last_modified=SUNDAY_BUILD, etag='"a"'),
        records=(GERDAU,), **options):
    """Invoke the command against a stubbed archive, returning its output."""
    output = StringIO()
    with patch(f"{COMMAND_MODULE}.fetch_itr_archive_state", return_value=state), \
         patch(f"{COMMAND_MODULE}.download_itr_index", return_value=b"") as download, \
         patch(f"{COMMAND_MODULE}.parse_itr_index", return_value=list(records)):
        call_command(COMMAND, "--year", "2026", stdout=output, **options)
    return output.getvalue(), download


# --- Recording a build ------------------------------------------------------

@pytest.mark.django_db
def test_records_the_published_build():
    run()

    build = CvmArchiveBuild.objects.get()
    assert build.year == 2026
    assert build.last_modified == SUNDAY_BUILD
    assert build.etag == '"a"'
    assert build.filing_count == 1


@pytest.mark.django_db
def test_records_every_filing_in_the_index():
    run(records=(GERDAU, PETROBRAS))

    assert CvmFiling.objects.count() == 2
    gerdau = CvmFiling.objects.get(cvm_code="3980")
    assert gerdau.company_name == "GERDAU S.A."
    assert gerdau.cnpj == "33.611.500/0001-19"
    assert gerdau.reference_date == date(2026, 6, 30)
    assert gerdau.filed_at == date(2026, 8, 4)
    assert gerdau.document_id == "160130"


@pytest.mark.django_db
def test_attributes_each_filing_to_the_build_that_first_carried_it():
    """The lag is measured against CVM's own timestamp, not our poll time,
    so it does not move when the polling interval changes."""
    run()

    assert CvmFiling.objects.get().first_seen_in.last_modified == SUNDAY_BUILD


# --- Not re-reading an unchanged archive ------------------------------------

@pytest.mark.django_db
def test_an_unchanged_archive_downloads_nothing():
    """Polling hourly is only affordable because this path costs one HEAD."""
    run()
    _, download = run()

    download.assert_not_called()
    assert CvmArchiveBuild.objects.count() == 1


@pytest.mark.django_db
def test_an_unchanged_archive_says_so():
    run()
    output, _ = run()

    assert "unchanged" in output.lower()


@pytest.mark.django_db
def test_force_re_reads_an_unchanged_archive():
    run()
    _, download = run(force=True)

    download.assert_called_once_with(2026)


# --- A new build ------------------------------------------------------------

@pytest.mark.django_db
def test_a_new_build_is_recorded_alongside_the_previous_one():
    run()
    run(state=ArchiveState(last_modified=NEXT_SUNDAY_BUILD, etag='"b"'))

    assert list(
        CvmArchiveBuild.objects.order_by("last_modified").values_list(
            "last_modified", flat=True,
        )
    ) == [SUNDAY_BUILD, NEXT_SUNDAY_BUILD]


@pytest.mark.django_db
def test_a_filing_keeps_the_build_that_first_carried_it():
    """Re-seeing a filing in a later build must not restate when it appeared."""
    run()
    run(state=ArchiveState(last_modified=NEXT_SUNDAY_BUILD, etag='"b"'),
        records=(GERDAU, PETROBRAS))

    assert CvmFiling.objects.get(cvm_code="3980").first_seen_in.last_modified == (
        SUNDAY_BUILD
    )
    assert CvmFiling.objects.get(cvm_code="9512").first_seen_in.last_modified == (
        NEXT_SUNDAY_BUILD
    )


@pytest.mark.django_db
def test_a_restatement_is_recorded_as_its_own_filing():
    """Version 2 has its own DT_RECEB and its own lag."""
    restated = FilingRecord(**{**GERDAU.__dict__, "version": 2,
                               "filed_at": date(2026, 8, 20)})
    run(records=(GERDAU, restated))

    assert CvmFiling.objects.filter(cvm_code="3980").count() == 2


@pytest.mark.django_db
def test_a_filing_with_no_received_date_is_still_recorded():
    undated = FilingRecord(**{**GERDAU.__dict__, "filed_at": None})
    run(records=(undated,))

    assert CvmFiling.objects.get().filed_at is None


# --- Degraded server behaviour ----------------------------------------------

@pytest.mark.django_db
def test_records_filings_even_when_the_server_reports_no_build_time():
    """Without Last-Modified there is no build to attribute to, but the
    filings themselves are still worth having."""
    run(state=ArchiveState(last_modified=None, etag=""))

    assert CvmArchiveBuild.objects.count() == 0
    assert CvmFiling.objects.get().first_seen_in is None
