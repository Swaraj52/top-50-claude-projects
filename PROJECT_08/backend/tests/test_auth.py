from __future__ import annotations

import pytest

from conftest import TZ, add_item


def test_health(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_protected_pages_redirect_to_login(make_browser):
    b = make_browser()
    for path in ("/", "/library", "/search", "/ask", "/clusters", "/collections", "/tags", "/items/new", "/settings"):
        r = b.get(path)
        assert r.status_code == 303, path
        assert r.headers["location"] == "/login"


def test_register_creates_session_and_dashboard(browser):
    r = browser.get("/")
    assert r.status_code == 200
    assert "What does your library know?" in r.text
    assert "Swayam" in r.text
    assert "An empty shelf, for now" in r.text


def test_register_rejects_bad_email(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "A", "email": "not-an-email", "password": "long enough 1"})
    assert r.status_code == 422
    assert "valid email" in r.text


def test_register_rejects_short_name(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "   ", "email": "a@b.example", "password": "long enough 1"})
    assert r.status_code == 422
    assert "Tell us your name" in r.text


def test_register_rejects_short_password(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "A", "email": "a@b.example", "password": "short"})
    assert r.status_code == 422
    assert "at least 8" in r.text


def test_register_rejects_duplicate_email(make_browser):
    b = make_browser()
    b.register(email="same@example.com")
    b2 = make_browser()
    b2.get("/register")
    r = b2.post("/register", {"name": "B", "email": "same@example.com", "password": "long enough 1"})
    assert r.status_code == 409
    assert "already exists" in r.text


def test_register_stores_a_valid_timezone(make_browser):
    b = make_browser()
    b.register(tz=TZ)
    r = b.get("/settings")
    assert f'value="{TZ}"' in r.text


def test_register_falls_back_to_utc_for_an_unknown_timezone(make_browser):
    b = make_browser()
    b.register(tz="Mars/Olympus")
    r = b.get("/settings")
    assert 'value="UTC"' in r.text


def test_login_and_logout(make_browser):
    first = make_browser().register(email="loop@example.com", password="long enough 1")
    first.close()
    b = make_browser()
    assert b.login(email="loop@example.com").status_code == 303
    assert b.get("/").status_code == 200
    r = b.post("/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert b.get("/").status_code == 303


def test_login_wrong_password(make_browser):
    make_browser().register(email="wrong@example.com")
    b = make_browser()
    r = b.login(email="wrong@example.com", password="nope nope nope")
    assert r.status_code == 401
    assert "Incorrect email or password" in r.text


def test_login_unknown_email_is_rejected(make_browser):
    b = make_browser()
    r = b.login(email="nobody@example.com", password="long enough 1")
    assert r.status_code == 401
    assert "Incorrect email or password" in r.text


def test_login_rate_limit_after_ten_failures(make_browser):
    make_browser().register(email="limit@example.com")
    b = make_browser()
    for _ in range(10):
        assert b.login(email="limit@example.com", password="wrong wrong wrong").status_code == 401
    r = b.login(email="limit@example.com", password="wrong wrong wrong")
    assert r.status_code == 429
    assert "Too many failed attempts" in r.text


def test_login_page_redirects_when_already_signed_in(browser):
    r = browser.get("/login")
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_register_page_redirects_when_already_signed_in(browser):
    r = browser.get("/register")
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_post_without_csrf_is_refused(browser):
    r = browser.post("/items/new", {"title": "No token", "body": "x"}, csrf=False)
    assert r.status_code == 403


def test_post_with_a_stale_csrf_token_is_refused(browser):
    r = browser.post("/items/new", {"title": "Bad token", "body": "x", "csrf_token": "nope"})
    assert r.status_code == 403


def test_register_post_needs_the_pre_csrf_cookie(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "A", "email": "cookie@example.com", "password": "long enough 1", "csrf_token": "wrong"})
    assert r.status_code == 403


def test_sessions_are_isolated_between_accounts(make_browser):
    a = make_browser().register(email="a@example.com")
    item_id = add_item(a, title="A private note", body="Only for A.")
    b = make_browser().register(email="b@example.com", name="B")
    assert b.get("/library").status_code == 200
    assert "A private note" not in b.get("/library").text
    assert b.get(f"/items/{item_id}").status_code == 404
    assert b.get(f"/items/{item_id}/edit").status_code == 404


def test_logout_ends_this_session_only(make_browser):
    a = make_browser().register(email="two@example.com")
    b = make_browser()
    b.login(email="two@example.com")
    a.post("/logout")
    assert a.get("/").status_code == 303
    assert b.get("/").status_code == 200


def test_security_headers_are_present(browser):
    r = browser.get("/")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "same-origin"


def test_password_hash_is_not_the_password(app, browser):
    from sqlalchemy import select

    from app.db import make_sessionmaker
    from app.models import User

    Session = make_sessionmaker(app.state.engine)
    with Session() as db:
        user = db.scalar(select(User).where(User.email == "swayam@example.com"))
        assert user is not None
        assert user.password_hash != "long enough 1"
        assert "$" in user.password_hash


@pytest.mark.parametrize("path", ["/", "/library", "/search", "/ask", "/clusters", "/collections", "/tags", "/settings", "/items/new"])
def test_signed_in_pages_render(browser, path):
    assert browser.get(path).status_code == 200


def test_unknown_page_renders_the_error_shell(browser):
    r = browser.get("/not-a-page")
    assert r.status_code == 404
    assert "Error 404" in r.text
    assert "doesn&#39;t exist" in r.text
