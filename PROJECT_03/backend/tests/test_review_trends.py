import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import anthropic
import httpx2
import pytest
from sqlalchemy import select

from app.models import Blocker, Checkin, Review, Task, User
from app.routes.review import ai_client
from app.services import charts, planner, trends
from app.timeutil import local_today

IST = ZoneInfo("Asia/Kolkata")
TODAY = local_today(IST)
TOMORROW = TODAY + timedelta(days=1)


def db_tasks(app):
    with app.state.sessionmaker() as db:
        return {t.title: t for t in db.scalars(select(Task))}


def add(browser, title, **form):
    r = browser.post("/tasks", {"title": title, **{k: str(v) for k, v in form.items()}})
    assert r.status_code == 303


# --- planner (unit) --------------------------------------------------------------------------


def make_task(i, priority=2, est=30, carry=0, due=None, status="todo", planned=TODAY, age=0):
    return Task(
        id=i, user_id=1, title=f"t{i}", priority=priority, estimate_min=est, carry_count=carry, due_date=due,
        status=status, planned_for=planned, created_at=datetime.now(timezone.utc) - timedelta(days=age),
    )


def test_scoring_reasons_and_order():
    tasks = [make_task(1, priority=3), make_task(2, priority=1), make_task(3, priority=2, due=TODAY - timedelta(days=2)), make_task(4, carry=3, status="doing")]
    items, load, over = planner.build_plan(tasks, 600, TOMORROW)
    assert [i.task_id for i in items][:2] == [3, 4]  # overdue beats plain P1; carried + in progress next
    assert "overdue by 3 days" in items[0].reasons
    assert "carried over 3×" in items[1].reasons and "already in progress" in items[1].reasons
    assert load == 120 and not over


def test_plan_respects_capacity_and_flags_oversized_work():
    tasks = [make_task(1, priority=1, est=240), make_task(2, est=120), make_task(3, est=90)]
    items, load, _ = planner.build_plan(tasks, 360, TOMORROW)
    assert [i.task_id for i in items] == [1, 2] and load == 360
    items, load, over = planner.build_plan([make_task(9, est=600)], 360, TOMORROW)
    assert [i.task_id for i in items] == [9] and over


def test_preferred_order_is_used_but_capacity_still_applies():
    tasks = [make_task(1, priority=1, est=200), make_task(2, priority=3, est=200)]
    items, _, _ = planner.build_plan(tasks, 300, TOMORROW, preferred_order=[2, 99])
    assert [i.task_id for i in items] == [2]


def test_parse_decision():
    assert planner.parse_decision("drop", TODAY) == "drop"
    assert planner.parse_decision((TODAY + timedelta(days=5)).isoformat(), TODAY) == TODAY + timedelta(days=5)
    assert planner.parse_decision(TODAY.isoformat(), TODAY) == "carry"  # not in the future
    assert planner.parse_decision("garbage", TODAY) == "carry"


# --- review flow ---------------------------------------------------------------------------


def test_rule_review_triage_and_commit(app, browser):
    add(browser, "Finish deck", priority=1, estimate_min=60)
    add(browser, "Email vendor")
    add(browser, "Old idea")
    add(browser, "Big refactor", estimate_min=120)
    t = db_tasks(app)
    browser.post(f"/tasks/{t['Finish deck'].id}/status", {"status": "done"})
    browser.post("/log", {"kind": "win", "text": "Client said yes"})
    later = (TODAY + timedelta(days=4)).isoformat()

    browser.get("/review")
    r = browser.post(
        "/review/generate",
        {f"decision_{t['Email vendor'].id}": "carry", f"decision_{t['Old idea'].id}": "drop",
         f"decision_{t['Big refactor'].id}": "later", f"later_{t['Big refactor'].id}": later},
    )
    assert r.status_code == 303
    page = browser.get("/review").text
    assert "Rule-based review" in page and "Client said yes" in page and "Email vendor" in page

    with app.state.sessionmaker() as db:
        review = db.scalar(select(Review))
    assert review.source == "rule" and [i["title"] for i in review.plan["items"]] == ["Email vendor"]
    assert review.plan["carried_ids"] == [t["Email vendor"].id]

    browser.post("/review/commit", {"notes": "Good day"})
    browser.get("/review")
    browser.post("/review/commit", {"notes": "Good day, really"})  # committing twice must not double-count
    t = db_tasks(app)
    assert t["Old idea"].status == "dropped"
    assert t["Email vendor"].planned_for == TOMORROW and t["Email vendor"].carry_count == 1
    assert t["Big refactor"].planned_for == date.fromisoformat(later) and t["Big refactor"].carry_count == 0
    assert "Plan committed" in browser.get("/review").text


def test_commit_without_review_is_rejected(browser):
    assert browser.post("/review/commit").status_code == 409


def test_regeneration_is_rate_limited(browser):
    browser.get("/review")
    assert browser.post("/review/generate").status_code == 303
    assert browser.post("/review/generate").status_code == 429


class FakeMessages:
    def __init__(self, outcome):
        self.outcome, self.calls = outcome, []

    def create(self, **kw):
        self.calls.append(kw)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def reply(payload, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=payload if isinstance(payload, str) else json.dumps(payload))], stop_reason=stop, model="claude-opus-5-5")


@pytest.fixture
def with_ai(app, settings):
    settings.anthropic_api_key = "sk-test-not-real"

    def install(outcome):
        m = FakeMessages(outcome)
        app.dependency_overrides[ai_client] = lambda: SimpleNamespace(beta=SimpleNamespace(messages=m))
        return m

    yield install
    app.dependency_overrides.clear()


def test_ai_review_orders_plan_but_cannot_invent_tasks(app, browser, with_ai):
    add(browser, "Write tests", priority=1)
    add(browser, "Tidy docs", priority=3)
    t = db_tasks(app)
    m = with_ai(reply({
        "headline": "Steady day", "recap": "You kept things moving.", "wins": ["Shipped"], "blockers": [],
        "tomorrow_focus": [{"task_id": t["Tidy docs"].id, "why": "Quick win first"}, {"task_id": 9999, "why": "invented"}],
        "reflection_question": "What helped?",
    }))
    browser.get("/review")
    browser.post("/review/generate")
    with app.state.sessionmaker() as db:
        review = db.scalar(select(Review))
    assert review.source == "ai" and review.model == "claude-opus-5-5"
    assert [i["title"] for i in review.plan["items"]] == ["Tidy docs", "Write tests"]
    assert [f["task_id"] for f in review.content["tomorrow_focus"]] == [t["Tidy docs"].id]
    call = m.calls[0]
    assert call["output_config"]["effort"] == "low" and call["fallbacks"] == "default"
    sent = json.loads(call["messages"][0]["content"])
    assert {c["task_id"] for c in sent["candidates"]} == {t["Write tests"].id, t["Tidy docs"].id}
    assert "✦ Written by Claude" in browser.get("/review").text


@pytest.mark.parametrize(
    "outcome, expected",
    [
        (reply("not json"), "unexpected format"),
        (reply({"headline": "x"}), "incomplete review"),
        (reply({"headline": "x"}, stop="refusal"), "declined"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")), "could not be reached"),
    ],
)
def test_ai_failures_fall_back_to_rules(app, browser, with_ai, outcome, expected):
    add(browser, "Something")
    with_ai(outcome)
    browser.get("/review")
    browser.post("/review/generate")
    with app.state.sessionmaker() as db:
        review = db.scalar(select(Review))
    assert review.source == "rule" and expected in review.note
    assert [i["title"] for i in review.plan["items"]] == ["Something"]


# --- trends, history, settings -------------------------------------------------------------------


def seed_week(app):
    with app.state.sessionmaker() as db:
        user = db.scalar(select(User))
        for back in range(7):
            day = TODAY - timedelta(days=back)
            noon = datetime(day.year, day.month, day.day, 12, tzinfo=IST).astimezone(timezone.utc)
            for i in range(back % 3):
                db.add(Task(user_id=user.id, title=f"d{back}-{i}", area="writing" if i else "code", estimate_min=60, status="done", completed_at=noon))
            db.add(Checkin(user_id=user.id, day=day, energy=3 + back % 2, mood=4, focus_hours=2.5))
            db.add(Review(user_id=user.id, day=day, source="rule", content={"headline": f"day {back}", "recap": "", "wins": [], "blockers": [], "tomorrow_focus": [], "reflection_question": "?"},
                          plan={"items": [], "carried_ids": [1] if back == 1 else []}, committed=back != 0))
        db.add(Blocker(user_id=user.id, text="Waiting for legal review", opened_on=TODAY - timedelta(days=6), resolved_on=TODAY - timedelta(days=5)))
        db.add(Blocker(user_id=user.id, text="Waiting for legal review again", opened_on=TODAY - timedelta(days=2)))
        db.commit()


def test_trend_maths_in_local_days(app, browser):
    seed_week(app)
    with app.state.sessionmaker() as db:
        user = db.scalar(select(User))
        t = trends.compute(db, user, IST, TODAY, 7)
    assert t.completed == [(6 - i) % 3 for i in range(7)]
    assert t.total_completed == sum(b % 3 for b in range(7))
    assert t.carried == [0, 0, 0, 0, 0, 1, 0]
    assert t.focus == [2.5] * 7
    assert t.streak == 6  # yesterday back six days; today's review isn't committed
    assert t.completion_rate == round(100 * t.total_completed / (t.total_completed + 1))
    assert dict(t.area_minutes)["code"] > 0


def test_rest_days_do_not_break_the_streak(app, browser):
    with app.state.sessionmaker() as db:
        user = db.scalar(select(User))
        empty = {"headline": "", "recap": "", "wins": [], "blockers": [], "tomorrow_focus": [], "reflection_question": "?"}
        for back in (1, 4, 5):  # reviews on these days; days 2-3 are a quiet weekend
            db.add(Review(user_id=user.id, day=TODAY - timedelta(days=back), source="rule", content=empty, plan={}, committed=True))
        db.commit()
        assert trends.review_streak(db, user, IST, TODAY) == 3
        # Activity on day 2 without a review breaks it.
        db.add(Checkin(user_id=user.id, day=TODAY - timedelta(days=2), energy=3, mood=3, focus_hours=1))
        db.commit()
        assert trends.review_streak(db, user, IST, TODAY) == 1


def test_trends_history_and_settings_pages(app, browser):
    seed_week(app)
    page = browser.get("/trends").text
    assert page.count("<svg") == 3 and "Tasks completed per day" in page and "day review streak" in page
    assert "Waiting for legal review" in page  # recurring blocker theme
    assert browser.get("/trends?span=14").status_code == 200
    hist = browser.get("/history").text
    assert "day 1" in hist and "not committed" in hist
    assert "day 2" in browser.get(f"/history/{TODAY - timedelta(days=2)}").text
    assert browser.get("/history/2001-01-01").status_code == 404
    r = browser.post("/settings", {"name": "Swayam", "timezone": "Europe/London", "capacity_hours": "5"})
    assert r.status_code == 303
    assert browser.post("/settings", {"name": "Swayam", "timezone": "Mars/Base", "capacity_hours": "5"}).status_code == 422
    with app.state.sessionmaker() as db:
        assert db.scalar(select(User)).capacity_hours == 5


def test_charts_render_accessible_svg():
    svg = str(charts.bar_chart("Done <per> day", ["Mon", "Tue"], [1, 3]))
    assert svg.count("<rect") == 2 and "<title>Done &lt;per&gt; day</title>" in svg and 'class="bar now"' in svg
    line = str(charts.line_chart("Energy", ["a", "b", "c"], [("Energy", [3, None, 5], "energy")], max_v=5))
    assert line.count("<circle") == 2 and "M" in line


def test_migrations_match_models(migrated_db):
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    from app.db import Base

    engine = create_engine(f"sqlite:///{migrated_db.as_posix()}")
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    engine.dispose()
