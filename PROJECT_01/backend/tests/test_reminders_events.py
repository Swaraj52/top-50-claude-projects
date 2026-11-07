from datetime import datetime, timedelta, timezone

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.isoformat()


# --- reminders ------------------------------------------------------------------------


def test_reminder_due_snooze_dismiss(client):
    past = client.post("/api/reminders", json={"text": "stretch", "remind_at": iso(NOW - timedelta(minutes=5))}).json()
    client.post("/api/reminders", json={"text": "later", "remind_at": iso(NOW + timedelta(hours=2))})

    assert [r["text"] for r in client.get("/api/reminders/due").json()] == ["stretch"]
    assert len(client.get("/api/reminders").json()) == 2

    snoozed = client.post(f"/api/reminders/{past['id']}/snooze", json={"minutes": 10}).json()
    assert datetime.fromisoformat(snoozed["remind_at"]) > NOW + timedelta(minutes=9)
    assert client.get("/api/reminders/due").json() == []

    dismissed = client.post(f"/api/reminders/{past['id']}/dismiss").json()
    assert dismissed["status"] == "dismissed"
    assert len(client.get("/api/reminders").json()) == 1
    assert len(client.get("/api/reminders?status=all").json()) == 2


def test_rescheduling_a_dismissed_reminder_reactivates_it(client):
    r = client.post("/api/reminders", json={"text": "x", "remind_at": iso(NOW)}).json()
    client.post(f"/api/reminders/{r['id']}/dismiss")
    patched = client.patch(f"/api/reminders/{r['id']}", json={"remind_at": iso(NOW + timedelta(days=1))}).json()
    assert patched["status"] == "pending"


def test_reminder_requires_timezone_aware_time(client):
    r = client.post("/api/reminders", json={"text": "x", "remind_at": "2030-01-01T09:00:00"})
    assert r.status_code == 422


def test_reminder_cannot_link_someone_elses_task(client, make_client):
    task = client.post("/api/tasks", json={"title": "mine"}).json()
    bob = make_client("bob@example.com", name="Bob")
    r = bob.post("/api/reminders", json={"text": "x", "remind_at": iso(NOW), "task_id": task["id"]})
    assert r.status_code == 404
    assert client.post("/api/reminders", json={"text": "x", "remind_at": iso(NOW), "task_id": task["id"]}).status_code == 201


def test_snooze_bounds(client):
    r = client.post("/api/reminders", json={"text": "x", "remind_at": iso(NOW)}).json()
    assert client.post(f"/api/reminders/{r['id']}/snooze", json={"minutes": 0}).status_code == 422
    assert client.post(f"/api/reminders/{r['id']}/snooze", json={"minutes": 99999}).status_code == 422


# --- events ---------------------------------------------------------------------------


def make_event(client, title, start, minutes=30, **extra):
    r = client.post(
        "/api/events",
        json={"title": title, "start_at": iso(start), "end_at": iso(start + timedelta(minutes=minutes)), **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


def query(client, start, end):
    r = client.get("/api/events", params={"start": iso(start), "end": iso(end)})
    assert r.status_code == 200, r.text
    return [e["title"] for e in r.json()]


def test_event_range_uses_overlap(client):
    make_event(client, "standup", NOW + timedelta(hours=1))
    make_event(client, "spans window start", NOW - timedelta(minutes=30), minutes=60)
    make_event(client, "next week", NOW + timedelta(days=7))
    assert query(client, NOW, NOW + timedelta(days=1)) == ["spans window start", "standup"]


def test_local_event_is_editable(client):
    e = make_event(client, "1:1", NOW, location="Room 4")
    assert e["read_only"] is False and e["source_id"] is None and e["location"] == "Room 4"
    r = client.patch(f"/api/events/{e['id']}", json={"title": "1:1 with Sam"})
    assert r.json()["title"] == "1:1 with Sam"
    bad = client.patch(f"/api/events/{e['id']}", json={"end_at": iso(NOW - timedelta(hours=1))})
    assert bad.status_code == 422
    assert client.delete(f"/api/events/{e['id']}").status_code == 204


def test_event_validation(client):
    r = client.post("/api/events", json={"title": "x", "start_at": iso(NOW), "end_at": iso(NOW - timedelta(minutes=1))})
    assert r.status_code == 422
    r = client.get("/api/events", params={"start": iso(NOW), "end": iso(NOW + timedelta(days=90))})
    assert r.status_code == 422
    r = client.get("/api/events", params={"start": iso(NOW), "end": iso(NOW)})
    assert r.status_code == 422


def test_events_are_private(client, make_client):
    e = make_event(client, "secret", NOW)
    bob = make_client("bob@example.com", name="Bob")
    assert query(bob, NOW - timedelta(days=1), NOW + timedelta(days=1)) == []
    assert bob.delete(f"/api/events/{e['id']}").status_code == 404
