from django.db import migrations


class Migration(migrations.Migration):
    """Trigram index for the search endpoint's formal-name fallback, which
    runs an ILIKE '%q%' over Ticker.name."""

    dependencies = [
        ("quotes", "0031_indicatorsnapshot_pe1_indicatorsnapshot_pe11_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            'CREATE INDEX IF NOT EXISTS "ticker_name_trgm" ON "quotes_ticker" USING gin ("name" gin_trgm_ops);',
            reverse_sql='DROP INDEX IF EXISTS "ticker_name_trgm";',
        ),
    ]
