"""Delete McpCall audit rows older than the retention window.

The MCP endpoint is public, so its audit table grows forever without this:
the per-IP daily recording cap bounds the growth rate, the weekly systemd
timer running this command bounds the total size. The window comes from
settings.MCP_CALL_RETENTION_DAYS.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from assistant.models import McpCall


class Command(BaseCommand):
    help = "Delete McpCall rows older than settings.MCP_CALL_RETENTION_DAYS."

    def handle(self, *args, **options):
        retention_days = settings.MCP_CALL_RETENTION_DAYS
        cutoff = timezone.now() - timezone.timedelta(days=retention_days)
        deleted_count, _ = McpCall.objects.filter(timestamp__lt=cutoff).delete()
        self.stdout.write(
            f"Pruned {deleted_count} MCP call(s) older than "
            f"{retention_days} days."
        )
