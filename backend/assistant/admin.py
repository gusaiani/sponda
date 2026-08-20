from django.contrib import admin

from assistant.models import McpCall


@admin.register(McpCall)
class McpCallAdmin(admin.ModelAdmin):
    """Read-only browser for the MCP audit log.

    The admin dashboard shows 30-day aggregates mined from these rows; this
    page is for reading the raw rows — which arguments a call sent, what a
    zero-result screen actually asked for. Strictly read-only: the table is
    written by the MCP endpoint and an edited audit row is worse than none.
    """

    list_display = (
        "timestamp",
        "method",
        "tool_name",
        "result_count",
        "failed",
        "rate_limited",
        "latency_ms",
        "user_agent",
    )
    list_filter = ("method", "tool_name", "failed", "rate_limited")
    date_hierarchy = "timestamp"
    search_fields = ("ip_hash", "user_agent", "client_name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
