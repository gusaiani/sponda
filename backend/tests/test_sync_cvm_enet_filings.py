"""Tests for the scheduled ingestion of freshly delivered ITRs from ENET.

The archive path (`sync_cvm_filings`) can only see what CVM's weekly batch
rebuild has published, so a quarter filed the day after a rebuild waits days.
This command asks ENET · the system companies actually file into · what was
delivered in the last few days and ingests it through the same gates: BRAPI
is never displaced, one company failing does not stop the rest, an unchanged
quarter is never rewritten.
"""
from datetime import date
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.cvm_enet import EnetFiling
from quotes.models import (
    SOURCE_BRAPI,
    SOURCE_CVM,
    BalanceSheet,
    QuarterlyCashFlow,
    QuarterlyEarnings,
    Ticker,
)
from tests.test_cvm_enet import (
    build_first_quarter_package,
    build_second_quarter_package,
)

COMMAND = "sync_cvm_enet_filings"
MODULE = "quotes.management.commands.sync_cvm_enet_filings"

ALLIED_CODE = "25330"
FIRST_QUARTER = date(2026, 3, 31)
SECOND_QUARTER = date(2026, 6, 30)


def _filing(reference_date=SECOND_QUARTER, *, filed_at=date(2026, 8, 12),
            version=1, cvm_code=ALLIED_CODE):
    return EnetFiling(
        cvm_code=cvm_code,
        company_name="ALLIED TECNOLOGIA S.A.",
        reference_date=reference_date,
        filed_at=filed_at,
        version=version,
        document_number="160482",
        protocol="025330ITR300620260100160482-70",
    )


@pytest.fixture
def allied(db):
    return Ticker.objects.create(
        symbol="ALLD3", name="ALLIED TECNOLOGIA S.A.", type="stock",
        market_cap=425_109_607, cvm_code=ALLIED_CODE,
    )


DEFAULT_PACKAGES = {
    SECOND_QUARTER: build_second_quarter_package,
    FIRST_QUARTER: build_first_quarter_package,
}


def run(recent=(_filing(),), earlier=(_filing(FIRST_QUARTER, filed_at=date(2026, 5, 7)),),
        packages=DEFAULT_PACKAGES, **options):
    """Run the command against a fake ENET.

    ``recent`` answers the delivery-window search the run starts with;
    ``earlier`` answers any search for a previous quarter's filing.
    """
    output, error = StringIO(), StringIO()

    def fake_search(start, end, session=None):
        if start in {filing.reference_date for filing in earlier}:
            return list(earlier)
        return list(recent)

    def fake_download(filing, session=None):
        return packages[filing.reference_date]()

    with patch(f"{MODULE}.open_enet_session"), \
            patch(f"{MODULE}.search_itr_filings", side_effect=fake_search) as search, \
            patch(f"{MODULE}.download_filing_package", side_effect=fake_download) as download:
        call_command(COMMAND, stdout=output, stderr=error, **options)
    return output.getvalue() + error.getvalue(), search, download


# --- Writing what BRAPI lacks -----------------------------------------------

@pytest.mark.django_db
def test_writes_a_quarter_no_other_source_holds(allied):
    run()

    earnings = QuarterlyEarnings.objects.get(ticker="ALLD3", end_date=SECOND_QUARTER)
    assert earnings.source == SOURCE_CVM
    assert earnings.revenue == 1_458_278_000
    assert BalanceSheet.objects.filter(ticker="ALLD3", end_date=SECOND_QUARTER).exists()


@pytest.mark.django_db
def test_the_cash_flow_is_differenced_against_the_previous_filing(allied):
    run()

    cash_flow = QuarterlyCashFlow.objects.get(ticker="ALLD3", end_date=SECOND_QUARTER)
    assert cash_flow.operating_cash_flow == 198_535_000 - 69_229_000


@pytest.mark.django_db
def test_one_cvm_code_writes_every_ticker_that_shares_it(allied):
    Ticker.objects.create(
        symbol="ALLD4", name="ALLIED TECNOLOGIA S.A.", type="stock",
        market_cap=425_109_607, cvm_code=ALLIED_CODE,
    )
    _, _, download = run()

    assert QuarterlyEarnings.objects.filter(end_date=SECOND_QUARTER).count() == 2
    assert download.call_count == 2  # the quarter and its predecessor, once each


@pytest.mark.django_db
def test_a_first_quarter_needs_no_previous_filing(allied):
    _, search, download = run(
        recent=(_filing(FIRST_QUARTER, filed_at=date(2026, 5, 7)),),
    )

    cash_flow = QuarterlyCashFlow.objects.get(ticker="ALLD3", end_date=FIRST_QUARTER)
    assert cash_flow.operating_cash_flow == 69_229_000
    assert search.call_count == 1
    assert download.call_count == 1


@pytest.mark.django_db
def test_a_missing_previous_filing_leaves_the_cash_flow_unsaid(allied):
    """None is honest; inventing a delta against nothing would not be."""
    output, _, _ = run(earlier=())

    cash_flow = QuarterlyCashFlow.objects.get(ticker="ALLD3", end_date=SECOND_QUARTER)
    assert cash_flow.operating_cash_flow is None
    assert QuarterlyEarnings.objects.get(ticker="ALLD3").revenue == 1_458_278_000
    assert "previous" in output.lower()


# --- Not displacing BRAPI ---------------------------------------------------

@pytest.mark.django_db
def test_leaves_a_quarter_brapi_already_holds(allied):
    QuarterlyEarnings.objects.create(
        ticker="ALLD3", end_date=SECOND_QUARTER, net_income=999,
        source=SOURCE_BRAPI,
    )
    _, _, download = run()

    row = QuarterlyEarnings.objects.get(ticker="ALLD3", end_date=SECOND_QUARTER)
    assert row.net_income == 999
    assert row.source == SOURCE_BRAPI
    download.assert_not_called()


@pytest.mark.django_db
def test_a_second_run_rewrites_nothing(allied):
    run()
    _, _, download = run()

    download.assert_not_called()


@pytest.mark.django_db
def test_a_restatement_is_written_over_the_earlier_filing(allied):
    run()
    restatement = _filing(version=2, filed_at=date(2026, 8, 20))
    run(recent=(restatement,))

    assert QuarterlyEarnings.objects.get(ticker="ALLD3").filed_at == date(2026, 8, 20)


# --- Scope ------------------------------------------------------------------

@pytest.mark.django_db
def test_ignores_a_filing_whose_company_maps_to_no_ticker(db):
    _, _, download = run()

    assert not QuarterlyEarnings.objects.exists()
    download.assert_not_called()


@pytest.mark.django_db
def test_a_filing_without_consolidated_statements_is_skipped(allied):
    packages = {
        SECOND_QUARTER: lambda: build_second_quarter_package(consolidated=False),
        FIRST_QUARTER: build_first_quarter_package,
    }
    output, _, _ = run(packages=packages)

    assert not QuarterlyEarnings.objects.exists()
    assert "skip" in output.lower()


# --- One failure does not stop the rest -------------------------------------

@pytest.mark.django_db
def test_a_company_that_fails_to_parse_does_not_stop_the_others(allied):
    Ticker.objects.create(symbol="BBBB3", type="stock", cvm_code="55555")
    broken = _filing(cvm_code="55555")

    def packages_with_a_broken_one(filing, session=None):
        if filing.cvm_code == "55555":
            return b"not a zip"
        return DEFAULT_PACKAGES[filing.reference_date]()

    output, error = StringIO(), StringIO()
    with patch(f"{MODULE}.open_enet_session"), \
            patch(f"{MODULE}.search_itr_filings") as search, \
            patch(f"{MODULE}.download_filing_package",
                  side_effect=packages_with_a_broken_one):
        search.side_effect = lambda start, end, session=None: (
            [_filing(FIRST_QUARTER, filed_at=date(2026, 5, 7))]
            if start == FIRST_QUARTER else [broken, _filing()]
        )
        call_command(COMMAND, stdout=output, stderr=error)
    combined = output.getvalue() + error.getvalue()

    assert QuarterlyEarnings.objects.filter(ticker="ALLD3").exists()
    assert not QuarterlyEarnings.objects.filter(ticker="BBBB3").exists()
    assert "failed" in combined


@pytest.mark.django_db
def test_a_rejected_statement_does_not_stop_the_others(allied):
    """The continuity gate refusing one company must stay local to it."""
    BalanceSheet.objects.create(
        ticker="ALLD3", end_date=FIRST_QUARTER, stockholders_equity=1,
    )
    output, _, _ = run()

    assert not QuarterlyEarnings.objects.filter(ticker="ALLD3").exists()
    assert "reject" in output.lower()


# --- Dry run and reporting --------------------------------------------------

@pytest.mark.django_db
def test_dry_run_writes_nothing_and_downloads_nothing(allied):
    output, _, download = run(dry_run=True)

    assert not QuarterlyEarnings.objects.exists()
    assert "ALLD3" in output
    download.assert_not_called()


@pytest.mark.django_db
def test_reports_what_it_wrote(allied):
    output, _, _ = run()

    assert "ALLD3" in output
    assert "2026-06-30" in output


@pytest.mark.django_db
def test_the_filing_date_is_recorded_on_the_row(allied):
    run()

    assert QuarterlyEarnings.objects.get(ticker="ALLD3").filed_at == date(2026, 8, 12)
