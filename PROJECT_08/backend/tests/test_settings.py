from __future__ import annotations

import json

from conftest import add_collection, add_item


def test_settings_shows_counts_and_export(browser):
    add_item(browser, title="One", body="a b c")
    add_item(browser, title="Two", body="d e", tags="pricing")
    page = browser.get("/settings")
    assert page.status_code == 200
    assert "Download JSON export" in page.text
    assert "Claude is <strong>off</strong>" in page.text


def test_save_profile_updates_name_and_timezone(browser):
    r = browser.post("/settings", {"name": "Swayam Naik", "timezone": "Europe/London"})
    assert r.status_code == 303
    assert r.headers["location"] == "/settings?saved=1"
    page = browser.get("/settings?saved=1")
    assert "Swayam Naik" in page.text
    assert 'value="Europe/London"' in page.text
    assert "Saved." in page.text


def test_profile_rejects_an_empty_name(browser):
    r = browser.post("/settings", {"name": "  ", "timezone": "UTC"})
    assert r.status_code == 422
    assert "between 1 and 80" in r.text


def test_profile_rejects_an_unknown_timezone(browser):
    r = browser.post("/settings", {"name": "Swayam", "timezone": "Moon/Base"})
    assert r.status_code == 422
    assert "Unknown timezone" in r.text


def test_password_change_requires_the_current_password(browser):
    r = browser.post("/settings/password", {"current_password": "wrong", "new_password": "brand new 2"})
    assert r.status_code == 422
    assert "current password is incorrect" in r.text


def test_password_change_requires_eight_characters(browser):
    r = browser.post("/settings/password", {"current_password": "long enough 1", "new_password": "short"})
    assert r.status_code == 422
    assert "at least 8" in r.text


def test_password_change_ends_other_sessions(make_browser):
    a = make_browser().register(email="pw@example.com", password="long enough 1")
    b = make_browser()
    b.login(email="pw@example.com", password="long enough 1")
    r = a.post("/settings/password", {"current_password": "long enough 1", "new_password": "a new secret 2"})
    assert r.status_code == 303
    assert a.get("/").status_code == 200
    assert b.get("/").status_code == 303
    b.login(email="pw@example.com", password="a new secret 2")
    assert b.get("/").status_code == 200


def test_export_has_every_item_and_no_secrets(browser):
    add_collection(browser, "Client work", "A shelf")
    import re

    page = browser.get("/collections")
    collection_id = re.search(r'action="/collections/(\d+)"', page.text).group(1)
    item_id = add_item(browser, title="Exported note", body="The pricing text.", tags="pricing, q4", starred="on")
    browser.post(
        f"/items/{item_id}/edit",
        {
            "title": "Exported note",
            "body": "The pricing text.",
            "kind": "note",
            "tags": "pricing, q4",
            "collection_id": collection_id,
            "starred": "on",
        },
    )
    r = browser.get("/settings/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "loom-export.json" in r.headers["content-disposition"]
    payload = json.loads(r.text)
    assert payload["format"] == "loom-export-v1"
    assert payload["exported_for"] == "swayam@example.com"
    assert payload["collections"] == [{"name": "Client work", "description": "A shelf"}]
    assert len(payload["items"]) == 1
    entry = payload["items"][0]
    assert entry["title"] == "Exported note"
    assert entry["tags"] == ["pricing", "q4"]
    assert entry["starred"] is True
    assert entry["collection"] == "Client work"
    text = r.text.lower()
    for secret in ("password", "token", "csrf", "api_key", "hash"):
        assert secret not in text


def test_export_is_scoped_to_one_account(make_browser):
    a = make_browser().register(email="a@example.com")
    add_item(a, title="A note")
    b = make_browser().register(email="b@example.com", name="B")
    payload = json.loads(b.get("/settings/export").text)
    assert payload["items"] == []
    assert payload["collections"] == []


def test_delete_account_requires_delete_and_password(browser):
    r = browser.post("/settings/delete", {"confirm": "delete", "password": "long enough 1"})
    assert r.status_code == 422
    assert "Type DELETE" in r.text
    r = browser.post("/settings/delete", {"confirm": "DELETE", "password": "wrong password"})
    assert r.status_code == 422
    assert "password is incorrect" in r.text


def test_delete_account_removes_data_and_session(make_browser, app):
    a = make_browser().register(email="gone@example.com")
    add_collection(a, "Shelf")
    add_item(a, title="Gone note", body="text", tags="x")
    r = a.post("/settings/delete", {"confirm": "DELETE", "password": "long enough 1"})
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert a.get("/").status_code == 303

    from sqlalchemy import select

    from app.db import make_sessionmaker
    from app.models import Collection, Item, User

    Session = make_sessionmaker(app.state.engine)
    with Session() as db:
        assert db.scalar(select(User).where(User.email == "gone@example.com")) is None
        assert db.scalars(select(Item)).all() == []
        assert db.scalars(select(Collection)).all() == []


def test_delete_account_can_be_repeated_by_nobody(make_browser):
    a = make_browser().register(email="twice@example.com")
    a.post("/settings/delete", {"confirm": "DELETE", "password": "long enough 1"})
    r = a.get("/settings")
    assert r.status_code == 303


def test_settings_page_explains_the_ai_switch(browser):
    page = browser.get("/settings")
    assert "ANTHROPIC_API_KEY" in page.text
    assert "No key is required" in page.text
