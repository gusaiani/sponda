from django.contrib import admin

from .models import IPCAIndex, LookupLog, QuarterlyEarnings


@admin.register(QuarterlyEarnings)
class QuarterlyEarningsAdmin(admin.ModelAdmin):
    list_display = ("ticker", "end_date", "eps", "net_income", "fetched_at")
    list_filter = ("ticker",)


@admin.register(IPCAIndex)
class IPCAIndexAdmin(admin.ModelAdmin):
    list_display = ("date", "accumulated_index")


@admin.register(LookupLog)
class LookupLogAdmin(admin.ModelAdmin):
    list_display = ("ticker", "session_key", "user", "timestamp")
    list_filter = ("ticker",)
