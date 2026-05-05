from django.db import migrations, models


def turn_on_for_existing_users(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(learning_mode_enabled=False).update(learning_mode_enabled=True)


def reverse_noop(apps, schema_editor):
    """Reversal is intentionally a no-op: we don't know which users had
    explicitly disabled the flag before this migration ran."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_user_learning_mode_enabled"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="learning_mode_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(turn_on_for_existing_users, reverse_noop),
    ]
