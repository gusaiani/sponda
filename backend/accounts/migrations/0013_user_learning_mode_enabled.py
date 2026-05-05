from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_alert_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="learning_mode_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
