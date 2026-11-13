from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAYS = [("Mon", 0), ("Tue", 1), ("Wed", 2), ("Thu", 3), ("Fri", 4), ("Sat", 5), ("Sun", 6)]


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


def parse_days(value: str) -> list[int]:
    """Parse a stored day list into sorted unique ISO weekdays (fallback: every day)."""
    out = set()
    for chunk in (value or "").split(","):
        chunk = chunk.strip()
        if chunk.isdigit() and 0 <= int(chunk) <= 6:
            out.add(int(chunk))
    return sorted(out) or list(range(7))


def days_to_string(days: list[int]) -> str:
    return ",".join(str(d) for d in sorted(set(d for d in days if 0 <= d <= 6))) or "0,1,2,3,4,5,6"


def schedule_label(value) -> str:
    """Human schedule label. Accepts a stored day string or a Habit-like object."""
    days = getattr(value, "days", value)
    parsed = parse_days(days)
    if len(parsed) == 7:
        return "Every day"
    if parsed == [0, 1, 2, 3, 4]:
        return "Weekdays"
    if parsed == [5, 6]:
        return "Weekends"
    names = dict((num, name) for name, num in WEEKDAYS)
    return " · ".join(names[d] for d in parsed)


def month_grid(year: int, month: int, week_starts_monday: bool = True) -> list[list[date | None]]:
    """Weeks of dates for a month, padded to full Monday-start weeks."""
    cal = calendar.Calendar(firstweekday=0 if week_starts_monday else 6)
    weeks: list[list[date | None]] = []
    for week in cal.monthdatescalendar(year, month):
        weeks.append([d if d.month == month else None for d in week])
    return weeks


def month_bounds(day: date) -> tuple[date, date]:
    first = day.replace(day=1)
    last = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    return first, last
