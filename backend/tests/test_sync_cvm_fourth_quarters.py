"""Tests for ingesting Q4, which only the annual DFP can supply.

Same posture as the quarterly sync: BRAPI is never displaced, one company
failing does not stop the rest, and nothing is downloaded when there is no
work. What differs is that Q4 must be derived rather than read, so a company
missing any of Q1 to Q3 cannot be done at all.
"""
import io
import zipfile
from datetime import date
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from quotes.models import (
    SOURCE_BRAPI,
    SOURCE_CVM,
    BalanceSheet,
    QuarterlyEarnings,
    Ticker,
)
from tests.test_cvm import BALANCE_SHEET_COLUMNS, FLOW_COLUMNS, _csv_bytes
from tests.test_cvm_annual import balance, flow

COMMAND = "sync_cvm_fourth_quarters"
MODULE = "quotes.management.commands.sync_cvm_fourth_quarters"

GERDAU_CODE = "3980"
YEAR = 2025
YEAR_END = date(2025, 12, 31)

INDEX_COLUMNS = (
    "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC"
)


def dfp_archive(net_income=5_600_000, filed_at="2026-03-20"):
    index = "\n".join([
        INDEX_COLUMNS,
        f"33.611.500/0001-19;2025-12-31;1;GERDAU S.A.;003980;DFP;9;{filed_at};x",
    ]).encode("latin-1")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"dfp_cia_aberta_{YEAR}.csv", index)
        archive.writestr(f"dfp_cia_aberta_DRE_con_{YEAR}.csv", _csv_bytes(
            FLOW_COLUMNS, [
                flow("3.01", "Receita de Venda de Bens e/ou Serviços", 70_000_000),
                flow("3.11", "Lucro/Prejuízo Consolidado do Período", net_income),
            ]))
        archive.writestr(f"dfp_cia_aberta_BPA_con_{YEAR}.csv", _csv_bytes(
            BALANCE_SHEET_COLUMNS, [
                balance("1", "Ativo Total", 81_810_298),
                balance("1.01", "Ativo Circulante", 28_573_526),
            ]))
        archive.writestr(f"dfp_cia_aberta_BPP_con_{YEAR}.csv", _csv_bytes(
            BALANCE_SHEET_COLUMNS, [
                balance("2", "Passivo Total", 81_810_298),
                balance("2.01", "Passivo Circulante", 10_360_391),
                balance("2.02", "Passivo Não Circulante", 17_715_159),
                balance("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
            ]))
        archive.writestr(f"dfp_cia_aberta_DFC_MI_con_{YEAR}.csv", _csv_bytes(
            FLOW_COLUMNS, [
                flow("6.01", "Caixa Líquido Atividades Operacionais", 9_000_000),
            ]))
        archive.writestr(f"dfp_cia_aberta_DFC_MD_con_{YEAR}.csv",
                         _csv_bytes(FLOW_COLUMNS, []))
    return buffer.getvalue()


@pytest.fixture
def gerdau_with_three_quarters(db):
    Ticker.objects.create(
        symbol="GGBR3", name="GERDAU S.A.", type="stock",
        market_cap=40_000_000_000, cvm_code=GERDAU_CODE,
    )
    for month, day, income in ((3, 31, 1_300_000_000),
                               (6, 30, 1_400_000_000),
                               (9, 30, 1_400_000_000)):
        QuarterlyEarnings.objects.create(
            ticker="GGBR3", end_date=date(YEAR, month, day),
            net_income=income, source=SOURCE_BRAPI,
        )


def run(archive=None, **options):
    output = StringIO()
    with patch(f"{MODULE}.download_dfp_archive",
               return_value=archive if archive is not None else dfp_archive()) as get:
        call_command(COMMAND, "--year", str(YEAR), stdout=output, **options)
    return output.getvalue(), get


# --- Deriving and writing ---------------------------------------------------

@pytest.mark.django_db
def test_writes_the_fourth_quarter_as_the_year_less_the_nine_months(
    gerdau_with_three_quarters,
):
    run()

    fourth = QuarterlyEarnings.objects.get(ticker="GGBR3", end_date=YEAR_END)
    assert fourth.net_income == 5_600_000_000 - 4_100_000_000
    assert fourth.source == SOURCE_CVM


@pytest.mark.django_db
def test_the_year_end_balance_sheet_is_taken_whole(gerdau_with_three_quarters):
    run()

    sheet = BalanceSheet.objects.get(ticker="GGBR3", end_date=YEAR_END)
    assert sheet.stockholders_equity == 53_734_748_000


@pytest.mark.django_db
def test_the_filing_date_comes_from_the_annual_document(
    gerdau_with_three_quarters,
):
    """Without it the row is frozen against a restated annual."""
    run()

    assert QuarterlyEarnings.objects.get(
        ticker="GGBR3", end_date=YEAR_END,
    ).filed_at == date(2026, 3, 20)


# --- What it will not do ----------------------------------------------------

@pytest.mark.django_db
def test_leaves_a_fourth_quarter_brapi_already_holds(gerdau_with_three_quarters):
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=YEAR_END, net_income=777, source=SOURCE_BRAPI,
    )
    _, download = run()

    assert QuarterlyEarnings.objects.get(
        ticker="GGBR3", end_date=YEAR_END,
    ).net_income == 777
    download.assert_not_called()


@pytest.mark.django_db
def test_skips_a_company_missing_one_of_the_first_three_quarters(db):
    """Q4 is the year less the nine months; two quarters is not nine months."""
    Ticker.objects.create(symbol="GGBR3", type="stock", cvm_code=GERDAU_CODE)
    for month, day in ((3, 31), (6, 30)):
        QuarterlyEarnings.objects.create(
            ticker="GGBR3", end_date=date(YEAR, month, day),
            net_income=1_000, source=SOURCE_BRAPI,
        )
    _, download = run()

    assert not QuarterlyEarnings.objects.filter(end_date=YEAR_END).exists()
    download.assert_not_called()


@pytest.mark.django_db
def test_downloads_nothing_when_no_company_needs_a_fourth_quarter(db):
    _, download = run()

    download.assert_not_called()


@pytest.mark.django_db
def test_a_year_reporting_nothing_is_refused_not_absorbed(
    gerdau_with_three_quarters,
):
    """A zero annual against real quarters would derive a huge false loss."""
    output, _ = run(archive=dfp_archive(net_income=0))

    assert not QuarterlyEarnings.objects.filter(end_date=YEAR_END).exists()
    assert "refus" in output.lower() or "reject" in output.lower()


@pytest.mark.django_db
def test_dry_run_writes_nothing(gerdau_with_three_quarters):
    output, _ = run(dry_run=True)

    assert not QuarterlyEarnings.objects.filter(end_date=YEAR_END).exists()
    assert "GGBR3" in output
