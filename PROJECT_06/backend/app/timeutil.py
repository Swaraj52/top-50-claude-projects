from __future__ import annotations

import re
from datetime import date, datetime, timedelta
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


def parse_attendees(raw: str) -> list[str]:
    """Split an attendee string on commas, semicolons or newlines; keep order and drop blanks."""
    seen: set[str] = set()
    out: list[str] = []
    for piece in re.split(r"[,;\n]", raw or ""):
        name = piece.strip().lstrip("@")
        if not name or len(name) > 80:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out[:30]
