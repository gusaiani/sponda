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
def test_refreshes_a_quarter_it_wrote_itself(gerdau):
    """A restatement should reach the page; only other sources are protected."""
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=QUARTER, net_income=1, source=SOURCE_CVM,
    )
    run()

    assert QuarterlyEarnings.objects.get(ticker="GGBR3").net_income != 1


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
