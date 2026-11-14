from __future__ import annotations

import json

from sqlalchemy import select

from app.models import ActionItem, Decision, Meeting, User
from conftest import create_meeting, today_local


def test_memory_page_offers_search_prompts(make_browser):
    b = make_browser().register()
    page = b.get("/memory").text
    assert "ASK THE ARCHIVE" in page
    assert "What does Priya own?" in page


def test_memory_search_finds_meetings_decisions_and_actions(browser):
    create_meeting(browser)
    page = browser.get("/memory?q=Priya").text
    assert "Weekly product review" in page
    assert "send the onboarding deck" in page
    assert "result" in page


def test_memory_search_matches_a_decision(browser):
    create_meeting(browser)
    page = browser.get("/memory?q=pricing").text
    assert "Keep pricing on one page" in page


def test_memory_search_matches_meeting_notes(browser):
    create_meeting(browser)
    page = browser.get("/memory?q=onboarding%20flow").text
    assert "Weekly product review" in page


def test_memory_search_reports_no_match(browser):
    create_meeting(browser)
    page = browser.get("/memory?q=zzzznothing").text
    assert "Nothing in the archive" in page


def test_memory_search_is_scoped_to_the_account(make_browser):
    owner = make_browser().register()
    create_meeting(owner)
    stranger = make_browser().register(email="stranger@example.com", name="Stranger")
    page = stranger.get("/memory?q=Priya").text
    assert "Nothing in the archive" in page


def test_settings_shows_the_archive_counts(browser):
    create_meeting(browser)
    page = browser.get("/settings").text
    assert "1 meetings" in page
    assert "2 decisions" in page
    assert "2 follow-ups" in page
    assert "Local extractor" in page


def test_profile_can_change_name_and_timezone(browser, app):
    r = browser.post("/settings", {"name": "Swayam Naik", "timezone": "Europe/London"})
    assert r.status_code == 303
    assert r.headers["location"] == "/settings?saved=1"
    with app.state.sessionmaker() as db:
        user = db.scalar(select(User))
        assert (user.name, user.timezone) == ("Swayam Naik", "Europe/London")


def test_profile_rejects_an_empty_name(browser, app):
    r = browser.post("/settings", {"name": "  ", "timezone": "UTC"})
    assert r.status_code == 422
    with app.state.sessionmaker() as db:
        assert db.scalar(select(User)).name == "Swayam"


def test_profile_rejects_an_unknown_timezone(browser, app):
    r = browser.post("/settings", {"name": "Swayam", "timezone": "Mars/Olympus"})
    assert r.status_code == 422
    assert "Unknown timezone" in r.text
    with app.state.sessionmaker() as db:
        assert db.scalar(select(User)).timezone == "Asia/Kolkata"


def test_password_change_rejects_a_wrong_current_password(browser):
    r = browser.post("/settings/password", {"current_password": "wrong", "new_password": "a new password"})
    assert r.status_code == 422
    assert "current password is incorrect" in r.text


def test_password_change_rejects_a_short_new_password(browser):
    r = browser.post("/settings/password", {"current_password": "long enough 1", "new_password": "short"})
    assert r.status_code == 422
    assert "at least 8" in r.text


def test_password_change_keeps_this_session_and_ends_other_devices(make_browser):
    owner = make_browser().register()
    other = make_browser()
    other.login()
    assert other.get("/").status_code == 200
    r = owner.post("/settings/password", {"current_password": "long enough 1", "new_password": "a brand new password"})
    assert r.status_code == 303
    assert owner.get("/").status_code == 200
    assert other.get("/").status_code == 303
    fresh = make_browser()
    assert fresh.login(password="a brand new password").status_code == 303


def test_export_contains_the_archive_and_no_secrets(browser):
    create_meeting(browser)
    r = browser.get("/settings/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "quorum-export.json" in r.headers["content-disposition"]
    payload = json.loads(r.text)
    assert payload["format"] == "quorum-export-v1"
    assert payload["exported_for"] == "swayam@example.com"
    meeting = payload["meetings"][0]
    assert meeting["title"] == "Weekly product review"
    assert meeting["source"] == "local"
    assert "notes" in meeting and "summary" in meeting
    assert len(meeting["decisions"]) == 2
    assert len(meeting["actions"]) == 2
    assert "password" not in r.text.lower() or "password_hash" not in r.text


def test_delete_account_requires_the_typed_word(browser, app):
    r = browser.post("/settings/delete", {"password": "long enough 1", "confirm": "delete"})
    assert r.status_code == 422
    assert "Type DELETE" in r.text
    with app.state.sessionmaker() as db:
        assert db.scalar(select(User)) is not None


def test_delete_account_requires_the_password(browser, app):
    r = browser.post("/settings/delete", {"password": "wrong", "confirm": "DELETE"})
    assert r.status_code == 422
    assert "password is incorrect" in r.text
    with app.state.sessionmaker() as db:
        assert db.scalar(select(User)) is not None


def test_delete_account_removes_everything(browser, app):
    create_meeting(browser)
    r = browser.post("/settings/delete", {"password": "long enough 1", "confirm": "DELETE"})
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    with app.state.sessionmaker() as db:
        assert db.scalar(select(User)) is None
        assert db.scalar(select(Meeting)) is None
        assert db.scalar(select(Decision)) is None
        assert db.scalar(select(ActionItem)) is None
    assert browser.get("/").headers["location"] == "/login"


def test_health_endpoint(make_browser):
    r = make_browser().get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_security_headers_are_present(make_browser):
    r = make_browser().get("/login")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "same-origin"


def test_unknown_page_renders_the_error_shell(browser):
    r = browser.get("/no-such-page")
    assert r.status_code == 404
    assert "ERROR 404" in r.text
    assert "Back to today" in r.text
