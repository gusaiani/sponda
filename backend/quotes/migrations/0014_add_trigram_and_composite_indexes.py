from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quotes", "0013_add_market_cap"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Enable pg_trgm for fast LIKE / ILIKE searches
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="DROP EXTENSION IF EXISTS pg_trgm;",
        ),
        # Trigram GIN indexes for search autocomplete
        migrations.RunSQL(
            'CREATE INDEX "ticker_display_name_trgm" ON "quotes_ticker" USING gin ("display_name" gin_trgm_ops);',
            reverse_sql='DROP INDEX IF EXISTS "ticker_display_name_trgm";',
        ),
        migrations.RunSQL(
            'CREATE INDEX "ticker_symbol_trgm" ON "quotes_ticker" USING gin ("symbol" gin_trgm_ops);',
            reverse_sql='DROP INDEX IF EXISTS "ticker_symbol_trgm";',
        ),
        # Composite indexes for common query patterns
        migrations.AddIndex(
            model_name="companyanalysis",
            index=models.Index(
                fields=["ticker", "-generated_at"], name="quotes_comp_ticker_63350e_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="lookuplog",
            index=models.Index(
                fields=["user", "timestamp"], name="quotes_look_user_id_6169a1_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="lookuplog",
            index=models.Index(
                fields=["session_key", "timestamp"],
                name="quotes_look_session_a615d3_idx",
            ),
        ),
    ]
