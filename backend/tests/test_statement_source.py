"""Tests that every statement row records which provider wrote it.

Until now a row's origin was implicit: Brazilian tickers came from BRAPI, the
rest from FMP. Once CVM also writes, that inference breaks, and without
provenance a disagreement between sources cannot be audited and a bad parse
cannot be rolled back — the rows are indistinguishable from good ones.

The rule that matters: a writer stamps its own source. BRAPI overwrites CVM
rows when it catches up, which is intended, but it must also correct the
provenance. Updating the figures while leaving `source` saying "cvm" would
leave the audit trail asserting something false, which is worse than having
no audit trail at all.
"""
from datetime import date
from unittest.mock import patch

import pytest

from quotes.models import (
    SOURCE_BRAPI,
    SOURCE_CVM,
    SOURCE_FMP,
    BalanceSheet,
    QuarterlyCashFlow,
    QuarterlyEarnings,
)

TICKER = "GGBR3"
QUARTER = date(2026, 6, 30)


# --- The default ------------------------------------------------------------

@pytest.mark.django_db
def test_a_row_written_without_a_source_is_marked_unknown():
    """Historical rows predate provenance; they must not claim one."""
    earnings = QuarterlyEarnings.objects.create(
        ticker=TICKER, end_date=QUARTER, net_income=1,
    )

    assert earnings.source == ""


@pytest.mark.django_db
@pytest.mark.parametrize("model", [QuarterlyEarnings, QuarterlyCashFlow, BalanceSheet])
def test_every_statement_model_records_a_source(model):
    row = model.objects.create(ticker=TICKER, end_date=QUARTER, source=SOURCE_CVM)

    assert model.objects.get(pk=row.pk).source == SOURCE_CVM


# --- BRAPI stamps its own ---------------------------------------------------

@pytest.mark.django_db
def test_brapi_stamps_its_own_source_on_a_new_row():
    from quotes import brapi

    with patch.object(brapi, "fetch_income_statements", return_value=[
        {"endDate": "2026-06-30", "netIncome": 1_470_000_000, "totalRevenue": 1},
    ]):
        brapi.sync_earnings(TICKER)

    assert QuarterlyEarnings.objects.get(ticker=TICKER).source == SOURCE_BRAPI


@pytest.mark.django_db
def test_brapi_corrects_the_provenance_of_a_row_it_overwrites():
    """BRAPI winning on conflict is intended; leaving the row labelled 'cvm'
    afterwards would make the audit trail assert something false."""
    from quotes import brapi

    QuarterlyEarnings.objects.create(
        ticker=TICKER, end_date=QUARTER, net_income=1, source=SOURCE_CVM,
    )
    with patch.object(brapi, "fetch_income_statements", return_value=[
        {"endDate": "2026-06-30", "netIncome": 1_470_000_000, "totalRevenue": 1},
    ]):
        brapi.sync_earnings(TICKER)

    row = QuarterlyEarnings.objects.get(ticker=TICKER)
    assert row.net_income == 1_470_000_000
    assert row.source == SOURCE_BRAPI


@pytest.mark.django_db
def test_brapi_stamps_cash_flows_and_balance_sheets_too():
    from quotes import brapi

    with patch.object(brapi, "fetch_cash_flow_statements", return_value=[
        {"endDate": "2026-06-30", "operatingCashFlow": 10, "investmentCashFlow": -2},
    ]):
        brapi.sync_cash_flows(TICKER)
    with patch.object(brapi, "fetch_balance_sheets", return_value=[
        {"endDate": "2026-06-30", "totalAssets": 10, "totalLiab": 4,
         "totalStockholderEquity": 6},
    ]):
        brapi.sync_balance_sheets(TICKER)

    assert QuarterlyCashFlow.objects.get(ticker=TICKER).source == SOURCE_BRAPI
    assert BalanceSheet.objects.get(ticker=TICKER).source == SOURCE_BRAPI


# --- FMP stamps its own -----------------------------------------------------

@pytest.mark.django_db
def test_fmp_stamps_its_own_source():
    from quotes import fmp

    with patch.object(fmp, "fetch_income_statements", return_value=[
        {"date": "2026-06-30", "netIncome": 5, "revenue": 9,
         "reportedCurrency": "USD"},
    ]):
        fmp.sync_earnings("AAPL")

    assert QuarterlyEarnings.objects.get(ticker="AAPL").source == SOURCE_FMP


# --- The seeder stamps CVM --------------------------------------------------

@pytest.mark.django_db
def test_the_cvm_seeder_stamps_cvm():
    from tests.test_seed_quarter_from_cvm import gerdau_archive
    from django.core.management import call_command

    with patch(
        "quotes.management.commands.seed_quarter_from_cvm.download_itr_archive",
        return_value=gerdau_archive(),
    ):
        call_command(
            "seed_quarter_from_cvm", "--quarter", "2026-06-30", "--ticker", TICKER,
        )

    for model in (QuarterlyEarnings, QuarterlyCashFlow, BalanceSheet):
        assert model.objects.get(ticker=TICKER, end_date=QUARTER).source == SOURCE_CVM
