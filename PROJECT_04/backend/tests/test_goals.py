from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Checkin, Goal, Milestone
from tests.conftest import create_goal

_TOGGLE = re.compile(r'action="/milestones/(\d+)/toggle"')


def _milestone_ids(browser, goal_id):
    return [int(x) for x in _TOGGLE.findall(browser.get(f"/goals/{goal_id}").text)]


def test_create_and_view_goal(browser):
    goal_id = create_goal(browser, "Ship the portfolio", "career", (date.today() + timedelta(days=30)).isoformat(), "Get hired")
    r = browser.get(f"/goals/{goal_id}")
    assert r.status_code == 200
    assert "Ship the portfolio" in r.text
    assert "No actions yet" in r.text
    assert "Get hired" in r.text


def test_goal_validation(browser):
    r = browser.post("/goals", {"title": "x", "category": "health"})
    assert r.status_code == 422
    r = browser.post("/goals", {"title": "A real goal", "category": "nonsense"})
    assert r.status_code == 422
    r = browser.post("/goals", {"title": "A real goal", "category": "health", "target_date": "not-a-date"})
    assert r.status_code == 422


def test_other_users_goal_is_invisible(make_browser):
    a = make_browser().register("a@example.com", "A")
    b = make_browser().register("b@example.com", "B")
    goal_id = create_goal(a, "Private goal")
    assert b.get(f"/goals/{goal_id}").status_code == 404
    assert b.post(f"/goals/{goal_id}/update", {"title": "Stolen", "category": "health"}).status_code == 404
    assert b.post(f"/goals/{goal_id}/delete").status_code == 404


def test_weighted_milestone_progress(browser):
    goal_id = create_goal(browser)
    browser.post(f"/goals/{goal_id}/milestones", {"title": "Small", "weight": "1"})
    browser.post(f"/goals/{goal_id}/milestones", {"title": "Big", "weight": "4"})
    r = browser.get(f"/goals/{goal_id}")
    assert "0%" in r.text
    first, second = _milestone_ids(browser, goal_id)
    browser.post(f"/milestones/{first}/toggle")
    r = browser.get(f"/goals/{goal_id}")
    assert "20%" in r.text  # weight 1 of 5
    browser.post(f"/milestones/{second}/toggle")
    r = browser.get(f"/goals/{goal_id}")
    assert "100%" in r.text


def test_milestone_delete_and_validation(browser):
    goal_id = create_goal(browser)
    r = browser.post(f"/goals/{goal_id}/milestones", {"title": "", "weight": "1"})
    assert r.status_code == 422
    browser.post(f"/goals/{goal_id}/milestones", {"title": "Only one", "weight": "9"})
    detail = browser.get(f"/goals/{goal_id}")
    mid = int(detail.text.split('action="/milestones/')[1].split('/')[0])
    browser.post(f"/milestones/{mid}/delete")
    assert "No open milestones" in browser.get(f"/goals/{goal_id}").text or "Only one" not in browser.get(f"/goals/{goal_id}").text


def test_checkin_upserts_today(browser, app):
    goal_id = create_goal(browser)
    browser.post(f"/goals/{goal_id}/checkins", {"confidence": "4", "note": "Feeling good"})
    browser.post(f"/goals/{goal_id}/checkins", {"confidence": "2", "note": "Actually blocked"})
    with app.state.sessionmaker() as db:
        rows = db.scalars(select(Checkin).where(Checkin.goal_id == goal_id)).all()
        assert len(rows) == 1
        assert rows[0].confidence == 2
        assert rows[0].note == "Actually blocked"
    assert "Actually blocked" in browser.get(f"/goals/{goal_id}").text


def test_goal_status_and_filters(browser):
    goal_id = create_goal(browser)
    browser.post(f"/goals/{goal_id}/status", {"status": "achieved"})
    assert "Ship the portfolio" not in browser.get("/").text
    r = browser.get("/goals?status=achieved")
    assert "Run a half marathon" in r.text
    browser.post(f"/goals/{goal_id}/status", {"status": "active"})
    assert "Run a half marathon" in browser.get("/").text


def test_edit_goal(browser):
    goal_id = create_goal(browser)
    r = browser.post(f"/goals/{goal_id}/update", {"title": "Renamed goal", "category": "learning", "target_date": "", "why": "new why", "description": ""})
    assert r.status_code == 303
    assert "Renamed goal" in browser.get(f"/goals/{goal_id}").text


def test_delete_goal_cascades(browser, app):
    goal_id = create_goal(browser)
    browser.post(f"/goals/{goal_id}/milestones", {"title": "One", "weight": "2"})
    browser.post(f"/goals/{goal_id}/checkins", {"confidence": "3", "note": "x"})
    browser.post(f"/goals/{goal_id}/delete")
    assert browser.get(f"/goals/{goal_id}").status_code == 404
    with app.state.sessionmaker() as db:
        assert db.scalar(select(Goal.id).where(Goal.id == goal_id)) is None
        assert db.scalar(select(Milestone.id).where(Milestone.goal_id == goal_id)) is None
        assert db.scalar(select(Checkin.id).where(Checkin.goal_id == goal_id)) is None


def test_export_contains_goal_data(browser):
    goal_id = create_goal(browser)
    browser.post(f"/goals/{goal_id}/milestones", {"title": "Milestone A", "weight": "3"})
    r = browser.get("/settings/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "Run a half marathon" in r.text
    assert "Milestone A" in r.text
