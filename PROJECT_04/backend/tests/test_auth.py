from __future__ import annotations


def test_signed_out_redirects_to_login(app):
    from fastapi.testclient import TestClient

    c = TestClient(app, follow_redirects=False)
    r = c.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert "Content-Security-Policy" in c.get("/login").headers


def test_register_signs_in_and_shows_empty_state(browser):
    r = browser.get("/")
    assert r.status_code == 200
    assert "Swayam" in r.text
    assert "No goals yet" in r.text
    assert "built by Swayam" in r.text


def test_duplicate_email_rejected(make_browser):
    b = make_browser()
    b.get("/register")
    b.post("/register", {"name": "Swayam", "email": "swayam@example.com", "password": "long enough 1", "timezone": "UTC"})
    b2 = make_browser()
    r = b2.get("/register")
    assert r.status_code == 200
    r = b2.post("/register", {"name": "Other", "email": "swayam@example.com", "password": "long enough 1", "timezone": "UTC"})
    assert r.status_code == 409
    assert "already exists" in r.text


def test_login_validation_and_wrong_password(make_browser):
    b = make_browser().register()
    b.post("/logout")
    b.get("/login")
    r = b.post("/login", {"email": "swayam@example.com", "password": "wrong password"})
    assert r.status_code == 401
    r = b.post("/login", {"email": "swayam@example.com", "password": "long enough 1"})
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_csrf_required_for_state_change(browser):
    r = browser.post("/goals", {"title": "A goal", "category": "health"}, csrf=False)
    assert r.status_code == 403


def test_invalid_email_and_short_password(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "A", "email": "not-an-email", "password": "long enough 1", "timezone": "UTC"})
    assert r.status_code == 422
    r = b.post("/register", {"name": "A", "email": "a@example.com", "password": "short", "timezone": "UTC"})
    assert r.status_code == 422


def test_xss_is_escaped(browser):
    browser.post("/goals", {"title": "<script>alert(1)</script>", "category": "personal"})
    r = browser.get("/")
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text


def test_logout_clears_access(browser):
    browser.post("/logout")
    r = browser.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
