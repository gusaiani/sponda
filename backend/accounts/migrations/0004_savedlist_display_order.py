from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_pageview"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedcomparison",
            name="display_order",
            field=models.IntegerField(default=0),
        ),
    ]
