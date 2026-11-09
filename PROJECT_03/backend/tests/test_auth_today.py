import json

from sqlalchemy import select

from app.models import Blocker, Checkin, LogEntry, Task


def tasks(app):
    with app.state.sessionmaker() as db:
        return list(db.scalars(select(Task).order_by(Task.id)))


# --- auth ---------------------------------------------------------------------------------


def test_signed_out_pages_redirect_to_login(make_browser):
    b = make_browser()
    for path in ("/", "/today", "/review", "/trends", "/history", "/settings"):
        r = b.get(path)
        assert r.status_code == 303 and r.headers["location"] == "/login", path
    r = b.c.post("/tasks", headers={"HX-Request": "true"})
    assert r.status_code == 401 and r.headers["hx-redirect"] == "/login"


def test_register_requires_form_token_and_validates(make_browser):
    b = make_browser()
    b.get("/register")
    assert b.post("/register", {"name": "S", "email": "s@example.com", "password": "long enough 1"}, csrf=False).status_code == 403
    r = b.post("/register", {"name": "S", "email": "not-an-email", "password": "long enough 1"})
    assert r.status_code == 422 and "valid email" in r.text
    b.get("/register")
    r = b.post("/register", {"name": "S", "email": "s@example.com", "password": "short"})
    assert r.status_code == 422 and "at least 8" in r.text


def test_register_login_logout(make_browser, browser):
    page = browser.get("/today")
    assert page.status_code == 200 and "Today, Swayam" in page.text
    assert "built by Swayam" in page.text
    assert browser.post("/logout", csrf=False).status_code == 403  # logout needs the CSRF token too
    assert browser.post("/logout").status_code == 303
    assert browser.get("/today").headers["location"] == "/login"

    other = make_browser()
    other.get("/login")
    bad = other.post("/login", {"email": "swayam@example.com", "password": "nope"})
    assert bad.status_code == 401 and "Incorrect email or password" in bad.text
    other.get("/login")
    ok = other.post("/login", {"email": "SWAYAM@example.com", "password": "long enough 1"})
    assert ok.status_code == 303 and ok.headers["location"] == "/today"


def test_duplicate_email_and_rate_limit(make_browser, browser):
    b = make_browser()
    b.get("/register")
    assert b.post("/register", {"name": "X", "email": "swayam@example.com", "password": "long enough 1"}).status_code == 409
    for _ in range(10):
        b.get("/login")
        b.post("/login", {"email": "swayam@example.com", "password": "wrong"})
    b.get("/login")
    assert b.post("/login", {"email": "swayam@example.com", "password": "long enough 1"}).status_code == 429


def test_security_headers(browser):
    r = browser.get("/today")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert browser.get("/static/htmx.min.js").status_code == 200


# --- tasks --------------------------------------------------------------------------------


def test_add_task_plain_form_and_htmx(app, browser):
    r = browser.post("/tasks", {"title": "Write report", "area": " Writing ", "priority": "1", "estimate_min": "90"})
    assert r.status_code == 303
    r = browser.post("/tasks", {"title": "Plan sprint", "when": "backlog"}, htmx=True)
    assert r.status_code == 200 and 'id="tasks"' in r.text and "Write report" in r.text
    t1, t2 = tasks(app)
    assert (t1.area, t1.priority, t1.estimate_min, t1.planned_for is not None) == ("writing", 1, 90, True)
    assert t2.planned_for is None  # backlog


def test_task_lifecycle(app, browser):
    browser.post("/tasks", {"title": "Ship it", "when": "backlog"})
    tid = tasks(app)[0].id
    browser.post(f"/tasks/{tid}/status", {"status": "doing"}, htmx=True)
    t = tasks(app)[0]
    assert t.status == "doing" and t.planned_for is not None  # starting pulls it into today
    browser.post(f"/tasks/{tid}/status", {"status": "done"}, htmx=True)
    assert tasks(app)[0].completed_at is not None
    browser.post(f"/tasks/{tid}/status", {"status": "todo"}, htmx=True)
    assert tasks(app)[0].completed_at is None
    r = browser.post(f"/tasks/{tid}/update", {"title": "Ship v2", "area": "", "priority": "3", "estimate_min": "45", "due_date": "2030-01-02"}, htmx=True)
    assert "Ship v2" in r.text
    assert browser.post(f"/tasks/{tid}/delete", htmx=True).status_code == 200
    assert tasks(app) == []


def test_task_validation_surfaces_as_toast(browser):
    r = browser.post("/tasks", {"title": "   "}, htmx=True)
    assert r.status_code == 422 and r.headers["hx-reswap"] == "none"
    assert "can't be empty" in json.loads(r.headers["hx-trigger"])["app-error"]
    r = browser.post("/tasks", {"title": "x", "priority": "high"}, htmx=True)
    assert r.status_code == 422
    r = browser.post("/tasks", {"title": "   "})
    assert r.status_code == 422 and "be empty" in r.text  # full error page without HTMX (apostrophe is escaped)


def test_user_content_is_escaped(browser):
    browser.post("/tasks", {"title": '<script>alert("x")</script>'})
    page = browser.get("/today").text
    assert "<script>alert" not in page and "&lt;script&gt;alert" in page


def test_csrf_is_required(app, browser):
    assert browser.post("/tasks", {"title": "x"}, csrf=False).status_code == 403
    assert browser.c.post("/tasks", data={"title": "x"}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert browser.c.post("/tasks", data={"title": "ok"}, headers={"X-CSRF-Token": browser.token, "HX-Request": "true"}).status_code == 200
    assert [t.title for t in tasks(app)] == ["ok"]


def test_users_are_isolated(app, browser, make_browser):
    browser.post("/tasks", {"title": "Mine"})
    tid = tasks(app)[0].id
    other = make_browser().register(email="bob@example.com", name="Bob")
    assert "Mine" not in other.get("/today").text
    assert other.post(f"/tasks/{tid}/status", {"status": "done"}).status_code == 404
    assert other.post(f"/tasks/{tid}/delete").status_code == 404
    assert tasks(app)[0].status == "todo"


# --- log, blockers, check-in -------------------------------------------------------------------


def test_work_log(app, browser):
    r = browser.post("/log", {"kind": "win", "text": "Closed the big deal", "minutes": "40"}, htmx=True)
    assert 'id="log"' in r.text and "Closed the big deal" in r.text
    assert browser.post("/log", {"kind": "rant", "text": "x"}, htmx=True).status_code == 422
    with app.state.sessionmaker() as db:
        entry = db.scalar(select(LogEntry))
    assert (entry.kind, entry.minutes) == ("win", 40)
    browser.post(f"/log/{entry.id}/delete", htmx=True)
    with app.state.sessionmaker() as db:
        assert db.scalar(select(LogEntry)) is None


def test_blockers_open_resolve_reopen(app, browser):
    browser.post("/blockers", {"text": "Waiting for API keys"}, htmx=True)
    with app.state.sessionmaker() as db:
        bid = db.scalar(select(Blocker.id))
    r = browser.post(f"/blockers/{bid}/resolve", htmx=True)
    assert "<s>Waiting for API keys</s>" in r.text
    browser.post(f"/blockers/{bid}/resolve", htmx=True)  # reopen
    with app.state.sessionmaker() as db:
        assert db.get(Blocker, bid).resolved_on is None


def test_checkin_upserts_and_validates(app, browser):
    browser.post("/checkin", {"energy": "4", "mood": "5", "focus_hours": "3.3"}, htmx=True)
    r = browser.post("/checkin", {"energy": "2", "mood": "3", "focus_hours": "2"}, htmx=True)
    assert "saved ✓" in r.text
    with app.state.sessionmaker() as db:
        rows = list(db.scalars(select(Checkin)))
    assert len(rows) == 1 and (rows[0].energy, rows[0].focus_hours) == (2, 2.0)
    assert browser.post("/checkin", {"energy": "9", "mood": "3", "focus_hours": "1"}, htmx=True).status_code == 422
