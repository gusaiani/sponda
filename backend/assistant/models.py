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


class McpCall(models.Model):
    """One JSON-RPC message answered by the public MCP server.

    The only durable record of MCP traffic. PostHog is a browser snippet and
    MCP clients never load a page, so no product analytics sees this surface;
    the per-IP caps in assistant.mcp are cache keys that expire at midnight
    and answer "is this caller over budget", not "how much is it used".

    One row per answered message, lifecycle chatter (initialize, ping,
    tools/list) included, because connection volume is as interesting as
    tool volume when the question is who has actually wired Sponda up.
    Writes are best-effort: assistant.mcp swallows failures here rather than
    fail a working tool call for the sake of a statistic.
    """

    METHOD_TOOLS_CALL = "tools/call"
    METHOD_INITIALIZE = "initialize"

    # The JSON-RPC method: initialize, ping, tools/list, tools/call, or a
    # notifications/* name. Unsupported methods are recorded too: a client
    # probing for resources/list is worth knowing about.
    method = models.CharField(max_length=64, db_index=True)
    # Only set for tools/call rows, and set even when the call was rejected,
    # so rate-limit pressure can be attributed to the tool that caused it.
    tool_name = models.CharField(max_length=64, blank=True, default="")

    # clientInfo from initialize. Absent on every other method: the server is
    # stateless, so nothing carries the identity across requests.
    client_name = models.CharField(max_length=100, blank=True, default="")
    client_version = models.CharField(max_length=40, blank=True, default="")
    protocol_version = models.CharField(max_length=20, blank=True, default="")
    # The one per-request client signal that is always present.
    user_agent = models.CharField(max_length=300, blank=True, default="")

    # tools/call rows only: the arguments object the client sent, stored
    # verbatim so the dashboard can mine what callers actually ask for
    # (indicators, countries, sectors, symbols). Size-guarded at write time
    # (assistant.mcp) because the sender is unauthenticated; null for
    # lifecycle methods, argument-less calls, and rows predating the field.
    arguments = models.JSONField(null=True, blank=True)
    # screen_companies rows only: how many companies matched the screen
    # (the total match count, not the page size). Zero here is the signal
    # that a caller asked for something the data could not answer. Null for
    # every other tool and for screens that errored before running.
    result_count = models.IntegerField(null=True, blank=True)

    # SHA-256 of the client IP (quotes.client_ip.client_ip_hash), the same
    # identity the rate limiter counts against and PageView stores.
    ip_hash = models.CharField(max_length=64, db_index=True)

    # True for invalid params, executor errors surfaced as isError, and
    # rejected calls — anything the caller could not use. A "method not
    # found" answer to a capability probe (server/discover, resources/list)
    # is a usable answer and does not count.
    failed = models.BooleanField(default=False)
    # A subset of `failed`: turned away by a daily cap with HTTP 429.
    rate_limited = models.BooleanField(default=False)
    latency_ms = models.IntegerField(default=0)

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp", "method"]),
            models.Index(fields=["timestamp", "tool_name"]),
            models.Index(fields=["timestamp", "ip_hash"]),
        ]

    def __str__(self):
        return f"{self.method}{f' {self.tool_name}' if self.tool_name else ''} @ {self.timestamp}"
