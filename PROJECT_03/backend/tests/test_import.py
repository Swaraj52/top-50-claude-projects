from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models import Blocker, Task, User
from app.timeutil import local_today
from scripts.import_data import ImportError_, apply


def test_import_loads_tasks_blockers_and_settings(app, browser):
    payload = {
        "settings": {"name": "Swayam N", "timezone": "Asia/Kolkata", "capacity_hours": 5},
        "tasks": [
            {"title": "Prepare slides", "area": "Work", "priority": 1, "estimate_min": 60, "when": "today"},
            {"title": "Read paper", "when": "backlog"},
            {"title": "Call bank", "when": "tomorrow", "due_date": "2030-01-01"},
        ],
        "blockers": [{"text": "Waiting for lab access"}],
    }
    with app.state.sessionmaker() as db:
        counts = apply(db, "SWAYAM@example.com", payload)
        assert counts == {"tasks": 3, "blockers": 1, "settings": 3}
        user = db.scalar(select(User))
        tasks = {t.title: t for t in db.scalars(select(Task))}
        today = local_today(ZoneInfo("Asia/Kolkata"))
        assert user.name == "Swayam N" and user.capacity_hours == 5
        assert tasks["Prepare slides"].planned_for == today and tasks["Prepare slides"].area == "work"
        assert tasks["Read paper"].planned_for is None
        assert tasks["Call bank"].planned_for == today + timedelta(days=1)
        assert db.scalar(select(Blocker)).text == "Waiting for lab access"
    assert "Prepare slides" in browser.get("/today").text


def test_import_rejects_bad_input_without_saving(app, browser):
    with app.state.sessionmaker() as db:
        with pytest.raises(ImportError_):
            apply(db, "nobody@example.com", {})
        with pytest.raises(ImportError_):
            apply(db, "swayam@example.com", {"tasks": [{"title": "  "}]})
        db.rollback()
        assert db.scalars(select(Task)).all() == []
