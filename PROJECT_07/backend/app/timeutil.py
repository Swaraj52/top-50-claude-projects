from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKDAY_INDEX = {name.lower(): i for i, name in enumerate(WEEKDAYS)}


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


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def relative_day(value: str, today: date) -> date | None:
    """Parse a small set of human due-date phrases; return None when unsure."""
    value = (value or "").strip().lower()
    if not value:
        return None
    if value in ("today", "eod"):
        return today
    if value == "tomorrow":
        return today + timedelta(days=1)
    if value in ("next week", "in a week"):
        return today + timedelta(days=7)
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if iso:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    match = re.search(r"\b(?:by|on|due)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", value)
    if match:
        target = WEEKDAY_INDEX[match.group(1)]
        ahead = (target - today.weekday()) % 7
        return today + timedelta(days=ahead or 7)
    return None


def parse_people(raw: str) -> list[str]:
    """Split a free-text people field on commas, semicolons or newlines."""
    seen: set[str] = set()
    out: list[str] = []
    for piece in re.split(r"[,;\n]", raw or ""):
        name = piece.strip()
        if not name or len(name) > 120:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out[:40]


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


def local_day_of(value: datetime, tz: ZoneInfo) -> date:
    return value.astimezone(tz).date()


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
