from django.conf import settings
from django.db import models


class LLMQuery(models.Model):
    """One assistant question: who asked, about what, the verdict, the cost.

    Single source of truth for daily quota counting, cost dashboards, and the
    eval corpus. Mirrors quotes.models.LookupLog's dual identity (user OR
    ip_hash) so limits work for both authed and anonymous callers.

    Also the designated corpus for the natural-language screening feature:
    `feature` tags which product surface asked, and `interpreted_filters`
    stores the parsed filter set for `screen` rows so screening prompts can
    be evaluated against what the model actually understood.
    """

    FEATURE_ASK = "ask"
    FEATURE_SCREEN = "screen"
    FEATURE_CHOICES = [
        (FEATURE_ASK, "Ask about a company"),
        (FEATURE_SCREEN, "Screen companies by filters"),
    ]

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

    feature = models.CharField(
        max_length=16, choices=FEATURE_CHOICES, default=FEATURE_ASK
    )

    # Blank for `screen` rows: a screening query has no single ticker, it
    # returns a list of matches. Required in spirit (but not at the DB
    # level) for `ask` rows, which are always about one company.
    ticker = models.CharField(max_length=10, blank=True, default="")
    tab = models.CharField(max_length=20, blank=True, default="")
    locale = models.CharField(max_length=5, blank=True, default="")

    question = models.TextField()                    # raw user text (PII — purge policy later)
    classification = models.CharField(max_length=16) # on_topic | off_topic |jailbreak
    model = models.CharField(max_length=40, blank=True, default="")
    # Parsed filter set for `feature=screen` rows (e.g. {"pe10_max": 10,
    # "sector": "Energy"}) - null for `ask` rows, which have no filters.
    interpreted_filters = models.JSONField(null=True, blank=True)

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
