"""Force re-sync of all balance sheets to pick up the totalCurrentAssets fix.

The BRAPI integration was previously looking for 'currentAssets' but BRAPI
actually returns the field as 'totalCurrentAssets'. This was fixed in brapi.py,
but existing BalanceSheet records still have current_assets=None from before
the fix. By resetting fetched_at to an old date, _ensure_fresh_data() will
re-sync them on next access.
"""

from datetime import datetime, timezone

from django.db import migrations


def force_resync_balance_sheets(apps, schema_editor):
    BalanceSheet = apps.get_model("quotes", "BalanceSheet")
    # Use .update() to bypass auto_now=True on fetched_at
    old_date = datetime(2000, 1, 1, tzinfo=timezone.utc)
    BalanceSheet.objects.update(fetched_at=old_date)


class Migration(migrations.Migration):

    dependencies = [
        ("quotes", "0008_add_revenue_dividends_current_assets"),
    ]

    operations = [
        migrations.RunPython(
            force_resync_balance_sheets,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
