from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_email_verification_and_operations"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="homepage_layout",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
