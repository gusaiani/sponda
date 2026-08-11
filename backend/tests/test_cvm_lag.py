"""Tests for turning recorded builds and filings into a latency measurement.

Two numbers decide whether a CVM-primary ingestion path is worth building:
how long the CVM takes to publish a filing it has received, and how often it
republishes at all. The second dominates — a one-day publication lag is
irrelevant if the archive is only rebuilt weekly.
"""
from datetime import date, datetime, timedelta, timezone
from io import StringIO

import pytest
from django.core.management import call_command

from quotes.cvm_lag import build_freshness_report, build_lag_report
from quotes.models import CvmArchiveBuild, CvmFiling

OBSERVATION_START = datetime(2026, 8, 2, 10, 30, 0, tzinfo=timezone.utc)
FIRST_SUNDAY = datetime(2026, 8, 9, 10, 39, 17, tzinfo=timezone.utc)
SECOND_SUNDAY = datetime(2026, 8, 16, 10, 41, 3, tzinfo=timezone.utc)
THIRD_SUNDAY = datetime(2026, 8, 23, 10, 12, 0, tzinfo=timezone.utc)


def make_build(last_modified, year=2026, filing_count=0):
    return CvmArchiveBuild.objects.create(
        year=year, last_modified=last_modified, etag="", filing_count=filing_count,
    )


def make_filing(cvm_code, filed_at, build, reference_date=date(2026, 6, 30)):
    return CvmFiling.objects.create(
        cvm_code=cvm_code, company_name=f"COMPANHIA {cvm_code}", cnpj="",
        reference_date=reference_date, filed_at=filed_at, version=1,
        document_id=cvm_code, first_seen_in=build,
    )


# --- The per-filing lag -----------------------------------------------------

@pytest.mark.django_db
def test_lag_is_the_days_from_receipt_to_publication():
    build = make_build(FIRST_SUNDAY)  # 2026-08-09
    filing = make_filing("3980", date(2026, 8, 4), build)

    assert filing.publication_lag_days == 5


@pytest.mark.django_db
def test_lag_is_unknown_without_a_received_date():
    filing = make_filing("3980", None, make_build(FIRST_SUNDAY))

    assert filing.publication_lag_days is None


@pytest.mark.django_db
def test_lag_is_unknown_for_a_filing_seen_outside_a_recorded_build():
    filing = make_filing("3980", date(2026, 8, 4), None)

    assert filing.publication_lag_days is None


# --- Rebuild cadence --------------------------------------------------------

@pytest.mark.django_db
def test_rebuild_intervals_are_the_gaps_between_consecutive_builds():
    for stamp in (FIRST_SUNDAY, SECOND_SUNDAY, THIRD_SUNDAY):
        make_build(stamp)

    report = build_lag_report(2026)

    assert report.build_count == 3
    assert [round(gap, 1) for gap in report.rebuild_interval_days] == [7.0, 7.0]
    assert report.median_rebuild_interval_days == pytest.approx(7.0, abs=0.1)


@pytest.mark.django_db
def test_a_single_build_yields_no_interval():
    """One observation is not a cadence, and must not be reported as one."""
    make_build(FIRST_SUNDAY)

    report = build_lag_report(2026)

    assert report.rebuild_interval_days == []
    assert report.median_rebuild_interval_days is None


@pytest.mark.django_db
def test_builds_of_another_year_are_not_mixed_in():
    make_build(FIRST_SUNDAY)
    make_build(datetime(2025, 8, 10, 10, 0, tzinfo=timezone.utc), year=2025)

    assert build_lag_report(2026).build_count == 1


# --- Publication lag distribution -------------------------------------------

@pytest.mark.django_db
def test_report_summarizes_the_publication_lag():
    make_build(OBSERVATION_START)         # 2026-08-02
    first = make_build(FIRST_SUNDAY)      # 2026-08-09
    second = make_build(SECOND_SUNDAY)    # 2026-08-16
    make_filing("1", date(2026, 8, 7), first)    # 2 days
    make_filing("2", date(2026, 8, 5), first)    # 4 days
    make_filing("3", date(2026, 8, 14), second)  # 2 days
    make_filing("4", date(2026, 8, 10), second)  # 6 days

    report = build_lag_report(2026)

    assert sorted(report.publication_lag_days) == [2, 2, 4, 6]
    assert report.median_publication_lag_days == 3
    assert report.max_publication_lag_days == 6


@pytest.mark.django_db
def test_filings_without_a_measurable_lag_are_excluded_not_zeroed():
    make_build(OBSERVATION_START)
    build = make_build(FIRST_SUNDAY)
    make_filing("1", date(2026, 8, 7), build)
    make_filing("2", None, build)

    report = build_lag_report(2026)

    assert report.publication_lag_days == [2]
    assert report.measured_filing_count == 1
    assert report.filing_count == 2


@pytest.mark.django_db
def test_report_can_be_narrowed_to_one_reference_quarter():
    make_build(OBSERVATION_START)
    build = make_build(FIRST_SUNDAY)
    make_filing("1", date(2026, 8, 7), build, reference_date=date(2026, 6, 30))
    make_filing("2", date(2026, 8, 5), build, reference_date=date(2026, 3, 31))

    report = build_lag_report(2026, reference_date=date(2026, 6, 30))

    assert report.publication_lag_days == [2]


# --- Not mistaking a backfill for a measurement -----------------------------

@pytest.mark.django_db
def test_filings_received_before_observation_began_are_not_measured():
    """The first poll sweeps up the whole year, which is not a measurement.

    A filing received in April and first recorded by an August poll may have
    been published in April; nobody was watching. Counting the gap as lag
    would report months of latency that never happened.
    """
    build = make_build(FIRST_SUNDAY)  # the first poll we ever ran
    make_filing("old", date(2026, 4, 20), build)

    report = build_lag_report(2026)

    assert report.publication_lag_days == []
    assert report.backfilled_filing_count == 1
    assert report.median_publication_lag_days is None


@pytest.mark.django_db
def test_a_filing_received_after_observation_began_is_measured():
    """Its absence from the earlier build is the evidence that dates it."""
    make_build(OBSERVATION_START)     # 2026-08-02, did not list the filing
    later = make_build(FIRST_SUNDAY)  # 2026-08-09, does
    make_filing("new", date(2026, 8, 5), later)

    report = build_lag_report(2026)

    assert report.publication_lag_days == [4]
    assert report.backfilled_filing_count == 0


@pytest.mark.django_db
def test_a_filing_absent_from_an_observed_build_is_measured_however_old_it_is():
    """Receipt date does not decide measurability; the observation does.

    A filing received before polling began but missing from the first build we
    saw was still watched into existence. Excluding it on its age alone would
    drop precisely the slowest filings and flatter the CVM.
    """
    make_build(OBSERVATION_START)          # 2026-08-02, did not list it
    later = make_build(SECOND_SUNDAY)      # 2026-08-16, does
    make_filing("slow", date(2026, 7, 28), later)

    report = build_lag_report(2026)

    assert report.publication_lag_days == [19]
    assert report.backfilled_filing_count == 0


@pytest.mark.django_db
def test_the_observation_window_starts_at_the_earliest_recorded_build():
    make_build(OBSERVATION_START)
    make_build(FIRST_SUNDAY)

    assert build_lag_report(2026).observation_start == OBSERVATION_START


@pytest.mark.django_db
def test_an_empty_report_reports_nothing_rather_than_failing():
    report = build_lag_report(2026)

    assert report.build_count == 0
    assert report.median_publication_lag_days is None
    assert report.p90_publication_lag_days is None


@pytest.mark.django_db
def test_p90_reflects_the_tail_that_a_median_hides():
    """The slow filings are what a user notices, so they are reported too."""
    make_build(datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc))
    build = make_build(FIRST_SUNDAY)  # 2026-08-09
    for number in range(8):
        make_filing(str(number), date(2026, 8, 8), build)  # 1 day
    make_filing("slow", date(2026, 7, 25), build)          # 15 days
    make_filing("slowest", date(2026, 7, 20), build)       # 20 days

    report = build_lag_report(2026)

    assert report.median_publication_lag_days == 1
    assert report.p90_publication_lag_days == 15
    assert report.max_publication_lag_days == 20


# --- The report command -----------------------------------------------------

def report_output(**options):
    output = StringIO()
    call_command("report_cvm_lag", "--year", "2026", stdout=output, **options)
    return output.getvalue()


@pytest.mark.django_db
def test_command_reports_honestly_with_no_observations():
    assert "not enough observations yet" in report_output()


@pytest.mark.django_db
def test_command_does_not_present_a_backfill_as_a_measurement():
    build = make_build(FIRST_SUNDAY)
    make_filing("old", date(2026, 4, 20), build)

    output = report_output()

    assert "already published when polling began" in output
    assert "publication lag: not enough observations yet" in output


@pytest.mark.django_db
def test_command_reports_the_ceiling_without_double_counting_the_wait():
    """The measured lag already contains the wait for its own rebuild."""
    make_build(OBSERVATION_START)      # 2026-08-02
    later = make_build(FIRST_SUNDAY)   # 2026-08-09, one week on
    make_filing("1", date(2026, 8, 5), later)   # 4 days

    output = report_output()

    assert "worst observed filing to published: 4d" in output
    assert "waits up to 7d for the next one" in output
    assert "11d" not in output, "the rebuild wait must not be counted twice"


# --- Filing to live: the goal as a number -----------------------------------

def make_cvm_row(ticker, quarter, filed_at, written_on):
    from quotes.models import QuarterlyEarnings, SOURCE_CVM
    row = QuarterlyEarnings.objects.create(
        ticker=ticker, end_date=quarter, net_income=1,
        source=SOURCE_CVM, filed_at=filed_at,
    )
    # fetched_at is auto_now, so it has to be set past the ORM.
    QuarterlyEarnings.objects.filter(pk=row.pk).update(fetched_at=written_on)
    return row


@pytest.mark.django_db
def test_filing_to_live_measures_receipt_to_the_row_being_written():
    make_build(datetime(2026, 8, 1, 10, tzinfo=timezone.utc))
    make_cvm_row("GGBR3", date(2026, 6, 30), date(2026, 8, 4),
                 datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc))

    report = build_freshness_report()

    assert report.days_to_live == [7]
    assert report.median_days_to_live == 7


@pytest.mark.django_db
def test_filing_to_live_ignores_rows_from_other_providers():
    """BRAPI rows have no filing date and are not what this measures."""
    from quotes.models import QuarterlyEarnings, SOURCE_BRAPI

    QuarterlyEarnings.objects.create(
        ticker="VALE3", end_date=date(2026, 6, 30), net_income=1,
        source=SOURCE_BRAPI,
    )
    assert build_freshness_report().days_to_live == []


@pytest.mark.django_db
def test_filing_to_live_reports_the_tail_not_just_the_middle():
    make_build(datetime(2026, 7, 25, 10, tzinfo=timezone.utc))
    for index, day in enumerate((2, 3, 3, 4, 4, 5, 5, 6, 9, 14)):
        # Midday UTC: midnight would fall on the previous day in Sao Paulo,
        # which is the timezone a filing date is expressed in.
        make_cvm_row(f"AA{index:02d}3", date(2026, 6, 30),
                     date(2026, 8, 1),
                     datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
                     + timedelta(days=day))

    report = build_freshness_report()

    assert report.median_days_to_live == 4
    assert report.p90_days_to_live == 9
    assert report.max_days_to_live == 14


@pytest.mark.django_db
def test_filing_to_live_says_nothing_without_rows():
    report = build_freshness_report()

    assert report.row_count == 0
    assert report.median_days_to_live is None


@pytest.mark.django_db
def test_filing_to_live_excludes_quarters_filed_before_we_could_ingest_them():
    """Catching up is not a measurement of the pipeline.

    The first sync wrote quarters filed months earlier, because that is when
    the feature shipped. Counting those reported a p90 of 89 days and a max of
    99 — figures that describe when ingestion began, not how long it takes.
    Same distinction the publication-lag report already makes, arrived at from
    the other direction.
    """
    make_build(FIRST_SUNDAY)  # observation began 2026-08-09
    make_cvm_row("OLDD3", date(2026, 3, 31), date(2026, 5, 4),
                 datetime(2026, 8, 11, 12, tzinfo=timezone.utc))

    report = build_freshness_report()

    assert report.days_to_live == []
    assert report.caught_up_row_count == 1


@pytest.mark.django_db
def test_filing_to_live_counts_a_quarter_filed_while_we_were_watching():
    make_build(FIRST_SUNDAY)  # 2026-08-09
    make_cvm_row("NEWW3", date(2026, 6, 30), date(2026, 8, 12),
                 datetime(2026, 8, 15, 12, tzinfo=timezone.utc))

    report = build_freshness_report()

    assert report.days_to_live == [3]
    assert report.caught_up_row_count == 0


@pytest.mark.django_db
def test_filing_to_live_measures_nothing_before_observation_began():
    """Without a recorded build there is no window, so nothing is claimed."""
    make_cvm_row("ANYY3", date(2026, 6, 30), date(2026, 8, 4),
                 datetime(2026, 8, 11, 12, tzinfo=timezone.utc))

    assert build_freshness_report().days_to_live == []
