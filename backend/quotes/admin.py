from django.contrib import admin

from .models import BalanceSheet, IPCAIndex, LookupLog, QuarterlyEarnings, Ticker


@admin.register(QuarterlyEarnings)
class QuarterlyEarningsAdmin(admin.ModelAdmin):
    list_display = ("ticker", "end_date", "eps", "net_income", "fetched_at")
    list_filter = ("ticker",)


@admin.register(IPCAIndex)
class IPCAIndexAdmin(admin.ModelAdmin):
    list_display = ("date", "annual_rate")


@admin.register(BalanceSheet)
class BalanceSheetAdmin(admin.ModelAdmin):
    list_display = ("ticker", "end_date", "total_debt", "total_liabilities", "stockholders_equity", "fetched_at")
    list_filter = ("ticker",)


@admin.register(Ticker)
class TickerAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "sector", "type", "updated_at")
    list_filter = ("type", "sector")
    search_fields = ("symbol", "name")


@admin.register(LookupLog)
class LookupLogAdmin(admin.ModelAdmin):
    list_display = ("ticker", "session_key", "user", "timestamp")
    list_filter = ("ticker",)
