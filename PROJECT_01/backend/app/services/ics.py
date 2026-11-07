"""Fetch and parse iCalendar (.ics) feeds into concrete event occurrences."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events
from sqlalchemy import delete
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..models import CalendarSource, Event

log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
MAX_EVENTS = 5000
WINDOW_BACK = timedelta(days=30)
WINDOW_FORWARD = timedelta(days=180)
USER_AGENT = "PersonalDashboard/1.0 (+calendar sync)"


class IcsError(Exception):
    """A user-facing problem with a calendar feed."""


@dataclass
class ParsedEvent:
    uid: str
    title: str
    location: str
    description: str
    start_at: datetime
    end_at: datetime
    all_day: bool


def fetch_ics(url: str, timeout: float = 15.0, transport: httpx.BaseTransport | None = None) -> bytes:
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": USER_AGENT, "Accept": "text/calendar, */*;q=0.5"},
            transport=transport,
        ) as client, client.stream("GET", url) as resp:
            if resp.url.scheme not in ("http", "https"):
                raise IcsError("Calendar URL redirected to an unsupported scheme")
            if resp.status_code >= 400:
                raise IcsError(f"Calendar server answered HTTP {resp.status_code}")
            chunks, size = [], 0
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise IcsError("Calendar feed is larger than 5 MB")
                chunks.append(chunk)
    except httpx.TimeoutException as exc:
        raise IcsError("Timed out while downloading the calendar") from exc
    except httpx.HTTPError as exc:
        raise IcsError(f"Could not download the calendar ({exc.__class__.__name__})") from exc
    return b"".join(chunks)


def _to_utc(value: date | datetime, tz: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:  # floating time: interpret in the user's timezone
            value = value.replace(tzinfo=tz)
        return value.astimezone(timezone.utc)
    return datetime.combine(value, time.min, tzinfo=tz).astimezone(timezone.utc)


def parse_ics(
    data: bytes,
    tz: ZoneInfo,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[ParsedEvent]:
    now = utcnow()
    window_start = window_start or now - WINDOW_BACK
    window_end = window_end or now + WINDOW_FORWARD
    try:
        cal = icalendar.Calendar.from_ical(data)
    except (ValueError, IndexError, KeyError) as exc:
        raise IcsError("This is not a valid iCalendar (.ics) file") from exc
    if getattr(cal, "name", "") != "VCALENDAR":
        raise IcsError("This is not a valid iCalendar (.ics) file")

    try:
        occurrences = recurring_ical_events.of(cal, skip_bad_series=True).between(
            window_start, window_end
        )
    except Exception as exc:  # the library raises several types for malformed rules
        raise IcsError(f"Could not expand the calendar's events: {exc}") from exc

    events: list[ParsedEvent] = []
    for comp in occurrences:
        if comp.name != "VEVENT" or str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        dtstart = comp.get("DTSTART")
        if dtstart is None:
            continue
        start = dtstart.dt
        all_day = not isinstance(start, datetime)
        if comp.get("DTEND") is not None:
            end = comp.get("DTEND").dt
        elif comp.get("DURATION") is not None:
            end = start + comp.get("DURATION").dt
        else:
            end = start + timedelta(days=1) if all_day else start
        start_utc, end_utc = _to_utc(start, tz), _to_utc(end, tz)
        if end_utc < start_utc:
            end_utc = start_utc
        events.append(
            ParsedEvent(
                uid=f"{comp.get('UID', '')}|{start_utc.isoformat()}"[:255],
                title=(str(comp.get("SUMMARY", "")).strip() or "(No title)")[:300],
                location=str(comp.get("LOCATION", "")).strip()[:300],
                description=str(comp.get("DESCRIPTION", "")).strip()[:5000],
                start_at=start_utc,
                end_at=end_utc,
                all_day=all_day,
            )
        )
        if len(events) >= MAX_EVENTS:
            log.warning("calendar truncated at %d events", MAX_EVENTS)
            break
    events.sort(key=lambda e: e.start_at)
    return events


def replace_source_events(db: DbSession, source: CalendarSource, parsed: list[ParsedEvent]) -> None:
    """Swap a source's events for a freshly parsed set (caller commits)."""
    db.execute(delete(Event).where(Event.source_id == source.id))
    db.add_all(
        Event(
            user_id=source.user_id,
            source_id=source.id,
            uid=p.uid,
            title=p.title,
            location=p.location,
            description=p.description,
            start_at=p.start_at,
            end_at=p.end_at,
            all_day=p.all_day,
        )
        for p in parsed
    )
    source.event_count = len(parsed)
    source.last_synced_at = utcnow()
    source.last_error = None
