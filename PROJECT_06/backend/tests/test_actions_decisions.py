from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.models import ActionItem, Decision
from conftest import create_meeting, today_local

DECISION_ONLY = "We agreed to ship the beta on 1 December."


def quiet_meeting(browser, title="Planning"):
    return create_meeting(browser, title=title, attendees="", notes=DECISION_ONLY)


def add_action(browser, meeting_id, title="Send the deck", owner="Priya", due=""):
    return browser.post(f"/meetings/{meeting_id}/actions", {"title": title, "owner": owner, "due_date": due})


def actions(app):
    with app.state.sessionmaker() as db:
        return list(db.scalars(select(ActionItem)))


def action(app, action_id):
    with app.state.sessionmaker() as db:
        return db.get(ActionItem, action_id)


def decisions(app):
    with app.state.sessionmaker() as db:
        return list(db.scalars(select(Decision).order_by(Decision.id)))


def test_add_action_stores_owner_and_due_date(browser, app):
    meeting_id = quiet_meeting(browser)
    due = today_local() + timedelta(days=5)
    r = add_action(browser, meeting_id, "Send the deck", "Priya", due.isoformat())
    assert r.status_code == 303
    row = actions(app)[0]
    assert (row.title, row.owner, row.due_date, row.status) == ("Send the deck", "Priya", due, "open")


def test_add_action_accepts_relative_due_dates(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id, due="tomorrow")
    assert actions(app)[0].due_date == today_local() + timedelta(days=1)


def test_add_action_rejects_a_short_title(browser, app):
    meeting_id = quiet_meeting(browser)
    r = add_action(browser, meeting_id, title="ab")
    assert r.status_code == 303
    assert "error=action" in r.headers["location"]
    assert actions(app) == []


def test_add_action_requires_csrf(browser, app):
    meeting_id = quiet_meeting(browser)
    r = browser.post(f"/meetings/{meeting_id}/actions", {"title": "Send the deck"}, csrf=False)
    assert r.status_code == 403
    assert actions(app) == []


def test_toggle_action_completes_and_reopens(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id)
    action_id = actions(app)[0].id
    r = browser.post(f"/actions/{action_id}/toggle", {"next": "/actions"})
    assert r.status_code == 303
    done = action(app, action_id)
    assert done.status == "done"
    assert done.completed_at is not None
    browser.post(f"/actions/{action_id}/toggle", {"next": "/actions"})
    reopened = action(app, action_id)
    assert reopened.status == "open"
    assert reopened.completed_at is None


def test_update_action_changes_its_fields(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id)
    action_id = actions(app)[0].id
    due = today_local() + timedelta(days=2)
    r = browser.post(
        f"/actions/{action_id}/update",
        {"title": "Send the revised deck", "owner": "Arjun", "due_date": due.isoformat(), "next": "/actions"},
    )
    assert r.status_code == 303
    row = action(app, action_id)
    assert (row.title, row.owner, row.due_date) == ("Send the revised deck", "Arjun", due)


def test_update_action_ignores_an_invalid_title(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id, title="Keep this title")
    action_id = actions(app)[0].id
    browser.post(f"/actions/{action_id}/update", {"title": "x", "owner": "", "due_date": "", "next": "/actions"})
    assert action(app, action_id).title == "Keep this title"


def test_delete_action_removes_it(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id)
    action_id = actions(app)[0].id
    r = browser.post(f"/actions/{action_id}/delete", {"next": "/actions"})
    assert r.status_code == 303
    assert action(app, action_id) is None


def test_next_target_cannot_become_an_open_redirect(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id)
    action_id = actions(app)[0].id
    for hostile in ["//evil.example", "https://evil.example", "/\\evil.example", ""]:
        r = browser.post(f"/actions/{action_id}/toggle", {"next": hostile})
        assert r.status_code == 303
        assert r.headers["location"] == "/actions"


def test_next_target_allows_a_same_site_path(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id)
    action_id = actions(app)[0].id
    r = browser.post(f"/actions/{action_id}/toggle", {"next": f"/meetings/{meeting_id}#actions"})
    assert r.headers["location"] == f"/meetings/{meeting_id}#actions"


def test_actions_page_groups_by_due_date(browser, app):
    meeting_id = quiet_meeting(browser)
    today = today_local()
    add_action(browser, meeting_id, title="Overdue task", due=(today - timedelta(days=2)).isoformat())
    add_action(browser, meeting_id, title="Today task", due=today.isoformat())
    add_action(browser, meeting_id, title="Soon task", due=(today + timedelta(days=3)).isoformat())
    add_action(browser, meeting_id, title="Later task", due=(today + timedelta(days=30)).isoformat())
    add_action(browser, meeting_id, title="Undated task", due="")
    page = browser.get("/actions").text
    for label in ["OVERDUE", "TODAY", "THIS WEEK", "LATER", "NO DATE"]:
        assert label in page
    for title in ["Overdue task", "Today task", "Soon task", "Later task", "Undated task"]:
        assert title in page


def test_actions_page_done_filter(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id, title="Finished task")
    add_action(browser, meeting_id, title="Still open")
    action_id = actions(app)[0].id
    browser.post(f"/actions/{action_id}/toggle", {"next": "/actions"})
    page = browser.get("/actions?status=done").text
    assert "Finished task" in page
    assert "Still open" not in page
    assert "COMPLETED" in page


def test_actions_owner_filter(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id, title="Priya task", owner="Priya")
    add_action(browser, meeting_id, title="Arjun task", owner="Arjun")
    page = browser.get("/actions?owner=Priya").text
    assert "Priya task" in page
    assert "Arjun task" not in page


def test_empty_actions_page_is_clear(make_browser):
    b = make_browser().register()
    page = b.get("/actions").text
    assert "No open follow-ups" in page


def test_unassigned_action_uses_a_small_pill(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id, title="Follow up with legal", owner="")
    page = browser.get("/actions").text
    assert "Follow up with legal" in page
    assert 'class="owner-pill unassigned"' in page


def test_add_decision_appears_in_the_log(browser, app):
    meeting_id = quiet_meeting(browser)
    r = browser.post(f"/meetings/{meeting_id}/decisions", {"text": "Hire a designer", "status": "revisit"})
    assert r.status_code == 303
    rows = decisions(app)
    assert len(rows) == 2
    added = rows[-1]
    assert (added.text, added.status) == ("Hire a designer", "revisit")
    assert added.decided_on == today_local()
    assert "Hire a designer" in browser.get("/decisions").text


def test_add_decision_rejects_short_text(browser):
    meeting_id = quiet_meeting(browser)
    r = browser.post(f"/meetings/{meeting_id}/decisions", {"text": "no", "status": "agreed"})
    assert r.status_code == 303
    assert "error=decision" in r.headers["location"]


def test_decision_status_toggles(browser, app):
    meeting_id = quiet_meeting(browser)
    decision_id = decisions(app)[0].id
    browser.post(f"/decisions/{decision_id}/status")
    with app.state.sessionmaker() as db:
        assert db.get(Decision, decision_id).status == "revisit"
    browser.post(f"/decisions/{decision_id}/status")
    with app.state.sessionmaker() as db:
        assert db.get(Decision, decision_id).status == "agreed"


def test_delete_decision_removes_it(browser, app):
    meeting_id = quiet_meeting(browser)
    decision_id = decisions(app)[0].id
    r = browser.post(f"/decisions/{decision_id}/delete")
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        assert db.get(Decision, decision_id) is None


def test_decisions_search_and_filter(browser, app):
    meeting_id = quiet_meeting(browser)
    browser.post(f"/meetings/{meeting_id}/decisions", {"text": "Use Postgres for the ledger", "status": "agreed"})
    assert "Postgres" in browser.get("/decisions?q=Postgres").text
    assert "No decision matches" in browser.get("/decisions?q=zzzz").text
    revisit = browser.get("/decisions?status=revisit").text
    assert "No decisions recorded" in revisit or "Ship the beta" not in revisit


def test_actions_page_counts_open_and_done(browser, app):
    meeting_id = quiet_meeting(browser)
    add_action(browser, meeting_id, title="Task one")
    add_action(browser, meeting_id, title="Task two")
    first = actions(app)[0].id
    browser.post(f"/actions/{first}/toggle", {"next": "/actions"})
    page = browser.get("/actions").text
    assert 'Open <span>1</span>' in page
    assert 'Done <span>1</span>' in page


def test_another_account_cannot_touch_actions_or_decisions(make_browser, app):
    owner = make_browser().register()
    meeting_id = quiet_meeting(owner)
    add_action(owner, meeting_id)
    action_id = actions(app)[0].id
    decision_id = decisions(app)[0].id
    stranger = make_browser().register(email="stranger@example.com", name="Stranger")
    assert stranger.post(f"/actions/{action_id}/toggle", {"next": "/actions"}).status_code == 404
    assert stranger.post(f"/actions/{action_id}/update", {"title": "Hijacked"}).status_code == 404
    assert stranger.post(f"/actions/{action_id}/delete").status_code == 404
    assert stranger.post(f"/decisions/{decision_id}/status").status_code == 404
    assert stranger.post(f"/decisions/{decision_id}/delete").status_code == 404
    assert action(app, action_id).title != "Hijacked"
