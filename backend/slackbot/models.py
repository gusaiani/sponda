from django.db import models

PROVIDER_CHOICES = [
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
]


class SlackLLMKey(models.Model):
    """One Slack user's BYOK provider credential, encrypted at rest.

    Keyed by (team, user): the same person in two workspaces registers
    twice, and one workspace never sees another's keys. The plaintext key
    exists only in memory inside the answer task; the row stores the
    Fernet ciphertext (slackbot.crypto).
    """
    slack_team_id = models.CharField(max_length=32)
    slack_user_id = models.CharField(max_length=32)
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES)
    encrypted_api_key = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slack_team_id", "slack_user_id"],
                name="unique_key_per_slack_user",
            )
        ]

    def __str__(self):
        return f"{self.slack_team_id}/{self.slack_user_id} ({self.provider})"


class SlackQuery(models.Model):
    """Audit row for one Slack question — mirror of assistant.LLMQuery.

    Doubles as the thread memory: the answer task rebuilds conversation
    history from this thread's prior ok rows, so follow-ups work without
    trusting anything the client resends.
    """
    slack_team_id = models.CharField(max_length=32)
    slack_user_id = models.CharField(max_length=32)
    channel_id = models.CharField(max_length=32)
    thread_ts = models.CharField(max_length=32)
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES)
    question = models.TextField()
    answer = models.TextField(blank=True, default="")
    # "ok" or the Failed event code (invalid_api_key, upstream_timeout, …).
    status = models.CharField(max_length=32, default="ok")
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    latency_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["channel_id", "thread_ts", "created_at"],
                name="slackquery_thread_idx",
            )
        ]
        verbose_name_plural = "slack queries"

    def __str__(self):
        return f"{self.channel_id}/{self.thread_ts}: {self.question[:40]}"
