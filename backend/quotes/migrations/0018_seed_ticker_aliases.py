from django.db import migrations

from quotes.ticker_aliases import TICKER_ALIASES, serialize_aliases


def apply_known_aliases(apps, schema_editor):
    Ticker = apps.get_model("quotes", "Ticker")
    for symbol, aliases in TICKER_ALIASES.items():
        Ticker.objects.filter(symbol=symbol).update(aliases=serialize_aliases(aliases))


def clear_known_aliases(apps, schema_editor):
    Ticker = apps.get_model("quotes", "Ticker")
    Ticker.objects.filter(symbol__in=TICKER_ALIASES.keys()).update(aliases="")


class Migration(migrations.Migration):
    dependencies = [
        ("quotes", "0017_add_ticker_aliases"),
    ]

    operations = [
        migrations.RunPython(apply_known_aliases, clear_known_aliases),
    ]
