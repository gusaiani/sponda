from django.contrib import admin

from slackbot.models import SlackLLMKey, SlackQuery


@admin.register(SlackLLMKey)
class SlackLLMKeyAdmin(admin.ModelAdmin):
    """Key rows are visible for support (who registered, which provider,
    when) — the ciphertext itself is deliberately not editable and the
    plaintext is never shown anywhere."""
    list_display = ("slack_team_id", "slack_user_id", "provider",
                    "created_at", "updated_at")
    list_filter = ("provider",)
    search_fields = ("slack_team_id", "slack_user_id")
    readonly_fields = ("encrypted_api_key", "created_at", "updated_at")


@admin.register(SlackQuery)
class SlackQueryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "slack_team_id", "slack_user_id", "provider",
                    "status", "input_tokens", "output_tokens", "latency_ms",
                    "short_question")
    list_filter = ("provider", "status")
    search_fields = ("slack_team_id", "slack_user_id", "question")
    readonly_fields = [field.name for field in SlackQuery._meta.fields]
    date_hierarchy = "created_at"

    @admin.display(description="question")
    def short_question(self, row):
        return row.question[:80]
