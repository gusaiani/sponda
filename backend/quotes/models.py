from django.conf import settings
from django.db import models


class QuarterlyEarnings(models.Model):
    ticker = models.CharField(max_length=10, db_index=True)
    end_date = models.DateField()
    net_income = models.BigIntegerField(null=True, blank=True)
    eps = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True,
        help_text="basicEarningsPerCommonShare from BRAPI",
    )
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("ticker", "end_date")
        ordering = ["-end_date"]

    def __str__(self):
        return f"{self.ticker} {self.end_date}"


class IPCAIndex(models.Model):
    date = models.DateField(unique=True)
    annual_rate = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text="12-month accumulated IPCA rate (%)",
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"IPCA {self.date}: {self.annual_rate}%"


class QuarterlyCashFlow(models.Model):
    ticker = models.CharField(max_length=10, db_index=True)
    end_date = models.DateField()
    operating_cash_flow = models.BigIntegerField(null=True, blank=True)
    investment_cash_flow = models.BigIntegerField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("ticker", "end_date")
        ordering = ["-end_date"]

    def __str__(self):
        return f"{self.ticker} {self.end_date} CF"


class BalanceSheet(models.Model):
    ticker = models.CharField(max_length=10, db_index=True)
    end_date = models.DateField()
    total_debt = models.BigIntegerField(
        null=True, blank=True,
        help_text="Dívida bruta (short + long term debt)",
    )
    total_liabilities = models.BigIntegerField(
        null=True, blank=True,
        help_text="Passivo total",
    )
    stockholders_equity = models.BigIntegerField(
        null=True, blank=True,
        help_text="Patrimônio líquido",
    )
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("ticker", "end_date")
        ordering = ["-end_date"]

    def __str__(self):
        return f"{self.ticker} {self.end_date} BS"


class Ticker(models.Model):
    symbol = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=200, blank=True, default="")
    sector = models.CharField(max_length=100, blank=True, default="")
    type = models.CharField(max_length=50, blank=True, default="")
    logo = models.URLField(max_length=500, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.symbol} — {self.name}"


class LookupLog(models.Model):
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
    )
    ticker = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.session_key or self.user} → {self.ticker} @ {self.timestamp}"
