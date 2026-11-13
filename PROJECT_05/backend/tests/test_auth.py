from __future__ import annotations


def test_register_creates_account_and_signs_in(browser):
    page = browser.get("/")
    assert page.status_code == 200
    assert "Keep the rhythm you chose." in page.text
    assert "Swayam" in page.text


def test_register_rejects_duplicate_email(make_browser):
    first = make_browser().register(email="same@example.com")
    second = make_browser()
    second.get("/register")
    r = second.post(
        "/register",
        {"name": "Other", "email": "same@example.com", "password": "another long 1", "timezone": "UTC"},
    )
    assert r.status_code == 409
    assert "already exists" in r.text


def test_register_rejects_short_password(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "Sam", "email": "sam@example.com", "password": "short", "timezone": "UTC"})
    assert r.status_code == 422
    assert "at least 8 characters" in r.text


def test_register_rejects_bad_email(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "Sam", "email": "not-an-email", "password": "long enough 1", "timezone": "UTC"})
    assert r.status_code == 422
    assert "valid email" in r.text


def test_register_requires_pre_csrf(make_browser):
    b = make_browser()
    b.get("/register")
    r = b.post("/register", {"name": "Sam", "email": "sam@example.com", "password": "long enough 1", "timezone": "UTC"}, csrf=False)
    assert r.status_code == 403


def test_login_and_logout(make_browser):
    make_browser().register(email="login@example.com")
    b = make_browser()
    r = b.login(email="login@example.com")
    assert r.status_code == 303
    assert b.get("/").status_code == 200
    out = b.post("/logout")
    assert out.status_code == 303
    assert out.headers["location"] == "/login"
    after = b.get("/", follow_redirects=False)
    assert after.status_code == 303
    assert after.headers["location"] == "/login"


def test_login_wrong_password(make_browser):
    make_browser().register(email="wrong@example.com")
    b = make_browser()
    r = b.login(email="wrong@example.com", password="definitely wrong")
    assert r.status_code == 401
    assert "Incorrect email or password" in r.text


def test_login_is_rate_limited(make_browser):
    b = make_browser()
    b.get("/login")
    last = None
    for _ in range(11):
        last = b.post("/login", {"email": "nobody@example.com", "password": "wrong password"})
    assert last.status_code == 429
    assert "Too many failed attempts" in last.text


def test_anonymous_visit_redirects(make_browser):
    b = make_browser()
    r = b.get("/habits")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_anonymous_htmx_request_gets_redirect_header(make_browser):
    b = make_browser()
    r = b.c.get("/habits", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 401
    assert r.headers["HX-Redirect"] == "/login"


def test_login_page_has_timezone_field(make_browser):
    b = make_browser()
    page = b.get("/register")
    assert 'data-browser-timezone' in page.text
