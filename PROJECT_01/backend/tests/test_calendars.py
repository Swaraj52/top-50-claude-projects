from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select

from app.models import CalendarSource, Event
from app.services import ics

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc

SAMPLE = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//tests//EN
BEGIN:VEVENT
UID:weekly-1
SUMMARY:Team sync
DTSTART;TZID=Europe/Berlin:20260105T100000
DTEND;TZID=Europe/Berlin:20260105T103000
RRULE:FREQ=WEEKLY;COUNT=4
EXDATE;TZID=Europe/Berlin:20260112T100000
END:VEVENT
BEGIN:VEVENT
UID:allday-1
SUMMARY:Holiday
DTSTART;VALUE=DATE:20260115
DTEND;VALUE=DATE:20260116
END:VEVENT
BEGIN:VEVENT
UID:floating-1
SUMMARY:Dentist
DTSTART:20260120T150000
DURATION:PT45M
END:VEVENT
BEGIN:VEVENT
UID:utc-1
SUMMARY:Webinar
LOCATION:Online
DTSTART:20260121T120000Z
DTEND:20260121T130000Z
END:VEVENT
BEGIN:VEVENT
UID:cancel-1
SUMMARY:Cancelled thing
STATUS:CANCELLED
DTSTART:20260122T120000Z
DTEND:20260122T130000Z
END:VEVENT
BEGIN:VEVENT
UID:outside-1
SUMMARY:Way later
DTSTART:20260601T120000Z
DTEND:20260601T130000Z
END:VEVENT
END:VCALENDAR
"""


def parse_sample():
    return ics.parse_ics(
        SAMPLE, IST, window_start=datetime(2026, 1, 1, tzinfo=UTC), window_end=datetime(2026, 2, 1, tzinfo=UTC)
    )


def test_parse_expands_recurrence_and_respects_exdate():
    events = parse_sample()
    assert [e.title for e in events] == ["Team sync", "Holiday", "Team sync", "Dentist", "Webinar", "Team sync"]
    syncs = [e for e in events if e.title == "Team sync"]
    # 10:00 Berlin (CET, UTC+1) = 09:00 UTC; Jan 12 excluded by EXDATE.
    assert [e.start_at for e in syncs] == [datetime(2026, 1, d, 9, 0, tzinfo=UTC) for d in (5, 19, 26)]
    assert len({e.uid for e in events}) == len(events)


def test_parse_all_day_and_floating_use_the_users_timezone():
    by_title = {e.title: e for e in parse_sample()}
    holiday = by_title["Holiday"]
    assert holiday.all_day
    assert holiday.start_at == datetime(2026, 1, 14, 18, 30, tzinfo=UTC)  # midnight IST
    assert holiday.end_at - holiday.start_at == timedelta(days=1)
    dentist = by_title["Dentist"]
    assert dentist.start_at == datetime(2026, 1, 20, 9, 30, tzinfo=UTC)  # 15:00 IST
    assert dentist.end_at == datetime(2026, 1, 20, 10, 15, tzinfo=UTC)
    assert by_title["Webinar"].location == "Online"


def test_parse_rejects_garbage():
    with pytest.raises(ics.IcsError):
        ics.parse_ics(b"this is not a calendar", IST)


def test_fetch_ics_enforces_status_and_size():
    ok = httpx.MockTransport(lambda req: httpx.Response(200, content=SAMPLE))
    assert ics.fetch_ics("https://cal.example.com/a.ics", transport=ok) == SAMPLE

    missing = httpx.MockTransport(lambda req: httpx.Response(404))
    with pytest.raises(ics.IcsError, match="404"):
        ics.fetch_ics("https://cal.example.com/a.ics", transport=missing)

    huge = httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * (ics.MAX_BYTES + 10)))
    with pytest.raises(ics.IcsError, match="5 MB"):
        ics.fetch_ics("https://cal.example.com/a.ics", transport=huge)


def feed_for_today(title="Planning", hour=10) -> bytes:
    start = datetime.now(IST).replace(hour=hour, minute=0, second=0, microsecond=0).astimezone(UTC)
    fmt = "%Y%m%dT%H%M%SZ"
    return (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//EN\nBEGIN:VEVENT\nUID:p1\n"
        f"SUMMARY:{title}\nDTSTART:{start.strftime(fmt)}\n"
        f"DTEND:{(start + timedelta(hours=1)).strftime(fmt)}\nEND:VEVENT\nEND:VCALENDAR\n"
    ).encode()


def today_events(client):
    start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    return client.get(
        "/api/events", params={"start": start.isoformat(), "end": (start + timedelta(days=1)).isoformat()}
    ).json()


def test_upload_creates_read_only_events(client):
    r = client.post(
        "/api/calendars/upload", files={"file": ("work.ics", feed_for_today(), "text/calendar")}
    )
    assert r.status_code == 201, r.text
    source = r.json()
    assert source["name"] == "work" and source["kind"] == "file" and source["event_count"] == 1

    [event] = today_events(client)
    assert event["title"] == "Planning" and event["read_only"] and event["source_name"] == "work"
    assert client.patch(f"/api/events/{event['id']}", json={"title": "x"}).status_code == 409
    assert client.post(f"/api/calendars/{source['id']}/sync").status_code == 409


def test_upload_rejects_invalid_file(client):
    r = client.post("/api/calendars/upload", files={"file": ("x.ics", b"nope", "text/calendar")})
    assert r.status_code == 400


def test_subscribe_encrypts_url_and_resyncs(client, app, monkeypatch):
    feeds = {"n": 0}

    def fake_fetch(url, timeout=15.0, transport=None):
        assert url == "https://calendar.example.com/private-abc/basic.ics"
        feeds["n"] += 1
        return feed_for_today("Planning" if feeds["n"] == 1 else "Planning (moved)", hour=11)

    monkeypatch.setattr(ics, "fetch_ics", fake_fetch)
    r = client.post(
        "/api/calendars",
        json={"name": "Work", "url": "webcal://calendar.example.com/private-abc/basic.ics", "color": "#123456"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "url" not in body and body["last_error"] is None

    with app.state.sessionmaker() as db:
        stored = db.scalar(select(CalendarSource.url_encrypted))
    assert "private-abc" not in stored
    assert app.state.secret_box.decrypt(stored).endswith("private-abc/basic.ics")

    synced = client.post(f"/api/calendars/{body['id']}/sync").json()
    assert synced["event_count"] == 1
    assert [e["title"] for e in today_events(client)] == ["Planning (moved)"]


def test_subscribe_with_unreachable_url_fails_fast(client, monkeypatch):
    def boom(url, timeout=15.0, transport=None):
        raise ics.IcsError("Calendar server answered HTTP 404")

    monkeypatch.setattr(ics, "fetch_ics", boom)
    r = client.post("/api/calendars", json={"name": "W", "url": "https://x.example.com/c.ics"})
    assert r.status_code == 400 and "404" in r.json()["detail"]
    assert client.get("/api/calendars").json() == []


def test_failed_resync_records_error(client, monkeypatch):
    monkeypatch.setattr(ics, "fetch_ics", lambda url, timeout=15.0, transport=None: feed_for_today())
    source = client.post("/api/calendars", json={"name": "W", "url": "https://x.example.com/c.ics"}).json()

    def boom(url, timeout=15.0, transport=None):
        raise ics.IcsError("Timed out while downloading the calendar")

    monkeypatch.setattr(ics, "fetch_ics", boom)
    assert client.post(f"/api/calendars/{source['id']}/sync").status_code == 502
    assert client.get("/api/calendars").json()[0]["last_error"].startswith("Timed out")
    # Previously synced events are kept when a sync fails.
    assert len(today_events(client)) == 1


def test_url_validation(client):
    assert client.post("/api/calendars", json={"name": "W", "url": "ftp://x.example.com/c.ics"}).status_code == 422
    assert client.post("/api/calendars", json={"name": "W", "url": "https://x.example.com/c.ics", "color": "red"}).status_code == 422


def test_deleting_a_calendar_removes_its_events(client, app):
    source = client.post(
        "/api/calendars/upload", files={"file": ("a.ics", feed_for_today(), "text/calendar")}
    ).json()
    assert client.delete(f"/api/calendars/{source['id']}").status_code == 204
    with app.state.sessionmaker() as db:
        assert db.scalars(select(Event)).all() == []


def test_calendars_are_private(client, make_client):
    source = client.post(
        "/api/calendars/upload", files={"file": ("a.ics", feed_for_today(), "text/calendar")}
    ).json()
    bob = make_client("bob@example.com", name="Bob")
    assert bob.get("/api/calendars").json() == []
    assert bob.delete(f"/api/calendars/{source['id']}").status_code == 404
