from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.models import WeeklyAction
from tests.conftest import create_goal


def _week(browser):
    r = browser.get("/weekly")
    val = r.text.split('name="week_start" value="')[1].split('"')[0]
    return val


def test_create_action_and_capacity(browser):
    goal_id = create_goal(browser)
    week = _week(browser)
    r = browser.post("/weekly/actions", {"title": "Draft chapter one", "goal_id": goal_id, "estimate_min": "60", "week_start": week})
    assert r.status_code == 303
    r = browser.get("/weekly")
    assert "Draft chapter one" in r.text
    assert "1h" in r.text or "60m" in r.text


def test_action_validation(browser):
    goal_id = create_goal(browser)
    week = _week(browser)
    assert browser.post("/weekly/actions", {"title": "x", "goal_id": goal_id, "estimate_min": "30", "week_start": week}).status_code == 422
    assert browser.post("/weekly/actions", {"title": "Valid action", "goal_id": 999, "estimate_min": "30", "week_start": week}).status_code == 404


def test_milestone_must_belong_to_goal(browser):
    g1 = create_goal(browser, "Goal one")
    g2 = create_goal(browser, "Goal two")
    browser.post(f"/goals/{g1}/milestones", {"title": "Only in one", "weight": "1"})
    mid = int(browser.get(f"/goals/{g1}").text.split('action="/milestones/')[1].split('/')[0])
    r = browser.post("/weekly/actions", {"title": "Wrong link", "goal_id": g2, "milestone_id": mid, "estimate_min": "30", "week_start": _week(browser)})
    assert r.status_code == 422


def test_toggle_action_and_htmx_partial(browser, app):
    goal_id = create_goal(browser)
    browser.post("/weekly/actions", {"title": "Toggle me", "goal_id": goal_id, "estimate_min": "30", "week_start": _week(browser)})
    with app.state.sessionmaker() as db:
        action_id = db.scalar(select(WeeklyAction.id).where(WeeklyAction.title == "Toggle me"))
    r = browser.post(f"/weekly/actions/{action_id}/toggle", htmx=True)
    assert r.status_code == 200
    assert 'aria-pressed="true"' in r.text
    assert "action-" in r.text
    with app.state.sessionmaker() as db:
        assert db.get(WeeklyAction, action_id).status == "done"
    browser.post(f"/weekly/actions/{action_id}/toggle", htmx=True)
    with app.state.sessionmaker() as db:
        assert db.get(WeeklyAction, action_id).status == "open"


def test_action_isolation(make_browser, app):
    a = make_browser().register("a@example.com", "A")
    b = make_browser().register("b@example.com", "B")
    gid = create_goal(a)
    a.post("/weekly/actions", {"title": "Private action", "goal_id": gid, "estimate_min": "30", "week_start": _week(a)})
    with app.state.sessionmaker() as db:
        action_id = db.scalar(select(WeeklyAction.id).where(WeeklyAction.title == "Private action"))
    assert b.post(f"/weekly/actions/{action_id}/toggle").status_code == 404
    assert b.post(f"/weekly/actions/{action_id}/delete").status_code == 404


def test_delete_action(browser, app):
    goal_id = create_goal(browser)
    browser.post("/weekly/actions", {"title": "Delete me", "goal_id": goal_id, "estimate_min": "30", "week_start": _week(browser)})
    with app.state.sessionmaker() as db:
        action_id = db.scalar(select(WeeklyAction.id).where(WeeklyAction.title == "Delete me"))
    browser.post(f"/weekly/actions/{action_id}/delete")
    with app.state.sessionmaker() as db:
        assert db.get(WeeklyAction, action_id) is None


def test_carry_unfinished_from_last_week(browser, app):
    goal_id = create_goal(browser)
    last_week = (date.today() - timedelta(days=7)).isoformat()
    browser.post("/weekly/actions", {"title": "Carry me", "goal_id": goal_id, "estimate_min": "30", "week_start": last_week})
    browser.post("/weekly/actions", {"title": "Finished", "goal_id": goal_id, "estimate_min": "30", "week_start": last_week})
    with app.state.sessionmaker() as db:
        done_id = db.scalar(select(WeeklyAction.id).where(WeeklyAction.title == "Finished"))
    browser.post(f"/weekly/actions/{done_id}/toggle")
    week = _week(browser)
    r = browser.post("/weekly/carry", {"week_start": week})
    assert r.status_code == 303
    assert "carried=1" in r.headers["location"]
    r = browser.get("/weekly")
    assert "Carry me" in r.text
    assert "Finished" not in r.text


def test_previous_and_next_week_navigation(browser):
    r = browser.get("/weekly?week=not-a-date")
    assert r.status_code == 200
    r = browser.get("/weekly?week=2026-01-07")
    assert r.status_code == 200
    assert "Jan 2026" in r.text
