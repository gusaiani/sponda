import hashlib
import secrets
from datetime import date

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


SUPPORTED_LANGUAGES = ("pt", "en", "es", "zh", "fr", "de", "it")
DEFAULT_LANGUAGE = "en"
LANGUAGE_CHOICES = tuple((code, code) for code in SUPPORTED_LANGUAGES)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    allow_contact = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default=DEFAULT_LANGUAGE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    homepage_layout = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.email


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_verification_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    TOKEN_EXPIRY_HOURS = 72

    def __str__(self):
        return f"Verification token for {self.user.email}"

    @classmethod
    def create_for_user(cls, user):
        token = secrets.token_urlsafe(48)
        return cls.objects.create(user=user, token=token)

    @property
    def is_expired(self):
        expiry = self.created_at + timezone.timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        return timezone.now() > expiry

    @property
    def is_valid(self):
        return not self.used and not self.is_expired


class UserOperation(models.Model):
    """Tracks write operations by unverified users for rate limiting."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="operations")
    operation = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.operation} @ {self.created_at}"

    DAILY_LIMIT = 14
    DAYS_BEFORE_VERIFICATION_REQUIRED = 5

    @classmethod
    def count_today(cls, user):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return cls.objects.filter(user=user, created_at__gte=today_start).count()

    @classmethod
    def distinct_active_days(cls, user):
        return cls.objects.filter(user=user).dates("created_at", "day").count()

    @classmethod
    def check_permission(cls, user):
        """Check if an unverified user can perform an operation.

        Returns (allowed, error_message).
        - Verified users: always allowed.
        - Unverified users with < 5 active days: allowed if < 14 ops today.
        - Unverified users with >= 5 active days: blocked, must verify.
        """
        if user.email_verified:
            return True, None

        active_days = cls.distinct_active_days(user)
        if active_days >= cls.DAYS_BEFORE_VERIFICATION_REQUIRED:
            return False, "Verifique seu email para continuar usando esta funcionalidade"

        today_count = cls.count_today(user)
        if today_count >= cls.DAILY_LIMIT:
            return False, f"Limite de {cls.DAILY_LIMIT} operações por dia atingido"

        return True, None

    @classmethod
    def record(cls, user, operation):
        return cls.objects.create(user=user, operation=operation)


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    TOKEN_EXPIRY_HOURS = 24

    def __str__(self):
        return f"Reset token for {self.user.email}"

    @classmethod
    def create_for_user(cls, user):
        token = secrets.token_urlsafe(48)
        return cls.objects.create(user=user, token=token)

    @property
    def is_expired(self):
        expiry = self.created_at + timezone.timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        return timezone.now() > expiry

    @property
    def is_valid(self):
        return not self.used and not self.is_expired


class FavoriteCompany(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    ticker = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "ticker")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} → {self.ticker}"


class SavedList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_lists")
    name = models.CharField(max_length=200)
    tickers = models.JSONField()  # List of ticker strings in order
    years = models.IntegerField(default=10)
    display_order = models.IntegerField(default=0)
    share_token = models.CharField(max_length=32, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_savedcomparison"
        ordering = ["display_order", "-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.user.email})"

    @classmethod
    def generate_share_token(cls):
        return secrets.token_urlsafe(24)


class SavedScreenerFilter(models.Model):
    """A user-saved combination of screener filter bounds and sort.

    Stored as a blob so the screener can evolve its set of indicators
    without requiring a migration each time. The view layer validates
    indicator and sort keys against the allow-list before persisting.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_screener_filters",
    )
    name = models.CharField(max_length=200)
    bounds = models.JSONField(default=dict, blank=True)
    sort = models.CharField(max_length=40, default="-market_cap")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.user.email})"


class CompanyVisit(models.Model):
    """Records each company visit by an analyst. One entry per user+ticker+date."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="visits")
    ticker = models.CharField(max_length=10)
    visited_at = models.DateField(default=date.today)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "ticker", "visited_at")
        ordering = ["-visited_at"]
        indexes = [models.Index(fields=["user", "-visited_at"])]

    def __str__(self):
        return f"{self.user.email} visited {self.ticker} on {self.visited_at}"


class RevisitSchedule(models.Model):
    """Tracks the next revisit date and optional recurrence for a user+ticker pair."""

    RECURRENCE_CHOICES = [
        (30, "Every 30 days"),
        (90, "Every 90 days"),
        (182, "Every 6 months"),
        (365, "Every year"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="revisit_schedules")
    ticker = models.CharField(max_length=10)
    next_revisit = models.DateField()
    recurrence_days = models.PositiveIntegerField(null=True, blank=True)
    share_token = models.CharField(max_length=32, unique=True, db_index=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "ticker")
        ordering = ["next_revisit"]

    def __str__(self):
        return f"{self.user.email} revisit {self.ticker} on {self.next_revisit}"

    @classmethod
    def generate_share_token(cls):
        return secrets.token_urlsafe(24)


class IndicatorAlert(models.Model):
    """A user-saved threshold on a company indicator.

    When the daily snapshot refresh finds an indicator has crossed the
    threshold, the alert checker emails the user and records the event so the
    in-app notifications page can surface it. Each alert is one rule — a user
    wanting both a floor *and* a ceiling on the same metric creates two rows.
    """

    COMPARISON_LTE = "lte"
    COMPARISON_GTE = "gte"
    COMPARISON_CHOICES = [
        (COMPARISON_LTE, "Less than or equal to"),
        (COMPARISON_GTE, "Greater than or equal to"),
    ]

    # Kept in sync with :class:`quotes.models.IndicatorSnapshot.INDICATOR_FIELDS`
    # minus the pure metadata fields (current_price isn't worth alerting on —
    # users watch prices elsewhere). If the snapshot model grows a new numeric
    # indicator, add it here as well.
    ALLOWED_INDICATORS = (
        "current_price",
        "pe10",
        "pfcf10",
        "peg",
        "pfcf_peg",
        "debt_to_equity",
        "debt_ex_lease_to_equity",
        "liabilities_to_equity",
        "current_ratio",
        "debt_to_avg_earnings",
        "debt_to_avg_fcf",
        "market_cap",
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="indicator_alerts",
    )
    ticker = models.CharField(max_length=10)
    indicator = models.CharField(max_length=40)
    comparison = models.CharField(max_length=3, choices=COMPARISON_CHOICES)
    threshold = models.DecimalField(max_digits=20, decimal_places=6)
    # Toggle without deleting: users can pause an alert temporarily.
    active = models.BooleanField(default=True)
    # Last time the alert condition evaluated true. Cleared when the indicator
    # crosses back so one crossing doesn't fire repeat notifications.
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "ticker", "indicator", "comparison")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "ticker"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        operator = "<=" if self.comparison == self.COMPARISON_LTE else ">="
        return f"{self.user.email} {self.ticker} {self.indicator} {operator} {self.threshold}"

    def clean(self):
        super().clean()
        if self.indicator not in self.ALLOWED_INDICATORS:
            raise ValueError(
                f"Unknown indicator {self.indicator!r}. "
                f"Allowed: {', '.join(self.ALLOWED_INDICATORS)}",
            )

    def is_triggered_by(self, value):
        """Return True when ``value`` satisfies this alert's threshold.

        ``None`` values never trigger — we can't assert anything about a row
        whose indicator couldn't be computed.
        """
        if value is None:
            return False
        if self.comparison == self.COMPARISON_LTE:
            return value <= self.threshold
        if self.comparison == self.COMPARISON_GTE:
            return value >= self.threshold
        return False


class PageView(models.Model):
    """Lightweight page view tracking. IPs are SHA-256 hashed for privacy."""

    path = models.CharField(max_length=500, db_index=True)
    ip_hash = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    session_key = models.CharField(max_length=40, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp", "path"]),
            models.Index(fields=["timestamp", "ip_hash"]),
        ]

    def __str__(self):
        return f"{self.path} @ {self.timestamp}"

    @staticmethod
    def hash_ip(ip_address):
        """One-way hash so we can count uniques without storing raw IPs."""
        salt = getattr(settings, "SECRET_KEY", "")[:16]
        return hashlib.sha256(f"{salt}:{ip_address}".encode()).hexdigest()
