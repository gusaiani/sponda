"""Tests for the scheduled ingestion of newly filed quarters from CVM.

The hourly poll already records what CVM has published (`CvmFiling`) and the
monthly pass maps tickers onto CVM codes. This command is the step that turns
those into statement rows, and it is the first place in the whole pipeline
where a parsing mistake reaches a page rather than a report.

So the defaults are conservative. BRAPI's rows are the ten-year baseline every
P/E10 denominator is built from, so CVM never displaces them · it fills gaps.
One company failing does not stop the rest. And nothing is downloaded at all
when there is no work, which is the normal state between earnings seasons.
"""
from datetime import date
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.cvm import CvmParseError
from quotes.models import (
    SOURCE_BRAPI,
    SOURCE_CVM,
    BalanceSheet,
    CvmArchiveBuild,
    CvmFiling,
    QuarterlyEarnings,
    Ticker,
)
from tests.test_seed_quarter_from_cvm import gerdau_archive

COMMAND = "sync_cvm_filings"
MODULE = "quotes.management.commands.sync_cvm_filings"

GERDAU_CODE = "3980"
QUARTER = date(2026, 6, 30)


@pytest.fixture
def gerdau(db):
    Ticker.objects.create(
        symbol="GGBR3", name="GERDAU S.A.", type="stock",
        market_cap=40_000_000_000, cvm_code=GERDAU_CODE,
    )
    return CvmFiling.objects.create(
        cvm_code=GERDAU_CODE, company_name="GERDAU S.A.", cnpj="33.611.500/0001-19",
        reference_date=QUARTER, filed_at=date(2026, 8, 4), version=1,
        document_id="160130",
    )


def run(**options):
    output = StringIO()
    with patch(f"{MODULE}.download_itr_archive", return_value=gerdau_archive()) as get:
        call_command(COMMAND, "--year", "2026", stdout=output, **options)
    return output.getvalue(), get


# --- Writing what BRAPI lacks -----------------------------------------------

@pytest.mark.django_db
def test_writes_a_quarter_no_other_source_holds(gerdau):
    run()

    earnings = QuarterlyEarnings.objects.get(ticker="GGBR3", end_date=QUARTER)
    assert earnings.source == SOURCE_CVM
    assert earnings.net_income is not None
    assert BalanceSheet.objects.filter(ticker="GGBR3", end_date=QUARTER).exists()


@pytest.mark.django_db
def test_one_cvm_code_writes_every_ticker_that_shares_it(gerdau):
    """ON and PN share one filing; both pages must show it."""
    Ticker.objects.create(
        symbol="GGBR4", name="GERDAU S.A.", type="stock",
        market_cap=40_000_000_000, cvm_code=GERDAU_CODE,
    )
    run()

    assert QuarterlyEarnings.objects.filter(end_date=QUARTER).count() == 2


# --- Not displacing BRAPI ---------------------------------------------------

@pytest.mark.django_db
def test_leaves_a_quarter_brapi_already_holds(gerdau):
    """BRAPI's series is the baseline; CVM fills gaps rather than competing."""
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=QUARTER, net_income=999, source=SOURCE_BRAPI,
    )
    run()

    row = QuarterlyEarnings.objects.get(ticker="GGBR3", end_date=QUARTER)
    assert row.net_income == 999
    assert row.source == SOURCE_BRAPI


@pytest.mark.django_db
def test_leaves_a_quarter_of_unrecorded_provenance_alone():
    """Rows predating provenance are BRAPI's; absence of a label is not
    permission to overwrite."""
    Ticker.objects.create(
        symbol="GGBR3", name="GERDAU S.A.", type="stock", cvm_code=GERDAU_CODE,
    )
    CvmFiling.objects.create(
        cvm_code=GERDAU_CODE, reference_date=QUARTER, version=1,
        filed_at=date(2026, 8, 4),
    )
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=QUARTER, net_income=42, source="",
    )
    run()

    assert QuarterlyEarnings.objects.get(ticker="GGBR3").net_income == 42


@pytest.mark.django_db
def test_leaves_its_own_row_alone_when_no_later_filing_exists(gerdau):
    """Holding a quarter is not a reason to rewrite it.

    Only a later filing is new information. Rewriting on every run re-parses
    the company and recomputes ten years of indicators to arrive back where it
    started · see the idempotency tests below.
    """
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=QUARTER, net_income=1,
        source=SOURCE_CVM, filed_at=date(2026, 8, 4),
    )
    _, download = run()

    assert QuarterlyEarnings.objects.get(ticker="GGBR3").net_income == 1
    download.assert_not_called()


# --- Scope ------------------------------------------------------------------

@pytest.mark.django_db
def test_ignores_a_filing_whose_company_maps_to_no_ticker():
    CvmFiling.objects.create(
        cvm_code="99999", reference_date=QUARTER, version=1,
        filed_at=date(2026, 8, 4),
    )
    _, download = run()

    assert not QuarterlyEarnings.objects.exists()
    download.assert_not_called()


@pytest.mark.django_db
def test_ignores_a_fourth_quarter_filing():
    """ITR covers Q1 to Q3; Q4 lives in the annual DFP."""
    Ticker.objects.create(symbol="GGBR3", type="stock", cvm_code=GERDAU_CODE)
    CvmFiling.objects.create(
        cvm_code=GERDAU_CODE, reference_date=date(2025, 12, 31), version=1,
        filed_at=date(2026, 3, 30),
    )
    _, download = run()

    download.assert_not_called()


@pytest.mark.django_db
def test_downloads_nothing_when_there_is_no_work(gerdau):
    """The normal state between earnings seasons."""
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=QUARTER, net_income=1, source=SOURCE_BRAPI,
    )
    _, download = run()

    download.assert_not_called()


@pytest.mark.django_db
def test_downloads_the_archive_once_for_many_filings(gerdau):
    Ticker.objects.create(symbol="GGBR4", type="stock", cvm_code=GERDAU_CODE)
    _, download = run()

    assert download.call_count == 1


# --- One failure does not stop the rest -------------------------------------

@pytest.mark.django_db
def test_a_company_that_fails_to_parse_does_not_stop_the_others(gerdau):
    Ticker.objects.create(symbol="AAAA3", type="stock", cvm_code="55555")
    CvmFiling.objects.create(
        cvm_code="55555", reference_date=QUARTER, version=1,
        filed_at=date(2026, 8, 4),
    )
    original = None

    def sometimes_fails(archive, cvm_code, quarter_end):
        if cvm_code == "55555":
            raise CvmParseError("no rows for this company")
        return original(archive, cvm_code, quarter_end)

    from quotes.management.commands import sync_cvm_filings as module
    original = module.extract_quarter_statements
    with patch.object(module, "extract_quarter_statements", sometimes_fails):
        output, _ = run()

    assert QuarterlyEarnings.objects.filter(ticker="GGBR3").exists()
    assert "1 failed" in output or "failed: 1" in output


@pytest.mark.django_db
def test_a_rejected_statement_does_not_stop_the_others(gerdau):
    """The continuity gate refusing one company is not a reason to abandon
    the season's remaining filings."""
    BalanceSheet.objects.create(
        ticker="GGBR3", end_date=date(2026, 3, 31), stockholders_equity=1,
    )
    output, _ = run()

    assert not QuarterlyEarnings.objects.filter(ticker="GGBR3").exists()
    assert "reject" in output.lower() or "refus" in output.lower()


# --- Dry run and reporting --------------------------------------------------

@pytest.mark.django_db
def test_dry_run_writes_nothing(gerdau):
    output, _ = run(dry_run=True)

    assert not QuarterlyEarnings.objects.exists()
    assert "GGBR3" in output


@pytest.mark.django_db
def test_reports_what_it_wrote(gerdau):
    output, _ = run()

    assert "GGBR3" in output
    assert "2026-06-30" in output


@pytest.mark.django_db
def test_a_build_with_no_new_filings_is_a_cheap_no_op():
    """Between seasons the poll records nothing new and this does nothing."""
    CvmArchiveBuild.objects.create(
        year=2026, last_modified="2026-08-09T10:39:17Z", filing_count=859,
    )
    output, download = run()

    download.assert_not_called()
    assert "0" in output


# --- Not rewriting what has not changed -------------------------------------

@pytest.mark.django_db
def test_a_second_run_rewrites_nothing(gerdau):
    """Rewriting an unchanged quarter is not harmless.

    Every rewrite re-parses the company, recomputes ten years of indicators and
    drops three caches. Four runs a day over a season is a great deal of work
    to arrive back where it started, and it churns the timestamp that answers
    "when did this go live".
    """
    run()
    output, download = run()

    download.assert_not_called()
    assert "0 quarter" in output


@pytest.mark.django_db
def test_the_filing_that_produced_a_row_is_recorded_on_it(gerdau):
    run()

    assert QuarterlyEarnings.objects.get(ticker="GGBR3").filed_at == date(2026, 8, 4)


@pytest.mark.django_db
def test_a_restatement_is_written_over_the_earlier_filing(gerdau):
    """A later DT_RECEB for the same quarter is new information."""
    run()
    CvmFiling.objects.create(
        cvm_code=GERDAU_CODE, reference_date=QUARTER, version=2,
        filed_at=date(2026, 8, 20), document_id="160999",
    )
    output, download = run()

    download.assert_called_once()
    assert QuarterlyEarnings.objects.get(ticker="GGBR3").filed_at == date(2026, 8, 20)
    assert "1 quarter" in output


@pytest.mark.django_db
def test_a_filing_with_no_received_date_does_not_cause_endless_rewrites(gerdau):
    """Without a date there is nothing to compare, so once written it rests."""
    CvmFiling.objects.filter(pk=gerdau.pk).update(filed_at=None)
    run()
    _, download = run()

    download.assert_not_called()


@pytest.mark.django_db
def test_a_row_with_no_filing_date_is_not_frozen_forever(gerdau):
    """Rows written before filed_at existed must still accept a restatement.

    is_writable compares filing dates, so a row without one would compare
    False against everything and never be updated again · the quarter would be
    stuck at whatever was first written, silently.
    """
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=QUARTER, net_income=1,
        source=SOURCE_CVM, filed_at=None,
    )
    run()

    row = QuarterlyEarnings.objects.get(ticker="GGBR3")
    assert row.net_income != 1
    assert row.filed_at == date(2026, 8, 4)
