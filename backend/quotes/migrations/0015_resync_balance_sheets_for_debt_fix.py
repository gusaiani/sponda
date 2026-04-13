"""Force re-sync of all balance sheets after fixing the total_debt override.

Previously, `_patch_latest_total_debt_from_financial_data` would upgrade
total_debt whenever BRAPI's `financialData.totalDebt` was larger — which
inflated debt for tickers like VALE3 (203.6B vs the correct 103.5B) and
made their D/E ratio disagree with the same company's ADR (VALE via FMP).
Resetting fetched_at makes `_ensure_fresh_data` re-sync existing rows
with the corrected logic on next access.
"""

from datetime import datetime, timezone

from django.db import migrations


def force_resync_balance_sheets(apps, schema_editor):
    BalanceSheet = apps.get_model("quotes", "BalanceSheet")
    old_date = datetime(2000, 1, 1, tzinfo=timezone.utc)
    BalanceSheet.objects.update(fetched_at=old_date)


class Migration(migrations.Migration):

    dependencies = [
        ("quotes", "0014_add_trigram_and_composite_indexes"),
    ]

    operations = [
        migrations.RunPython(
            force_resync_balance_sheets,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
