from __future__ import annotations

import json
import sys

from sqlalchemy import inspect, select

from app.db import Base
from app.models import Checkin, Goal, Milestone, User, WeeklyAction
from tests.conftest import create_goal


def test_migration_matches_models(app):
    tables = set(inspect(app.state.engine).get_table_names())
    assert set(Base.metadata.tables) <= tables
    assert "alembic_version" in tables


def test_health(app):
    from fastapi.testclient import TestClient

    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"] == "1.0.0"


def test_security_headers(browser):
    r = browser.get("/")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_settings_profile_and_password(browser, app):
    r = browser.post("/settings", {"name": "Swayam Naik", "timezone": "Asia/Kolkata", "weekly_capacity_min": "420"})
    assert r.status_code == 303
    assert "Swayam Naik" in browser.get("/settings").text
    r = browser.post("/settings/password", {"current_password": "wrong", "new_password": "a new password"})
    assert r.status_code == 422
    r = browser.post("/settings/password", {"current_password": "long enough 1", "new_password": "a new password"})
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        assert db.scalar(select(User.email)) == "swayam@example.com"


def test_settings_validation(browser):
    assert browser.post("/settings", {"name": "", "timezone": "UTC", "weekly_capacity_min": "300"}).status_code == 422
    assert browser.post("/settings", {"name": "A", "timezone": "Mars/Olympus", "weekly_capacity_min": "300"}).status_code == 422
    assert browser.post("/settings", {"name": "A", "timezone": "UTC", "weekly_capacity_min": "5"}).status_code == 422


def test_delete_account(browser, app):
    create_goal(browser)
    r = browser.post("/settings/delete", {"password": "long enough 1", "confirm": "no"})
    assert r.status_code == 422
    r = browser.post("/settings/delete", {"password": "wrong", "confirm": "DELETE"})
    assert r.status_code == 422
    r = browser.post("/settings/delete", {"password": "long enough 1", "confirm": "DELETE"})
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        assert db.scalar(select(User.id)) is None
    assert browser.get("/").status_code == 303


def test_import_accepts_export_shape(browser, app, tmp_path, monkeypatch):
    """An export puts actions and check-ins at the top level; the importer must read them."""
    create_goal(browser, "Existing goal")
    payload = {
        "format": "summit-export-v1",
        "goals": [
            {
                "title": "Imported goal",
                "category": "learning",
                "status": "active",
                "target_date": None,
                "milestones": [{"title": "First step", "weight": 3, "status": "open"}],
            }
        ],
        "actions": [
            {"goal": "Imported goal", "title": "Do the first step", "estimate_min": 30, "week_start": "2026-11-09", "status": "open"}
        ],
        "checkins": [{"goal": "Imported goal", "day": "2026-11-11", "confidence": 4, "note": "ok"}],
    }
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setattr(sys, "argv", ["import_data", "--email", "swayam@example.com", str(path)])
    from scripts import import_data

    assert import_data.main() == 0

    with app.state.sessionmaker() as db:
        goal = db.scalar(select(Goal).where(Goal.title == "Imported goal"))
        assert goal is not None
        assert db.scalar(select(Milestone).where(Milestone.goal_id == goal.id)) is not None
        assert db.scalar(select(WeeklyAction).where(WeeklyAction.goal_id == goal.id)).title == "Do the first step"
        assert db.scalar(select(Checkin).where(Checkin.goal_id == goal.id)).confidence == 4
