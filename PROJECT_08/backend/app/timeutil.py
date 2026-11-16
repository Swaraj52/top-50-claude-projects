from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def local_today(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


def to_utc(value: datetime, tz: ZoneInfo) -> datetime:
    """Interpret a naive datetime as local time in tz, then convert to UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(timezone.utc)


def parse_local_datetime(value: str, tz: ZoneInfo) -> datetime | None:
    """Parse a datetime-local value (or ISO 8601 with an offset) into UTC."""
    text = (value or "").strip()
    if not text:
        return None
    candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return to_utc(parsed, tz)


def start_of_day_utc(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)


def relative_label(value: datetime, now: datetime) -> str:
    """A compact age label for a list row: 'now', '12m', '3h', '2d', '4w'."""
    seconds = max(0, int((now - value).total_seconds()))
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 7:
        return f"{days}d"
    return f"{days // 7}w"
