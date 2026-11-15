from __future__ import annotations

import json

from sqlalchemy import func, select

from app.models import Draft, FollowUp, Mailbox, Session, Thread, User
from conftest import compose


def user(app, email="swayam@example.com"):
    with app.state.sessionmaker() as db:
        return db.scalar(select(User).where(User.email == email))


def test_settings_shows_the_archive_counts(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    browser.post(f"/threads/{thread_id}/followups", {"title": "A counted follow-up"})
    page = browser.get("/settings").text
    assert "Your archive" in page
    assert "Threads" in page
    assert "Drafts" in page
    assert "Follow-ups" in page
    assert "Mailboxes" in page


def test_profile_can_be_saved(browser, app):
    browser.get("/settings")
    r = browser.post(
        "/settings",
        {
            "name": "Swayam Naik",
            "timezone": "Europe/Berlin",
            "signature": "Product lead, Lumen Labs",
            "vips": "priya@lumen.example, Arjun Mehta",
        },
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/settings?saved=1"
    saved = user(app)
    assert saved.name == "Swayam Naik"
    assert saved.timezone == "Europe/Berlin"
    assert saved.signature == "Product lead, Lumen Labs"
    assert saved.vips == "priya@lumen.example, Arjun Mehta"
    assert "Saved." in browser.get("/settings?saved=1").text


def test_an_empty_name_is_rejected(browser, app):
    browser.get("/settings")
    r = browser.post("/settings", {"name": " ", "timezone": "UTC", "signature": "", "vips": ""})
    assert r.status_code == 422
    assert user(app).name == "Swayam"


def test_an_unknown_timezone_is_rejected(browser, app):
    browser.get("/settings")
    r = browser.post("/settings", {"name": "Swayam", "timezone": "Mars/Base", "signature": "", "vips": ""})
    assert r.status_code == 422
    assert user(app).timezone == "Asia/Kolkata"


def test_an_oversized_signature_is_rejected(browser):
    browser.get("/settings")
    r = browser.post("/settings", {"name": "Swayam", "timezone": "UTC", "signature": "x" * 241, "vips": ""})
    assert r.status_code == 422


def test_an_oversized_vip_list_is_rejected(browser):
    browser.get("/settings")
    r = browser.post("/settings", {"name": "Swayam", "timezone": "UTC", "signature": "", "vips": "x" * 2001})
    assert r.status_code == 422


def test_a_mailbox_can_be_added(browser, app):
    browser.get("/settings")
    r = browser.post("/settings/mailboxes", {"name": "Work", "address": "Work@Example.com"})
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        boxes = list(db.scalars(select(Mailbox).order_by(Mailbox.id)))
        assert [b.address for b in boxes] == ["swayam@example.com", "work@example.com"]


def test_a_duplicate_mailbox_is_rejected(browser):
    browser.get("/settings")
    r = browser.post("/settings/mailboxes", {"name": "Again", "address": "swayam@example.com"})
    assert r.status_code == 409
    assert "already listed" in r.text


def test_an_invalid_mailbox_address_is_rejected(browser):
    browser.get("/settings")
    r = browser.post("/settings/mailboxes", {"name": "Bad", "address": "not an address"})
    assert r.status_code == 422


def test_an_empty_mailbox_name_is_rejected(browser):
    browser.get("/settings")
    r = browser.post("/settings/mailboxes", {"name": " ", "address": "ok@example.com"})
    assert r.status_code == 422


def test_an_empty_mailbox_can_be_removed(browser, app):
    browser.get("/settings")
    browser.post("/settings/mailboxes", {"name": "Temp", "address": "temp@example.com"})
    with app.state.sessionmaker() as db:
        box_id = db.scalar(select(Mailbox.id).where(Mailbox.address == "temp@example.com"))
    r = browser.post(f"/settings/mailboxes/{box_id}/delete")
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        assert db.get(Mailbox, box_id) is None


def test_a_mailbox_with_threads_cannot_be_removed(browser, app):
    compose(browser)
    with app.state.sessionmaker() as db:
        box_id = db.scalar(select(Mailbox.id).where(Mailbox.address == "swayam@example.com"))
    r = browser.post(f"/settings/mailboxes/{box_id}/delete")
    assert r.status_code == 409
    with app.state.sessionmaker() as db:
        assert db.get(Mailbox, box_id) is not None


def test_another_users_mailbox_cannot_be_removed(browser, make_browser, app):
    other = make_browser().register(email="other@example.com", name="Other")
    with app.state.sessionmaker() as db:
        box_id = db.scalar(select(Mailbox.id).where(Mailbox.address == "other@example.com"))
    r = browser.post(f"/settings/mailboxes/{box_id}/delete")
    assert r.status_code == 404


def test_a_wrong_current_password_is_rejected(browser):
    browser.get("/settings")
    r = browser.post("/settings/password", {"current_password": "wrong", "new_password": "a new password"})
    assert r.status_code == 422
    assert "current password is incorrect" in r.text


def test_a_short_new_password_is_rejected(browser):
    browser.get("/settings")
    r = browser.post("/settings/password", {"current_password": "long enough 1", "new_password": "short"})
    assert r.status_code == 422


def test_changing_the_password_keeps_this_session_and_ends_others(browser, make_browser, app):
    second = make_browser()
    second.login()
    assert second.get("/inbox").status_code == 200
    browser.get("/settings")
    r = browser.post(
        "/settings/password", {"current_password": "long enough 1", "new_password": "a brand new password"}
    )
    assert r.status_code == 303
    assert browser.get("/inbox").status_code == 200
    assert second.get("/inbox").status_code == 303
    with app.state.sessionmaker() as db:
        uid = db.scalar(select(User.id).where(User.email == "swayam@example.com"))
        assert db.scalar(select(func.count(Session.id)).where(Session.user_id == uid)) == 1


def test_the_export_has_the_archive_shape_and_no_secrets(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    browser.post(f"/threads/{thread_id}/followups", {"title": "In the export", "due_date": "2026-12-01"})
    r = browser.c.get("/settings/export")
    assert r.status_code == 200
    assert "switchboard-export.json" in r.headers["content-disposition"]
    payload = json.loads(r.text)
    assert payload["format"] == "switchboard-export-v1"
    assert payload["exported_for"] == "swayam@example.com"
    assert len(payload["threads"]) == 1
    thread = payload["threads"][0]
    assert thread["subject"] == "Q4 launch checklist"
    assert len(thread["messages"]) == 1
    assert len(thread["drafts"]) == 1
    assert thread["followups"][0]["title"] == "In the export"
    blob = r.text.lower()
    assert "password" not in blob
    assert "csrf" not in blob
    assert "token_hash" not in blob


def test_the_export_is_scoped_to_the_account(browser, make_browser):
    compose(browser, subject="Mine only")
    other = make_browser().register(email="other@example.com", name="Other")
    other.get("/inbox")
    payload = json.loads(other.c.get("/settings/export").text)
    assert payload["threads"] == []


def test_delete_account_requires_the_typed_word(browser, app):
    browser.get("/settings")
    r = browser.post("/settings/delete", {"password": "long enough 1", "confirm": "delete"})
    assert r.status_code == 422
    assert user(app) is not None


def test_delete_account_requires_the_password(browser, app):
    browser.get("/settings")
    r = browser.post("/settings/delete", {"password": "wrong", "confirm": "DELETE"})
    assert r.status_code == 422
    assert user(app) is not None


def test_delete_account_removes_everything_and_ends_the_session(browser, make_browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    browser.post(f"/threads/{thread_id}/followups", {"title": "Gone with the account"})
    second = make_browser()
    second.login()
    browser.get("/settings")
    r = browser.post("/settings/delete", {"password": "long enough 1", "confirm": "DELETE"})
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    with app.state.sessionmaker() as db:
        assert db.scalar(select(func.count(User.id))) == 0
        assert db.scalar(select(func.count(Thread.id))) == 0
        assert db.scalar(select(func.count(Draft.id))) == 0
        assert db.scalar(select(func.count(FollowUp.id))) == 0
        assert db.scalar(select(func.count(Mailbox.id))) == 0
        assert db.scalar(select(func.count(Session.id))) == 0
    assert second.get("/inbox").status_code == 303


def test_settings_labels_the_local_writer(app, browser):
    page = browser.get("/settings").text
    assert "No API key is set" in page
    assert "labelled local writer" in page


def test_settings_shows_claude_when_a_key_is_present(app, browser):
    app.state.settings.anthropic_api_key = "test-key"
    page = browser.get("/settings").text
    assert "Claude is configured" in page
    assert "claude-opus-5-5" in page


def test_settings_shows_the_mailbox_labels(browser, app):
    browser.get("/settings")
    browser.post("/settings/mailboxes", {"name": "Work", "address": "work@example.com"})
    page = browser.get("/settings").text
    assert "Personal" in page
    assert "Work" in page
    assert "work@example.com" in page
