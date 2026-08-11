"""Tests the backfill that dates CVM rows written before filing dates existed.

Leaving them blank hides them from the filing-to-live metric, and letting the
sync adopt a date instead would rewrite the row and move `fetched_at` to that
moment — making the metric measure the backfill rather than when the data
actually went live.
"""
from datetime import date

import pytest

from quotes.models import SOURCE_BRAPI, SOURCE_CVM, CvmFiling, QuarterlyEarnings, Ticker

MIGRATION = "0030_backfill_statement_filed_at"


def run_backfill():
    """Apply just this migration's data function against the current schema.

    The schema editor is unused by the function · it only reads and writes
    rows · and instantiating a real one outside its context manager leaves
    connection state behind that other tests then trip over.
    """
    from importlib import import_module

    from django.apps.registry import apps as global_apps

    module = import_module(f"quotes.migrations.{MIGRATION}")
    module.backfill_filed_at(global_apps, None)


@pytest.fixture
def gerdau_filing(db):
    Ticker.objects.create(symbol="GGBR3", type="stock", cvm_code="3980")
    return CvmFiling.objects.create(
        cvm_code="3980", reference_date=date(2026, 6, 30), version=1,
        filed_at=date(2026, 8, 4), document_id="160130",
    )


@pytest.mark.django_db
def test_a_cvm_row_is_dated_from_the_filing_index(gerdau_filing):
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=date(2026, 6, 30), net_income=1, source=SOURCE_CVM,
    )

    run_backfill()

    assert QuarterlyEarnings.objects.get(ticker="GGBR3").filed_at == date(2026, 8, 4)


@pytest.mark.django_db
def test_the_backfill_does_not_move_when_the_row_went_live(gerdau_filing):
    """fetched_at is what the metric measures against; moving it would make
    the metric report this migration rather than the ingestion."""
    row = QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=date(2026, 6, 30), net_income=1, source=SOURCE_CVM,
    )
    written_at = QuarterlyEarnings.objects.get(pk=row.pk).fetched_at

    run_backfill()

    assert QuarterlyEarnings.objects.get(pk=row.pk).fetched_at == written_at


@pytest.mark.django_db
def test_rows_from_other_providers_are_left_alone(gerdau_filing):
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=date(2026, 6, 30), net_income=1,
        source=SOURCE_BRAPI,
    )

    run_backfill()

    assert QuarterlyEarnings.objects.get(ticker="GGBR3").filed_at is None


@pytest.mark.django_db
def test_a_row_whose_filing_is_not_indexed_keeps_an_unknown_date():
    """Nothing is known about when that one was received, and saying so is
    better than inventing a date."""
    Ticker.objects.create(symbol="ZZZZ3", type="stock", cvm_code="99999")
    QuarterlyEarnings.objects.create(
        ticker="ZZZZ3", end_date=date(2026, 6, 30), net_income=1, source=SOURCE_CVM,
    )

    run_backfill()

    assert QuarterlyEarnings.objects.get(ticker="ZZZZ3").filed_at is None


@pytest.mark.django_db
def test_a_restated_quarter_is_dated_from_the_filing_it_was_written_from():
    """The row was written when only the first filing existed."""
    Ticker.objects.create(symbol="GGBR3", type="stock", cvm_code="3980")
    for version, filed in ((1, date(2026, 8, 4)), (2, date(2026, 8, 20))):
        CvmFiling.objects.create(
            cvm_code="3980", reference_date=date(2026, 6, 30), version=version,
            filed_at=filed, document_id=str(version),
        )
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=date(2026, 6, 30), net_income=1, source=SOURCE_CVM,
    )

    run_backfill()

    assert QuarterlyEarnings.objects.get(ticker="GGBR3").filed_at == date(2026, 8, 4)
