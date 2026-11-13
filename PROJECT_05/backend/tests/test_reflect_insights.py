from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.models import Habit, HabitLog, Reflection, Suggestion
from app.services import ai, habitmath
from tests.conftest import create_habit, log_day, today_local


def test_reflect_page_has_prompts_and_form(browser):
    page = browser.get("/reflect")
    assert page.status_code == 200
    assert "Five minutes, honestly." in page.text
    assert "How did the week feel?" in page.text
    assert 'name="worked"' in page.text


def test_save_reflection(browser):
    day = today_local()
    r = browser.post(
        "/reflect",
        {"week": day.isoformat(), "mood": "4", "worked": "The walk held.", "friction": "Late nights.", "change": "Write before dinner."},
    )
    assert r.status_code == 303
    page = browser.get(r.headers["location"])
    assert "Reflection saved" in page.text
    assert "Write before dinner." in page.text


def test_saving_the_same_week_updates_instead_of_duplicating(browser, app):
    day = today_local()
    browser.post("/reflect", {"week": day.isoformat(), "mood": "3", "worked": "First", "friction": "", "change": ""})
    browser.post("/reflect", {"week": day.isoformat(), "mood": "5", "worked": "Second", "friction": "", "change": ""})
    with app.state.sessionmaker() as db:
        assert db.scalar(select(func.count()).select_from(Reflection)) == 1
        saved = db.scalar(select(Reflection))
        assert saved.worked == "Second"
        assert saved.mood == 5


def test_reflection_history_lists_past_weeks(browser):
    day = today_local()
    browser.post("/reflect", {"week": (day - timedelta(days=7)).isoformat(), "mood": "2", "worked": "", "friction": "Too much.", "change": "Drop one thing."})
    page = browser.get("/reflect")
    assert "Past reflections" in page.text
    assert "Drop one thing." in page.text


def test_reflect_week_navigation(browser):
    page = browser.get("/reflect")
    previous = today_local() - timedelta(days=today_local().weekday() + 7)
    assert f"/reflect?week={previous.isoformat()}" in page.text
    older = browser.get(f"/reflect?week={previous.isoformat()}")
    assert older.status_code == 200
    assert "This week" in older.text


def test_insights_page_with_data(browser):
    habit_id = create_habit(browser, title="Morning walk")
    log_day(browser, habit_id, today_local(), "done")
    page = browser.get("/insights")
    assert page.status_code == 200
    assert "Patterns, not perfection." in page.text
    assert "Morning walk" in page.text
    assert "Habit days done" in page.text


def test_insights_empty_state(browser):
    page = browser.get("/insights")
    assert page.status_code == 200
    assert "No habits to measure yet" in page.text


def test_local_coach_saves_labelled_suggestions(browser, app):
    habit_id = create_habit(browser, title="Strength training", days=["0", "2", "4"])
    log_day(browser, habit_id, today_local(), "done")
    r = browser.post(f"/habits/{habit_id}/coach")
    assert r.status_code == 303
    assert "coached=local" in r.headers["location"]
    page = browser.get(r.headers["location"])
    assert "Local coach: no API key" in page.text
    with app.state.sessionmaker() as db:
        rows = list(db.scalars(select(Suggestion).where(Suggestion.habit_id == habit_id)))
        assert 2 <= len(rows) <= 3
        assert all(row.source == "local" for row in rows)
        assert all(row.title and row.rationale for row in rows)


def test_coach_is_rate_limited(browser):
    habit_id = create_habit(browser)
    last = None
    for _ in range(7):
        last = browser.post(f"/habits/{habit_id}/coach")
    assert last.status_code == 429
    assert "short break" in last.text


def test_ai_validation_accepts_well_formed_payload():
    payload = {
        "suggestions": [
            {"title": "Shrink the first step", "rationale": "A two-minute version protects the cue on a hard day."},
            {"title": "Protect Wednesday", "rationale": "Move the habit earlier on the day it is most often missed."},
        ]
    }
    out = ai._validate(payload)
    assert len(out) == 2
    assert out[0].title == "Shrink the first step"


def test_ai_validation_rejects_thin_payloads():
    with pytest.raises(ValueError):
        ai._validate({"suggestions": [{"title": "ok", "rationale": "short"}]})
    with pytest.raises(ValueError):
        ai._validate({"suggestions": "not a list"})


def test_ai_falls_back_when_claude_is_unreachable(monkeypatch):
    class Offline:
        def __init__(self, *a, **kw):
            raise RuntimeError("offline")

    monkeypatch.setattr(ai.httpx, "Client", Offline)
    created = datetime(2026, 11, 1, 7, tzinfo=timezone.utc)
    habit = Habit(
        id=1, user_id=1, title="Read", intention="", cue="After coffee",
        days="0,1,2,3,4,5,6", status="active", created_at=created,
    )
    logs = [
        HabitLog(
            id=i, user_id=1, habit_id=1, day=date(2026, 11, 6) + timedelta(days=i),
            status="done", note="", created_at=datetime.combine(date(2026, 11, 6) + timedelta(days=i), time(20), tzinfo=timezone.utc),
        )
        for i in range(6)
    ]
    settings = Settings(_env_file=None, anthropic_api_key="test-key", run_migrations=False)
    result = ai.suggest(settings, habit, logs, date(2026, 11, 12))
    assert result.source == "local"
    assert "unavailable" in result.note
    assert 2 <= len(result.suggestions) <= 4
