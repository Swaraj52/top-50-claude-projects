from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.timeutil import local_today

IST = ZoneInfo("Asia/Kolkata")
TODAY = local_today(IST)


def test_set_and_complete_priorities(client):
    task = client.post("/api/tasks", json={"title": "Finish deck"}).json()
    r = client.put(
        "/api/priorities",
        json={"day": str(TODAY), "items": [{"text": "Finish deck", "task_id": task["id"]}, {"text": "Gym"}]},
    )
    assert r.status_code == 200
    items = r.json()
    assert [(p["position"], p["text"]) for p in items] == [(1, "Finish deck"), (2, "Gym")]
    assert client.get("/api/priorities").json() == items

    done = client.patch(f"/api/priorities/{items[0]['id']}", json={"done": True}).json()
    assert done["done"] is True
    # Completing a linked priority completes its task.
    assert client.get("/api/tasks?view=done").json()[0]["id"] == task["id"]


def test_priorities_are_replaced_and_capped_at_three(client):
    day = str(TODAY)
    client.put("/api/priorities", json={"day": day, "items": [{"text": "a"}, {"text": "b"}]})
    client.put("/api/priorities", json={"day": day, "items": [{"text": "c"}]})
    assert [p["text"] for p in client.get("/api/priorities").json()] == ["c"]
    four = [{"text": str(i)} for i in range(4)]
    assert client.put("/api/priorities", json={"day": day, "items": four}).status_code == 422


def test_priorities_cannot_reference_foreign_tasks(client, make_client):
    task = client.post("/api/tasks", json={"title": "mine"}).json()
    bob = make_client("bob@example.com", name="Bob")
    r = bob.put("/api/priorities", json={"day": str(TODAY), "items": [{"text": "x", "task_id": task["id"]}]})
    assert r.status_code == 404


def test_dashboard_aggregates_today(client):
    now = datetime.now(timezone.utc)
    client.post("/api/tasks", json={"title": "overdue", "due_date": str(TODAY - timedelta(days=1)), "priority": "high"})
    client.post("/api/tasks", json={"title": "today", "due_date": str(TODAY)})
    client.post("/api/tasks", json={"title": "later", "due_date": str(TODAY + timedelta(days=5))})
    done = client.post("/api/tasks", json={"title": "done", "due_date": str(TODAY)}).json()
    client.patch(f"/api/tasks/{done['id']}", json={"status": "done"})
    client.post("/api/reminders", json={"text": "call", "remind_at": now.isoformat()})
    client.post("/api/reminders", json={"text": "next week", "remind_at": (now + timedelta(days=7)).isoformat()})
    midday = datetime.combine(TODAY, datetime.min.time(), tzinfo=IST).replace(hour=12)
    client.post("/api/events", json={"title": "lunch", "start_at": midday.isoformat(), "end_at": (midday + timedelta(hours=1)).isoformat()})

    d = client.get("/api/dashboard/today").json()
    assert d["date"] == str(TODAY) and d["user_name"] == "Ana" and d["timezone"] == "Asia/Kolkata"
    assert [t["title"] for t in d["tasks"]] == ["overdue", "today"]
    assert [r["text"] for r in d["reminders"]] == ["call"]
    assert [e["title"] for e in d["events"]] == ["lunch"]
    assert d["counts"] == {
        "overdue": 1,
        "due_today": 1,
        "done_today": 1,
        "upcoming": 1,
        "events_today": 1,
        "unread_emails": 0,
        "attention_emails": 0,
    }
    assert d["briefing"] is None and d["email_connected"] is False and d["calendars_connected"] == 0


def test_new_user_gets_an_empty_dashboard(client):
    d = client.get("/api/dashboard/today").json()
    assert d["tasks"] == d["events"] == d["reminders"] == d["priorities"] == d["emails"] == []
