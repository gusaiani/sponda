"""Backfill country='BR' for every ticker matching the Brazilian symbol
pattern (letters followed by digits — PETR4, VALE3, SANB11, etc.).

Deterministic and free of any external API call, so it is safe to run
inside a deploy migration. Non-Brazilian tickers stay blank and get
backfilled out-of-band by ``manage.py sync_country``, which calls FMP's
profile endpoint per ticker.
"""
from django.db import migrations


def seed_brazilian_country(apps, schema_editor):
    Ticker = apps.get_model("quotes", "Ticker")
    Ticker.objects.filter(symbol__regex=r"^[A-Z]+\d+$").update(country="BR")


def clear_brazilian_country(apps, schema_editor):
    Ticker = apps.get_model("quotes", "Ticker")
    Ticker.objects.filter(symbol__regex=r"^[A-Z]+\d+$").update(country="")


class Migration(migrations.Migration):
    dependencies = [
        ("quotes", "0022_ticker_country"),
    ]

    operations = [
        migrations.RunPython(seed_brazilian_country, clear_brazilian_country),
    ]
