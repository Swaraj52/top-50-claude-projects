from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.db import utcnow
from app.models import Session, User
from app.security import hash_password


def user_row(app, email="swayam@example.com"):
    with app.state.sessionmaker() as db:
        return db.scalar(select(User).where(User.email == email))


def test_login_page_renders_without_a_nav(make_browser):
    b = make_browser()
    r = b.get("/login")
    assert r.status_code == 200
    assert "Sign in" in r.text
    assert "/logout" not in r.text


def test_register_page_renders(make_browser):
    r = make_browser().get("/register")
    assert r.status_code == 200
    assert "Start your memory" in r.text
    assert "Create account" in r.text


def test_register_creates_a_session_and_lands_on_today(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "Swayam", "email": "Swayam@Example.com", "password": "long enough 1", "timezone": "Asia/Kolkata"})
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    cookie = r.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie.lower() or "samesite=lax" in cookie.lower()
    home = b.get("/")
    assert home.status_code == 200
    assert "Swayam" in home.text
    assert user_row(b.c.app).email == "swayam@example.com"


def test_register_rejects_a_short_password(make_browser, app):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "Swayam", "email": "a@example.com", "password": "short", "timezone": "UTC"})
    assert r.status_code == 422
    assert "at least 8" in r.text
    assert user_row(app, "a@example.com") is None


def test_register_rejects_an_invalid_email(make_browser, app):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "Swayam", "email": "not-an-email", "password": "long enough 1", "timezone": "UTC"})
    assert r.status_code == 422
    assert "valid email" in r.text


def test_register_rejects_an_empty_name(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "  ", "email": "a@example.com", "password": "long enough 1", "timezone": "UTC"})
    assert r.status_code == 422


def test_register_rejects_a_duplicate_email(make_browser):
    make_browser().register()
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "Other", "email": "swayam@example.com", "password": "long enough 1", "timezone": "UTC"})
    assert r.status_code == 409
    assert "already exists" in r.text


def test_invalid_timezone_falls_back_to_utc(make_browser, app):
    b = make_browser()
    b.get("/register")
    b.post("/register", {"name": "Swayam", "email": "tz@example.com", "password": "long enough 1", "timezone": "Mars/Olympus"})
    assert user_row(app, "tz@example.com").timezone == "UTC"


def test_login_with_the_wrong_password_is_rejected(make_browser):
    make_browser().register()
    b = make_browser()
    b.get("/login")
    r = b.post("/login", {"email": "swayam@example.com", "password": "wrong password"})
    assert r.status_code == 401
    assert "Incorrect email or password" in r.text


def test_login_with_an_unknown_email_is_rejected(make_browser):
    b = make_browser()
    b.get("/login")
    r = b.post("/login", {"email": "ghost@example.com", "password": "long enough 1"})
    assert r.status_code == 401


def test_login_succeeds_and_normalises_the_email(make_browser):
    make_browser().register()
    b = make_browser()
    b.get("/login")
    r = b.post("/login", {"email": "  SWAYAM@EXAMPLE.COM ", "password": "long enough 1"})
    assert r.status_code == 303
    assert b.get("/").status_code == 200


def test_logout_ends_the_session(make_browser):
    b = make_browser().register()
    r = b.post("/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert b.get("/").headers["location"] == "/login"


def test_anonymous_visitors_are_redirected_to_login(make_browser):
    b = make_browser()
    for path in ["/", "/meetings", "/actions", "/decisions", "/memory", "/settings"]:
        r = b.get(path)
        assert r.status_code == 303, path
        assert r.headers["location"] == "/login"


def test_state_changing_forms_require_csrf(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "Swayam", "email": "a@example.com", "password": "long enough 1"}, csrf=False)
    assert r.status_code == 403


def test_session_expiry_sends_the_user_back_to_login(make_browser, app):
    b = make_browser().register()
    with app.state.sessionmaker() as db:
        session = db.scalar(select(Session))
        session.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    r = b.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_is_rate_limited(make_browser):
    make_browser().register()
    b = make_browser()
    b.get("/login")
    codes = []
    for _ in range(11):
        codes.append(b.post("/login", {"email": "swayam@example.com", "password": "wrong password"}).status_code)
    assert codes[-1] == 429


def test_logout_removes_the_server_side_session(make_browser, app):
    b = make_browser().register()
    with app.state.sessionmaker() as db:
        assert db.scalar(select(Session)) is not None
    b.post("/logout")
    with app.state.sessionmaker() as db:
        assert db.scalar(select(Session)) is None


def test_password_hash_is_never_returned_in_a_page(make_browser):
    b = make_browser().register()
    with b.c.app.state.sessionmaker() as db:
        stored = db.scalar(select(User)).password_hash
    assert "scrypt$" in stored
    for path in ["/", "/settings", "/meetings", "/actions"]:
        assert stored not in b.get(path).text
