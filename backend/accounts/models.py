import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)
    allow_contact = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


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
