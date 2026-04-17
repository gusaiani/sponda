"""Exchange market-hours helpers.

B3 (Brazil): Monday-Friday 10:00-17:30 BRT (UTC-3, no DST since 2019).
NYSE/NASDAQ: Monday-Friday 09:30-16:00 ET (America/New_York, DST-aware).
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_B3_TZ = ZoneInfo("America/Sao_Paulo")
_NYSE_TZ = ZoneInfo("America/New_York")

_B3_OPEN = (10, 0)
_B3_CLOSE = (17, 30)

_NYSE_OPEN = (9, 30)
_NYSE_CLOSE = (16, 0)


def _minutes_since_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def is_b3_open(now: datetime | None = None) -> bool:
    """Return True if B3 is currently in its regular session."""
    if now is None:
        now = datetime.now(tz=timezone.utc)
    local = now.astimezone(_B3_TZ)
    if local.weekday() >= 5:
        return False
    current = _minutes_since_midnight(local)
    open_minutes = _B3_OPEN[0] * 60 + _B3_OPEN[1]
    close_minutes = _B3_CLOSE[0] * 60 + _B3_CLOSE[1]
    return open_minutes <= current < close_minutes


def is_nyse_open(now: datetime | None = None) -> bool:
    """Return True if NYSE is currently in its regular session."""
    if now is None:
        now = datetime.now(tz=timezone.utc)
    local = now.astimezone(_NYSE_TZ)
    if local.weekday() >= 5:
        return False
    current = _minutes_since_midnight(local)
    open_minutes = _NYSE_OPEN[0] * 60 + _NYSE_OPEN[1]
    close_minutes = _NYSE_CLOSE[0] * 60 + _NYSE_CLOSE[1]
    return open_minutes <= current < close_minutes


def any_exchange_open(now: datetime | None = None) -> bool:
    """Return True if at least one major exchange (B3 or NYSE) is open."""
    if now is None:
        now = datetime.now(tz=timezone.utc)
    return is_b3_open(now) or is_nyse_open(now)
