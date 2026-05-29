from django.conf import settings
from django.db import models


class LLMQuery(models.Model):
    """One assistant question: who asked, about what, the verdict, the cost.

    Single source of truth for daily quota counting, cost dashboards, and the
    future eval corpus. Mirrors quotes.models.LookupLog's dual identity
    (user OR ip_hash) so limits work for both authed and anonymous callers.
    """

    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    # SHA-256 of the client IP (quotes.client_ip.client_ip_hash) - used so a
    # future anon/trial cap is per-IP, not per-trivially-cleared cookie.
    ip_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # keep cost/abuse rows if the user is deleted
    )

    ticker = models.CharField(max_length=10)
    tab = models.CharField(max_length=20, blank=True, default="")
    locale = models.CharField(max_length=5, blank=True, default="")

    question = models.TextField()                    # raw user text (PII — purge policy later)
    classification = models.CharField(max_length=16) # on_topic | off_topic |jailbreak
    model = models.CharField(max_length=40, blank=True, default="")

    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.IntegerField(default=0)
    status = models.CharField(max_length=16, default="ok")  # ok | off_topic | error | limited

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),    # per-user daily count
            models.Index(fields=["ip_hash", "created_at"]), # per-IP daily count (future)
            models.Index(fields=["ticker", "created_at"]),  # per-company analytics
        ]

    def __str__(self):
        return f"{self.user or self.ip_hash} → {self.ticker} [{self.classification}]"
