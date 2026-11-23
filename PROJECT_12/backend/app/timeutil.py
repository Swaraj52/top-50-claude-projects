from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def local_today(timezone: str = "UTC") -> str:
    """Return today's date in the given timezone."""
    tz = ZoneInfo(timezone)
    return datetime.now(tz).date()


def relative_label(dt: datetime, timezone: str = "UTC") -> str:
    """Return a relative label for a datetime (e.g., '2 hours ago')."""
    from datetime import datetime as _dt
    now = datetime.now(ZoneInfo(timezone))
    diff = now - dt.replace(tzinfo=ZoneInfo(timezone))
    total_seconds = abs(int(diff.total_seconds()))

    if total_seconds < 60:
        return "just now"
    elif total_seconds < 120:
        return "1 minute ago"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif total_seconds < 7200:
        return "1 hour ago"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif total_seconds < 172800:
        return "1 day ago"
    else:
        days = total_seconds // 86400
        return f"{days} day{'s' if days > 1 else ''} ago"


def zone(timezone: str = "UTC") -> ZoneInfo:
    """Return a ZoneInfo object for the given timezone."""
    return ZoneInfo(timezone)