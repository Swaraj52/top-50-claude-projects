from __future__ import annotations

import json

from tests.conftest import create_habit, log_day, today_local


def test_settings_page_loads(browser):
    page = browser.get("/settings")
    assert page.status_code == 200
    assert "Change password" in page.text
    assert "Export your data" in page.text
    assert "Delete account" in page.text


def test_save_profile_name_and_timezone(browser):
    r = browser.post("/settings", {"name": "Swayam Naik", "timezone": "Europe/London"})
    assert r.status_code == 303
    page = browser.get("/settings?saved=1")
    assert "Changes saved." in page.text
    assert "Swayam Naik" in page.text
    assert 'value="Europe/London"' in page.text


def test_reject_unknown_timezone(browser):
    r = browser.post("/settings", {"name": "Swayam", "timezone": "Mars/Olympus"})
    assert r.status_code == 422
    assert "Unknown timezone" in r.text


def test_reject_empty_name(browser):
    r = browser.post("/settings", {"name": "   ", "timezone": "UTC"})
    assert r.status_code == 422
    assert "Name must be" in r.text


def test_change_password_rejects_wrong_current(browser):
    r = browser.post("/settings/password", {"current_password": "wrong password", "new_password": "a new long one"})
    assert r.status_code == 422
    assert "current password is incorrect" in r.text


def test_change_password_then_sign_in_with_new_one(make_browser):
    owner = make_browser().register(email="change@example.com")
    r = owner.post("/settings/password", {"current_password": "long enough 1", "new_password": "brand new long 2"})
    assert r.status_code == 303

    other = make_browser()
    old = other.login(email="change@example.com", password="long enough 1")
    assert old.status_code == 401
    new = other.login(email="change@example.com", password="brand new long 2")
    assert new.status_code == 303


def test_export_contains_habits_logs_and_reflections(browser):
    day = today_local()
    habit_id = create_habit(browser, title="Morning walk")
    log_day(browser, habit_id, day, "done")
    browser.post("/reflect", {"week": day.isoformat(), "mood": "4", "worked": "Walked.", "friction": "", "change": "Keep it."})
    r = browser.get("/settings/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    payload = json.loads(r.text)
    assert payload["format"] == "cadence-export-v1"
    assert payload["habits"][0]["title"] == "Morning walk"
    assert payload["habits"][0]["logs"][0]["status"] == "done"
    assert payload["reflections"][0]["worked"] == "Walked."
    assert "password" not in r.text.lower()


def test_delete_account_requires_confirmation(browser):
    r = browser.post("/settings/delete", {"password": "long enough 1", "confirm": "no"})
    assert r.status_code == 422
    assert "Type DELETE" in r.text


def test_delete_account_requires_password(browser):
    r = browser.post("/settings/delete", {"password": "wrong", "confirm": "DELETE"})
    assert r.status_code == 422
    assert "password is incorrect" in r.text


def test_delete_account_removes_session(make_browser):
    owner = make_browser().register(email="delete@example.com")
    r = owner.post("/settings/delete", {"password": "long enough 1", "confirm": "DELETE"})
    assert r.status_code == 303
    assert r.headers["location"] == "/login"

    survivor = make_browser()
    failed = survivor.login(email="delete@example.com", password="long enough 1")
    assert failed.status_code == 401


def test_health_endpoint(app):
    from fastapi.testclient import TestClient

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "1.0.0"}


def test_security_headers_are_set(make_browser):
    b = make_browser()
    r = b.get("/login")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "same-origin"


def test_not_found_page_uses_app_chrome(browser):
    r = browser.get("/does-not-exist")
    assert r.status_code == 404
    assert "That page doesn" in r.text
    assert "Back to today" in r.text


def test_not_found_page_for_anonymous_visitor(make_browser):
    b = make_browser()
    r = b.get("/does-not-exist")
    assert r.status_code == 404
    assert "sign in" in r.text


def test_csrf_is_required_for_settings(browser):
    r = browser.post("/settings", {"name": "No Token", "timezone": "UTC"}, csrf=False)
    assert r.status_code == 403
