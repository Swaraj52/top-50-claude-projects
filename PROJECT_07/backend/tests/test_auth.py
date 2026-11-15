from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import utcnow
from app.models import Mailbox, Session, User


def test_health_endpoint(app):
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"]


def test_login_and_register_pages_render(make_browser):
    other = make_browser()
    login = other.get("/login")
    register = other.get("/register")
    assert login.status_code == 200
    assert register.status_code == 200
    assert "Sign in" in login.text
    assert "No mailbox password is ever asked for" in login.text
    assert "Create an account" in register.text


def test_register_creates_an_account_and_a_mailbox(make_browser, app):
    other = make_browser()
    other.register(email="new@example.com", name="New Person")
    page = other.get("/inbox")
    assert page.status_code == 200
    with app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == "new@example.com"))
        assert user is not None and user.name == "New Person"
        assert user.timezone == "Asia/Kolkata"
        boxes = list(db.scalars(select(Mailbox).where(Mailbox.user_id == user.id)))
        assert [box.address for box in boxes] == ["new@example.com"]


def test_register_rejects_a_duplicate_email(browser, make_browser):
    other = make_browser()
    r = other.get("/register")
    assert r.status_code == 200
    r = other.post(
        "/register",
        {"name": "Twin", "email": "swayam@example.com", "password": "long enough 1", "timezone": "UTC"},
    )
    assert r.status_code == 409
    assert "already exists" in r.text


def test_register_rejects_an_invalid_email(make_browser):
    other = make_browser()
    other.get("/register")
    r = other.post(
        "/register", {"name": "No", "email": "not-an-email", "password": "long enough 1", "timezone": "UTC"}
    )
    assert r.status_code == 422
    assert "valid email" in r.text


def test_register_rejects_a_short_password(make_browser):
    other = make_browser()
    other.get("/register")
    r = other.post(
        "/register", {"name": "No", "email": "short@example.com", "password": "short", "timezone": "UTC"}
    )
    assert r.status_code == 422
    assert "eight characters" in r.text


def test_register_rejects_an_empty_name(make_browser):
    other = make_browser()
    other.get("/register")
    r = other.post(
        "/register", {"name": "  ", "email": "noname@example.com", "password": "long enough 1", "timezone": "UTC"}
    )
    assert r.status_code == 422


def test_register_falls_back_to_utc_for_an_unknown_timezone(make_browser, app):
    other = make_browser()
    other.register(email="tz@example.com", tz="Mars/Olympus_Mons")
    with app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == "tz@example.com"))
        assert user.timezone == "UTC"


def test_register_requires_the_pre_csrf_cookie(browser):
    browser.get("/register")
    r = browser.post(
        "/register",
        {"name": "No Token", "email": "nocsrf@example.com", "password": "long enough 1", "timezone": "UTC"},
        csrf=False,
    )
    assert r.status_code == 403


def test_login_accepts_a_different_case_email(browser, make_browser):
    other = make_browser()
    r = other.login(email="SWAYAM@EXAMPLE.COM")
    assert r.status_code == 303
    assert other.get("/inbox").status_code == 200


def test_login_rejects_a_wrong_password(browser, make_browser):
    other = make_browser()
    r = other.login(password="definitely wrong")
    assert r.status_code == 401
    assert "Incorrect email or password" in r.text


def test_login_rejects_an_unknown_email(browser, make_browser):
    other = make_browser()
    r = other.login(email="ghost@example.com")
    assert r.status_code == 401


def test_login_requires_the_pre_csrf_cookie(browser, make_browser):
    other = make_browser()
    other.get("/login")
    r = other.post(
        "/login", {"email": "swayam@example.com", "password": "long enough 1"}, csrf=False
    )
    assert r.status_code == 403


def test_login_is_rate_limited(browser, make_browser):
    other = make_browser()
    other.get("/login")
    for _ in range(10):
        r = other.post("/login", {"email": "swayam@example.com", "password": "wrong password"})
        assert r.status_code == 401
    blocked = other.post("/login", {"email": "swayam@example.com", "password": "wrong password"})
    assert blocked.status_code == 429
    assert "Too many failed attempts" in blocked.text


def test_session_cookie_is_http_only_and_lax(browser, make_browser):
    other = make_browser()
    other.get("/login")
    r = other.post(
        "/login", {"email": "swayam@example.com", "password": "long enough 1"}
    )
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "sb_session=" in cookie


def test_logout_ends_the_session(browser):
    browser.get("/inbox")
    r = browser.post("/logout")
    assert r.status_code == 303
    after = browser.get("/inbox")
    assert after.status_code == 303
    assert after.headers["location"] == "/login"


def test_pages_redirect_to_login_without_a_session(make_browser):
    other = make_browser()
    r = other.get("/inbox")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_htmx_requests_get_a_redirect_header(make_browser):
    other = make_browser()
    r = other.get("/inbox", headers={"HX-Request": "true"})
    assert r.status_code == 401
    assert r.headers["HX-Redirect"] == "/login"


def test_an_expired_session_is_rejected(browser, app):
    browser.get("/inbox")
    with app.state.sessionmaker() as db:
        session = db.scalar(select(Session))
        session.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    r = browser.get("/inbox")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_security_headers_are_present(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        r = client.get("/login")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "same-origin"


def test_unknown_pages_render_the_error_page(browser):
    r = browser.get("/nothing-here")
    assert r.status_code == 404
    assert "That page" in r.text and "exist" in r.text
    assert "Back to the desk" in r.text


def test_static_assets_are_served(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        css = client.get("/static/app.css")
        icon = client.get("/static/favicon.svg")
    assert css.status_code == 200
    assert "Switchboard" in css.text
    assert icon.status_code == 200


def test_accounts_are_isolated(make_browser):
    first = make_browser().register(email="one@example.com", name="One")
    second = make_browser().register(email="two@example.com", name="Two")
    from conftest import compose

    thread_id = compose(first, subject="Private", sender="a@b.example", body="Only for one.")
    assert first.get(f"/threads/{thread_id}").status_code == 200
    assert second.get(f"/threads/{thread_id}").status_code == 404
    listing = second.get("/inbox").text
    assert "Private" not in listing


def test_an_authenticated_user_is_sent_away_from_login(browser):
    r = browser.get("/login")
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    r = browser.get("/register")
    assert r.status_code == 303
