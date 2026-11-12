from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.models import Goal, Milestone
from app.services import goalmath
from tests.conftest import create_goal

TOGGLE = 'action="/milestones/{}/toggle"'


def _milestone_id(browser, goal_id):
    text = browser.get(f"/goals/{goal_id}").text
    marker = 'action="/milestones/'
    chunk = text.split(marker)[1]
    return int(chunk.split("/")[0])


def test_insights_page_has_real_charts(browser):
    goal_id = create_goal(browser, "Learn Spanish", "learning")
    browser.post(f"/goals/{goal_id}/milestones", {"title": "First conversation", "weight": "3"})
    r = browser.get("/insights")
    assert r.status_code == 200
    assert "<svg" in r.text
    assert "Completed actions" in r.text
    assert "Goal health" in r.text
    assert "Learn Spanish" in r.text


def test_goal_review_page(browser):
    goal_id = create_goal(browser, "Write a novel", "creative", "", "Finish the draft")
    r = browser.get(f"/goals/{goal_id}/review")
    assert r.status_code == 200
    assert "Write a novel" in r.text
    assert "Generated from Summit" in r.text


def test_local_coach_creates_actions(browser, app):
    goal_id = create_goal(browser, "Ship the portfolio", "career")
    browser.post(f"/goals/{goal_id}/milestones", {"title": "Draft case studies", "weight": "3"})
    browser.post(f"/goals/{goal_id}/milestones", {"title": "Deploy the site", "weight": "2"})
    r = browser.post(f"/goals/{goal_id}/coach")
    assert r.status_code == 303
    assert "source=local" in r.headers["location"]
    assert "planned=" in r.headers["location"]
    detail = browser.get(f"/goals/{goal_id}")
    assert "local planner" in detail.text or "Added" in detail.text
    assert "Advance: Draft case studies" in detail.text
    assert "coach" in detail.text
    with app.state.sessionmaker() as db:
        from sqlalchemy import select

        from app.models import WeeklyAction

        rows = db.scalars(select(WeeklyAction).where(WeeklyAction.goal_id == goal_id, WeeklyAction.source == "coach")).all()
        assert 3 <= len(rows) <= 5


def test_coach_is_rate_limited(browser):
    goal_id = create_goal(browser)
    codes = [browser.post(f"/goals/{goal_id}/coach").status_code for _ in range(7)]
    assert 429 in codes[6:]


def test_pace_math():
    today = date(2026, 11, 12)
    goal = Goal(
        title="x",
        user_id=1,
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        target_date=today + timedelta(days=10),
        status="active",
    )
    goal.milestones = [
        Milestone(title="done", weight=1, status="done", position=1),
        Milestone(title="open", weight=3, status="open", position=2),
    ]
    assert goalmath.progress(goal) == 25
    p = goalmath.pace(goal, today)
    assert 80 <= p["expected"] <= 100
    assert p["state"] == "behind"
    assert goalmath.is_at_risk(goal, today)


def test_ahead_and_overdue():
    today = date(2026, 11, 12)
    ahead = Goal(title="a", user_id=1, created_at=datetime(2026, 11, 1, tzinfo=timezone.utc), target_date=today + timedelta(days=60), status="active")
    ahead.milestones = [Milestone(title="d", weight=5, status="done", position=1)]
    assert goalmath.pace(ahead, today)["state"] == "ahead"
    late = Goal(title="b", user_id=1, created_at=datetime(2026, 9, 1, tzinfo=timezone.utc), target_date=today - timedelta(days=2), status="active")
    late.milestones = [Milestone(title="o", weight=1, status="open", position=1)]
    assert goalmath.pace(late, today)["state"] == "overdue"
    assert goalmath.is_at_risk(late, today)


def test_ai_fallback_is_labelled(monkeypatch):
    from app.config import Settings
    from app.services import ai

    class Boom:
        def __init__(self, *a, **kw):
            raise RuntimeError("network down")

    import app.services.ai as module

    monkeypatch.setattr(module.httpx, "Client", Boom)
    goal = Goal(title="g", user_id=1, description="", why="", category="personal", status="active", created_at=datetime.now(timezone.utc))
    goal.milestones = [Milestone(id=7, title="m", weight=2, status="open", position=1)]
    result = ai.plan(Settings(_env_file=None, anthropic_api_key="test-key"), goal, goal.milestones, [], date.today(), date.today())
    assert result.source == "local"
    assert "unavailable" in result.note
    assert result.suggestions


def test_ai_output_validation_rejects_invented_ids():
    from app.services.ai import _validate

    with_ids = _validate(
        {
            "actions": [
                {"title": "Valid step", "rationale": "Because", "estimate_min": 30, "milestone_id": 99},
                {"title": "Second step", "rationale": "Also because", "estimate_min": 20, "milestone_id": 1},
            ]
        },
        {1},
    )
    assert with_ids[0].milestone_id is None
    assert with_ids[1].milestone_id == 1
    try:
        _validate({"actions": [{"title": "x", "rationale": "y"}]}, set())
    except ValueError:
        pass
    else:
        raise AssertionError("short plan should be rejected")
