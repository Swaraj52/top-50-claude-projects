from datetime import date, timedelta
from zoneinfo import ZoneInfo

from app.timeutil import local_today

TODAY = local_today(ZoneInfo("Asia/Kolkata"))


def add(client, title, **extra):
    r = client.post("/api/tasks", json={"title": title, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def titles(client, view):
    return [t["title"] for t in client.get(f"/api/tasks?view={view}").json()]


def test_create_defaults(client):
    t = add(client, "  Write report  ")
    assert t["title"] == "Write report"
    assert t["priority"] == "medium" and t["status"] == "todo" and t["due_date"] is None


def test_views_split_by_users_local_date(client):
    add(client, "past", due_date=str(TODAY - timedelta(days=2)))
    add(client, "now", due_date=str(TODAY))
    add(client, "later", due_date=str(TODAY + timedelta(days=3)))
    add(client, "someday")
    assert titles(client, "overdue") == ["past"]
    assert titles(client, "today") == ["now"]
    assert titles(client, "upcoming") == ["later"]
    assert titles(client, "all") == ["past", "now", "later", "someday"]


def test_all_view_orders_by_priority_within_a_day(client):
    add(client, "low", priority="low", due_date=str(TODAY))
    add(client, "high", priority="high", due_date=str(TODAY))
    add(client, "medium", due_date=str(TODAY))
    assert titles(client, "today") == ["high", "medium", "low"]


def test_completing_and_reopening(client):
    t = add(client, "ship")
    done = client.patch(f"/api/tasks/{t['id']}", json={"status": "done"}).json()
    assert done["completed_at"] is not None
    assert titles(client, "done") == ["ship"] and titles(client, "all") == []
    reopened = client.patch(f"/api/tasks/{t['id']}", json={"status": "todo"}).json()
    assert reopened["completed_at"] is None


def test_patch_can_clear_due_date_but_not_title(client):
    t = add(client, "x", due_date=str(TODAY))
    r = client.patch(f"/api/tasks/{t['id']}", json={"due_date": None, "title": None})
    assert r.status_code == 200
    assert r.json()["due_date"] is None and r.json()["title"] == "x"


def test_validation(client):
    assert client.post("/api/tasks", json={"title": "   "}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "priority": "urgent"}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x" * 201}).status_code == 422
    assert client.get("/api/tasks?view=bogus").status_code == 422


def test_delete(client):
    t = add(client, "gone")
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 204
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 404


def test_users_cannot_see_or_touch_each_others_tasks(client, make_client):
    t = add(client, "private")
    bob = make_client("bob@example.com", name="Bob")
    assert bob.get("/api/tasks").json() == []
    assert bob.patch(f"/api/tasks/{t['id']}", json={"title": "pwned"}).status_code == 404
    assert bob.delete(f"/api/tasks/{t['id']}").status_code == 404
    assert client.get("/api/tasks").json()[0]["title"] == "private"


def test_due_date_must_be_a_date(client):
    assert client.post("/api/tasks", json={"title": "x", "due_date": "tomorrow"}).status_code == 422
    assert add(client, "y", due_date=date(2030, 1, 2).isoformat())["due_date"] == "2030-01-02"
