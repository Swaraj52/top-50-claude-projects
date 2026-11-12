from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def local_today(tz: ZoneInfo, now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(tz).date()


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def parse_week(value: str | None, today: date) -> date:
    """Parse a YYYY-MM-DD week anchor and snap it to Monday; default this week."""
    if value:
        try:
            return monday_of(date.fromisoformat(value))
        except ValueError:
            pass
    return monday_of(today)


def week_label(start: date) -> str:
    end = start + timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {end:%b %Y}"
    return f"{start.day} {start:%b} – {end.day} {end:%b %Y}"
