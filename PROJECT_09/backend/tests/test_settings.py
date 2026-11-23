from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from app.models import (
    CanvasEntry,
    CostLine,
    Kpi,
    KpiReading,
    Milestone,
    RevenueStream,
    Session,
    SwotItem,
    User,
    Venture,
)
from conftest import add_canvas, add_cost, add_kpi, add_milestone, add_reading, add_stream, add_swot, add_venture

PASSWORD = "long enough 1"


def test_settings_page_shows_the_profile_and_counts(browser):
    venture_id = add_venture(browser, name="Sahaj")
    add_canvas(browser, venture_id, title="A real problem")
    add_swot(browser, venture_id, text="A real strength")
    add_stream(browser, venture_id)
    add_cost(browser, venture_id)
    add_milestone(browser, venture_id, title="First milestone")
    add_kpi(browser, venture_id)
    add_reading(browser, 1, value="5")
    text = browser.get("/settings").text
    assert "Your desk" in text
    assert "Swayam" in text
    assert "swayam@example.com" in text
    assert "Asia/Kolkata" in text
    assert "Ventures" in text and "Canvas notes" in text and "SWOT items" in text
    assert "Milestones" in text and "KPIs" in text and "Readings" in text
    assert "Built by" in text and "Swayam" in text


def test_saving_the_profile_updates_the_user(browser, db):
    r = browser.post("/settings", {"name": "Swayam Naik", "timezone": "UTC"})
    assert r.status_code == 303
    assert r.headers["location"] == "/settings?saved=1"
    db.expire_all()
    user = db.scalar(select(User))
    assert user.name == "Swayam Naik"
    assert user.timezone == "UTC"
    assert "Saved." in browser.get("/settings?saved=1").text


def test_blank_name_is_rejected(browser, db):
    r = browser.post("/settings", {"name": " ", "timezone": "UTC"})
    assert r.status_code == 422
    assert "between 1 and 80 characters" in r.text
    db.expire_all()
    assert db.scalar(select(User)).name == "Swayam"


def test_too_long_name_is_rejected(browser):
    r = browser.post("/settings", {"name": "x" * 81, "timezone": "UTC"})
    assert r.status_code == 422
    assert "between 1 and 80 characters" in r.text


def test_unknown_timezone_is_rejected(browser, db):
    r = browser.post("/settings", {"name": "Swayam", "timezone": "Mars/Olympus"})
    assert r.status_code == 422
    assert "Unknown timezone" in r.text
    db.expire_all()
    assert db.scalar(select(User)).timezone == "Asia/Kolkata"


def test_password_change_requires_the_current_password(browser, db):
    r = browser.post("/settings/password", {"current_password": "wrong one", "new_password": "a new password"})
    assert r.status_code == 422
    assert "current password is incorrect" in r.text
    db.expire_all()
    user = db.scalar(select(User))
    assert "a new password" not in user.password_hash


def test_password_change_requires_eight_characters(browser, db):
    r = browser.post("/settings/password", {"current_password": PASSWORD, "new_password": "short"})
    assert r.status_code == 422
    assert "at least 8 characters" in r.text


def test_password_change_works_and_keeps_the_current_session(browser, db, make_browser):
    other = make_browser()
    assert other.login(password=PASSWORD).status_code == 303
    r = browser.post("/settings/password", {"current_password": PASSWORD, "new_password": "a better password"})
    assert r.status_code == 303
    assert r.headers["location"] == "/settings?saved=1"
    db.expire_all()
    assert db.scalar(select(Session).where(Session.user_id == 1)) is not None
    # The current browser stays signed in.
    assert browser.get("/").status_code == 200
    # The other session was ended.
    assert other.c.get("/").headers["location"] == "/login"
    # The new password is the one that works.
    fresh = make_browser()
    assert fresh.login(password=PASSWORD).status_code == 401
    assert fresh.login(password="a better password").status_code == 303


def test_changing_the_password_does_not_change_another_account(browser, db, make_browser):
    other = make_browser().register(email="other@example.com", name="Other", password="other password 1")
    browser.post("/settings/password", {"current_password": PASSWORD, "new_password": "a better password"})
    db.expire_all()
    users = {user.email: user for user in db.scalars(select(User)).all()}
    from app.security import verify_password

    assert verify_password("other password 1", users["other@example.com"].password_hash)
    assert other.c.get("/").status_code == 200


def test_export_is_a_json_attachment(browser):
    add_venture(browser, name="Sahaj")
    r = browser.get("/settings/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers["content-disposition"]
    assert "keystone-export.json" in r.headers["content-disposition"]


def test_export_shape_covers_every_entity(browser):
    venture_id = add_venture(browser, name="Sahaj", segment="Installers", market="Growing")
    add_canvas(browser, venture_id, block="problem", title="A real problem", detail="Missed follow-ups")
    add_swot(browser, venture_id, quadrant="threat", text="An incumbent bundles it", impact="5", evidence="Pricing page")
    add_stream(browser, venture_id, name="Subscription", price="1499", volume="40")
    add_cost(browser, venture_id, name="Support", amount="18000")
    add_milestone(browser, venture_id, title="Ten installers", success_criterion="Ten accounts", owner="Swayam")
    add_kpi(browser, venture_id, name="Activated installers", unit="installers", target="40")
    add_reading(browser, 1, value="12", note="First week")

    payload = json.loads(browser.get("/settings/export").text)
    assert payload["format"] == "keystone-export-v1"
    assert payload["exported_for"] == "swayam@example.com"
    assert len(payload["ventures"]) == 1
    venture = payload["ventures"][0]
    assert venture["name"] == "Sahaj"
    assert venture["segment"] == "Installers"
    assert venture["market"] == "Growing"
    assert venture["stage"] == "validating"
    assert venture["canvas"][0] == {
        "block": "problem",
        "title": "A real problem",
        "detail": "Missed follow-ups",
        "sort_order": 1,
    }
    assert venture["swot"][0]["impact"] == 5
    assert venture["streams"][0]["price"] == 1499
    assert venture["costs"][0]["amount"] == 18000
    assert venture["milestones"][0]["title"] == "Ten installers"
    assert venture["kpis"][0]["name"] == "Activated installers"
    assert venture["kpis"][0]["readings"][0]["value"] == 12


def test_export_contains_no_secret_material(browser):
    add_venture(browser, name="Sahaj")
    text = browser.get("/settings/export").text
    lowered = text.lower()
    for forbidden in ("password", "scrypt", "token_hash", "csrf", "ks_session", "api_key"):
        assert forbidden not in lowered


def test_export_is_owner_scoped(browser, make_browser, db):
    add_venture(browser, name="Mine")
    other = make_browser().register(email="export-other@example.com", name="Other")
    add_venture(other, name="Theirs")
    mine = json.loads(browser.get("/settings/export").text)
    theirs = json.loads(other.get("/settings/export").text)
    assert [v["name"] for v in mine["ventures"]] == ["Mine"]
    assert [v["name"] for v in theirs["ventures"]] == ["Theirs"]


def test_export_includes_archived_ventures(browser):
    venture_id = add_venture(browser, name="Old idea")
    browser.post(f"/ventures/{venture_id}/archive")
    payload = json.loads(browser.get("/settings/export").text)
    assert payload["ventures"][0]["archived"] is True


def test_account_deletion_requires_the_word_delete(browser, db):
    r = browser.post("/settings/delete", {"password": PASSWORD, "confirm": "delete"})
    assert r.status_code == 422
    assert "Type DELETE to confirm" in r.text
    assert db.scalar(select(User)) is not None


def test_account_deletion_requires_the_password(browser, db):
    r = browser.post("/settings/delete", {"password": "wrong", "confirm": "DELETE"})
    assert r.status_code == 422
    assert "password is incorrect" in r.text
    assert db.scalar(select(User)) is not None


def test_account_deletion_removes_every_row_and_signs_out(browser, db):
    venture_id = add_venture(browser, name="Sahaj")
    add_canvas(browser, venture_id, title="A real problem")
    add_swot(browser, venture_id, text="A real strength")
    add_stream(browser, venture_id)
    add_cost(browser, venture_id)
    add_milestone(browser, venture_id, title="First milestone")
    add_kpi(browser, venture_id)
    add_reading(browser, 1, value="5")

    r = browser.post("/settings/delete", {"password": PASSWORD, "confirm": "DELETE"})
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert "ks_session" not in r.cookies

    db.expire_all()
    for model in (User, Session, Venture, CanvasEntry, SwotItem, RevenueStream, CostLine, Milestone, Kpi, KpiReading):
        assert db.scalar(select(func.count()).select_from(model)) == 0, model.__name__
    assert browser.c.get("/").headers["location"] == "/login"


def test_account_deletion_leaves_other_accounts_alone(browser, make_browser, db):
    other = make_browser().register(email="other@example.com", name="Other")
    add_venture(other, name="Theirs")
    browser.post("/settings/delete", {"password": PASSWORD, "confirm": "DELETE"})
    db.expire_all()
    assert db.scalar(select(User).where(User.email == "other@example.com")) is not None
    assert db.scalar(select(Venture).where(Venture.name == "Theirs")) is not None
    assert other.c.get("/").status_code == 200


@pytest.mark.parametrize("path", ["/settings", "/settings/export"])
def test_settings_pages_require_login(make_browser, path):
    r = make_browser().c.get(path)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_settings_forms_require_csrf(browser):
    assert browser.post("/settings", {"name": "No token"}, csrf=False).status_code == 403
    assert browser.post("/settings/password", {"current_password": PASSWORD}, csrf=False).status_code == 403
    assert browser.post("/settings/delete", {"password": PASSWORD, "confirm": "DELETE"}, csrf=False).status_code == 403
