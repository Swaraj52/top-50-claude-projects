from fastapi.testclient import TestClient


def test_register_signs_in_and_me_returns_user(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json() == {"id": 1, "email": "ana@example.com", "name": "Ana", "timezone": "Asia/Kolkata"}


def test_session_cookie_is_httponly_and_lax(anon):
    r = anon.post(
        "/api/auth/register",
        json={"email": "c@example.com", "password": "longenough", "name": "C"},
    )
    cookie = r.headers["set-cookie"].lower()
    assert "pd_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie


def test_email_is_case_insensitive_and_unique(client, anon):
    r = anon.post(
        "/api/auth/register",
        json={"email": "ANA@Example.com", "password": "another-pass", "name": "Imposter"},
    )
    assert r.status_code == 409


def test_register_validation_message_is_readable(anon):
    r = anon.post("/api/auth/register", json={"email": "x@example.com", "password": "short", "name": "X"})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("password:")


def test_register_rejects_unknown_timezone(anon):
    r = anon.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "longenough", "name": "X", "timezone": "Mars/Base"},
    )
    assert r.status_code == 422


def test_login_logout_cycle(client, anon):
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    bad = anon.post("/api/auth/login", json={"email": "ana@example.com", "password": "nope"})
    assert bad.status_code == 401
    good = anon.post("/api/auth/login", json={"email": "ana@example.com", "password": "correct horse 1"})
    assert good.status_code == 200
    assert anon.get("/api/auth/me").json()["email"] == "ana@example.com"


def test_unknown_email_gets_same_error_as_wrong_password(anon):
    r = anon.post("/api/auth/login", json={"email": "ghost@example.com", "password": "whatever"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"


def test_login_is_rate_limited_after_ten_failures(client, anon):
    for _ in range(10):
        assert anon.post("/api/auth/login", json={"email": "ana@example.com", "password": "x"}).status_code == 401
    r = anon.post("/api/auth/login", json={"email": "ana@example.com", "password": "correct horse 1"})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


def test_protected_routes_need_a_session(anon):
    for path in ("/api/tasks", "/api/dashboard/today", "/api/calendars", "/api/email/account"):
        assert anon.get(path).status_code == 401, path


def test_mutations_without_csrf_header_are_rejected(app, client):
    raw = TestClient(app, cookies=client.cookies)
    r = raw.post("/api/tasks", json={"title": "sneaky"})
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]
    # Reads stay allowed without the header.
    assert raw.get("/api/tasks").status_code == 200


def test_update_profile(client):
    r = client.patch("/api/auth/me", json={"name": "Ana P", "timezone": "Europe/London"})
    assert r.status_code == 200
    assert r.json()["timezone"] == "Europe/London"
    assert client.patch("/api/auth/me", json={"timezone": "Nowhere/Land"}).status_code == 422


def test_password_is_not_stored_in_plaintext(app, client):
    from sqlalchemy import select

    from app.models import User

    with app.state.sessionmaker() as db:
        stored = db.scalar(select(User.password_hash))
    assert stored.startswith("scrypt$") and "correct horse" not in stored


def test_health_and_meta(anon):
    assert anon.get("/api/health").json() == {"status": "ok"}
    meta = anon.get("/api/meta").json()
    assert meta["ai_enabled"] is False and meta["ai_model"] is None
