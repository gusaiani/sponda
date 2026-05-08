"""Schema + data migration adding the social profile fields.

Adds ``handle``, ``display_name``, ``bio``, ``is_private``, and
``handle_changed_at`` to the User model and backfills a unique handle for
every existing user, derived from their email's local part with a numeric
suffix on collision.
"""
from django.db import migrations, models


def _backfill_handles(apps, schema_editor):
    """Walk every existing User and assign a unique handle.

    Uses :func:`accounts.handles.derive_handle`. The function is imported
    here (not at module top) because the production helper module is fine to
    use during a migration — it has no Django model imports of its own.
    """
    from accounts.handles import derive_handle

    user_model = apps.get_model("accounts", "User")
    existing: set[str] = set()
    # Iterate deterministically so reruns produce the same handles.
    for user in user_model.objects.order_by("id").iterator():
        if user.handle:
            existing.add(user.handle)
            continue
        handle = derive_handle(user.email or f"user{user.id}@unknown", existing)
        user.handle = handle
        user.save(update_fields=["handle"])


def _reverse_noop(apps, schema_editor):
    """Reversal blanks every handle. The schema rollback then drops the
    column, so the values are lost either way; this is a no-op."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_learning_mode_default_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="handle",
            field=models.CharField(
                blank=True, max_length=24, null=True, unique=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="user",
            name="bio",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="user",
            name="is_private",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="handle_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(_backfill_handles, _reverse_noop),
    ]
