from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Session, User
from app.security import hash_token

from conftest import Browser, add_venture


def test_health_is_public_and_reports_version(browser):
    r = browser.c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"] == "1.0.0"


def test_root_redirects_anonymous_to_login(make_browser):
    r = make_browser().c.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_htmx_anonymous_gets_401_and_redirect_header(make_browser):
    r = make_browser().c.get("/", headers={"HX-Request": "true"})
    assert r.status_code == 401
    assert r.headers["HX-Redirect"] == "/login"


@pytest.mark.parametrize("path", ["/", "/ventures/new", "/settings", "/settings/export"])
def test_private_pages_require_login(make_browser, path):
    r = make_browser().c.get(path)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_and_register_pages_are_public(make_browser):
    anon = make_browser()
    assert anon.c.get("/login").status_code == 200
    assert anon.c.get("/register").status_code == 200


def test_register_creates_user_session_and_cookie(make_browser):
    anon = make_browser()
    anon.get("/register")
    r = anon.post(
        "/register",
        {"name": "Swayam", "email": "New@Example.com", "password": "long enough 1", "timezone": "Asia/Kolkata"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert "ks_session" in r.cookies
    assert "ks_csrf" not in r.cookies


def test_register_stores_a_scrypt_hash_not_the_password(make_browser, db):
    anon = make_browser()
    anon.get("/register")
    anon.post(
        "/register",
        {"name": "Swayam", "email": "hash@example.com", "password": "long enough 1", "timezone": "UTC"},
    )
    user = db.scalar(select(User).where(User.email == "hash@example.com"))
    assert user is not None
    assert user.password_hash.startswith("scrypt$")
    assert "long enough 1" not in user.password_hash


def test_register_stores_the_session_as_a_hash(make_browser, app, db):
    anon = make_browser()
    anon.get("/register")
    r = anon.post(
        "/register",
        {"name": "Swayam", "email": "session@example.com", "password": "long enough 1", "timezone": "UTC"},
    )
    token = r.cookies["ks_session"]
    stored = db.scalar(select(Session))
    assert stored.token_hash == hash_token(token)
    assert stored.token_hash != token


@pytest.mark.parametrize(
    ("email", "password", "name", "status"),
    [
        ("not-an-email", "long enough 1", "Swayam", 422),
        ("short@example.com", "short", "Swayam", 422),
        ("", "long enough 1", "Swayam", 422),
        ("no-name@example.com", "long enough 1", "", 422),
        ("long-name@example.com", "long enough 1", "x" * 81, 422),
    ],
)
def test_register_rejects_invalid_input(make_browser, email, password, name, status):
    anon = make_browser()
    anon.get("/register")
    r = anon.post("/register", {"name": name, "email": email, "password": password, "timezone": "UTC"})
    assert r.status_code == status
    assert 'role="alert"' in r.text


def test_register_rejects_a_duplicate_email(make_browser):
    first = make_browser()
    first.get("/register")
    first.post(
        "/register",
        {"name": "Swayam", "email": "dup@example.com", "password": "long enough 1", "timezone": "UTC"},
    )
    other = make_browser()
    other.get("/register")
    r = other.post(
        "/register",
        {"name": "Other", "email": "DUP@example.com", "password": "long enough 2", "timezone": "UTC"},
    )
    assert r.status_code == 409
    assert "already exists" in r.text


def test_register_falls_back_to_utc_for_an_unknown_timezone(make_browser, db):
    anon = make_browser()
    anon.get("/register")
    anon.post(
        "/register",
        {"name": "Swayam", "email": "tz@example.com", "password": "long enough 1", "timezone": "Mars/Olympus"},
    )
    user = db.scalar(select(User).where(User.email == "tz@example.com"))
    assert user.timezone == "UTC"


def test_registered_user_lands_on_an_empty_portfolio(browser):
    r = browser.get("/")
    assert r.status_code == 200
    assert "Start with one sentence" in r.text
    assert "Built by" in r.text and "Swayam" in r.text


def test_authenticated_user_is_redirected_away_from_auth_pages(browser):
    assert browser.c.get("/login").headers["location"] == "/"
    assert browser.c.get("/register").headers["location"] == "/"


def test_logout_ends_the_session(browser, db):
    r = browser.post("/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert browser.c.get("/").headers["location"] == "/login"
    assert db.scalar(select(Session)) is None


def test_logout_requires_csrf(browser):
    r = browser.c.post("/logout")
    assert r.status_code == 403
    assert browser.c.get("/").status_code == 200


def test_login_works_with_the_right_password(browser, make_browser):
    other = make_browser()
    r = other.login(email="swayam@example.com", password="long enough 1")
    assert r.status_code == 303
    assert other.c.get("/").status_code == 200


def test_login_is_case_insensitive_on_email(browser, make_browser):
    other = make_browser()
    assert other.login(email="SWAYAM@example.com", password="long enough 1").status_code == 303


def test_login_rejects_a_wrong_password(browser, make_browser):
    other = make_browser()
    r = other.login(email="swayam@example.com", password="wrong password")
    assert r.status_code == 401
    assert "Incorrect email or password" in r.text
    assert other.c.get("/").headers["location"] == "/login"


def test_login_rejects_an_unknown_email(browser, make_browser):
    other = make_browser()
    r = other.login(email="nobody@example.com", password="long enough 1")
    assert r.status_code == 401


def test_login_rate_limit_blocks_after_ten_failures(browser, make_browser):
    other = make_browser()
    other.get("/login")
    statuses = []
    for _ in range(11):
        r = other.post("/login", {"email": "swayam@example.com", "password": "wrong password"})
        statuses.append(r.status_code)
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_login_requires_the_pre_csrf_cookie(browser, make_browser):
    other = make_browser()
    r = other.c.post("/login", data={"email": "swayam@example.com", "password": "long enough 1"})
    assert r.status_code == 403


def test_login_rejects_a_foreign_csrf_token(browser, make_browser):
    other = make_browser()
    other.get("/login")
    r = other.c.post(
        "/login",
        data={"email": "swayam@example.com", "password": "long enough 1", "csrf_token": "forged"},
    )
    assert r.status_code == 403


def test_form_action_requires_the_session_csrf_token(browser):
    r = browser.post("/ventures/new", {"name": "No token"}, csrf=False)
    assert r.status_code == 403


def test_form_action_rejects_a_forged_csrf_token(browser):
    r = browser.post("/ventures/new", {"name": "Forged", "csrf_token": "not-the-token"})
    assert r.status_code == 403


def test_htmx_form_error_returns_a_trigger_not_a_page(browser):
    r = browser.c.post(
        "/ventures/new",
        data={"name": "Forged", "csrf_token": "not-the-token"},
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 403
    assert r.headers["HX-Reswap"] == "none"


def test_security_headers_are_present(browser):
    r = browser.get("/")
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "same-origin"


def test_csp_forbids_inline_scripts(browser):
    r = browser.get("/")
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
    assert "<script>" not in r.text


def test_a_tampered_session_cookie_is_rejected(browser):
    browser.c.cookies.clear()
    browser.c.cookies.set("ks_session", "not-a-real-token")
    r = browser.c.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_an_expired_session_is_rejected(browser, db):
    from datetime import timedelta

    from app.db import utcnow

    session = db.scalar(select(Session))
    session.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    r = browser.c.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_unknown_pages_render_a_friendly_error(browser):
    r = browser.get("/no-such-page")
    assert r.status_code == 404
    assert "Error 404" in r.text and "exist" in r.text


def test_unknown_venture_ids_are_404_not_500(browser):
    r = browser.get("/ventures/9999")
    assert r.status_code == 404
    assert "Error 404" in r.text and "exist" in r.text


def test_two_accounts_are_isolated(browser, make_browser):
    venture_id = add_venture(browser, name="Mine")
    other = make_browser().register(email="other@example.com", name="Other")
    assert other.c.get(f"/ventures/{venture_id}").status_code == 404
    assert "Mine" not in other.c.get("/").text


def test_static_assets_are_served(browser):
    for path in ("/static/app.css", "/static/app.js", "/static/htmx.min.js", "/static/favicon.svg"):
        assert browser.c.get(path).status_code == 200, path


def test_error_page_keeps_the_credit_for_a_signed_in_user(browser):
    r = browser.get("/no-such-page")
    assert "Built by" in r.text
