"""Record which filing produced each CVM row already written.

66 quarters were written before ``filed_at`` existed. Two things follow from
leaving them blank: they are invisible to the filing-to-live metric, and
``is_writable`` would adopt a filing date for them on the next run — which
rewrites the row and moves ``fetched_at`` to that moment, making the metric
measure the backfill rather than when the data actually went live.

Setting the date here instead leaves ``fetched_at`` alone, so those rows report
the latency a reader of the site actually experienced.

The date comes from the filing index the poll recorded, joined through the
ticker's CVM code. Rows whose filing is not in the index keep a null date,
which is honest: nothing is known about when that one was received.
"""
from django.db import migrations

STATEMENT_MODELS = ("QuarterlyEarnings", "QuarterlyCashFlow", "BalanceSheet")
SOURCE_CVM = "cvm"


def backfill_filed_at(apps, schema_editor):
    Ticker = apps.get_model("quotes", "Ticker")
    CvmFiling = apps.get_model("quotes", "CvmFiling")

    cvm_code_by_ticker = dict(
        Ticker.objects.exclude(cvm_code=None).exclude(cvm_code="")
        .values_list("symbol", "cvm_code")
    )
    filed_at_by_filing = {}
    for cvm_code, reference_date, filed_at in (
        CvmFiling.objects.exclude(filed_at=None)
        .values_list("cvm_code", "reference_date", "filed_at")
    ):
        key = (cvm_code, reference_date)
        # A restatement carries a later date; the row was written from
        # whichever filing existed at the time, so take the earliest.
        if key not in filed_at_by_filing or filed_at < filed_at_by_filing[key]:
            filed_at_by_filing[key] = filed_at

    for model_name in STATEMENT_MODELS:
        model = apps.get_model("quotes", model_name)
        updated = []
        for row in model.objects.filter(source=SOURCE_CVM, filed_at=None).only(
            "ticker", "end_date", "filed_at",
        ):
            cvm_code = cvm_code_by_ticker.get(row.ticker)
            filed_at = filed_at_by_filing.get((cvm_code, row.end_date))
            if filed_at is None:
                continue
            row.filed_at = filed_at
            updated.append(row)
        # bulk_update leaves fetched_at untouched, which is the whole point.
        model.objects.bulk_update(updated, ["filed_at"], batch_size=500)


def forget_filed_at(apps, schema_editor):
    for model_name in STATEMENT_MODELS:
        model = apps.get_model("quotes", model_name)
        model.objects.filter(source=SOURCE_CVM).update(filed_at=None)


class Migration(migrations.Migration):

    dependencies = [("quotes", "0029_statement_filed_at")]

    operations = [migrations.RunPython(backfill_filed_at, forget_filed_at)]
