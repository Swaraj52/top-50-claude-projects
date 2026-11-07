"""Security primitives, migrations and SPA serving."""

import time

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.config import Settings
from app.db import Base
from app.main import create_app
from app.security import SecretBox, SlidingWindowLimiter, hash_password, verify_password


def test_password_hashing():
    stored = hash_password("s3cret-pass")
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong", stored)
    assert hash_password("s3cret-pass") != stored  # salted
    assert not verify_password("x", "not-a-hash")


def test_secret_box_round_trip_and_wrong_key():
    token = SecretBox("key-one").encrypt("imap-password")
    assert "imap-password" not in token
    assert SecretBox("key-one").decrypt(token) == "imap-password"
    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        SecretBox("key-two").decrypt(token)


def test_sliding_window_limiter():
    limiter = SlidingWindowLimiter(limit=2, window=0.2)
    limiter.hit("k")
    assert not limiter.blocked("k")
    limiter.hit("k")
    assert limiter.blocked("k") and not limiter.blocked("other")
    time.sleep(0.25)
    assert not limiter.blocked("k")


def test_migrations_match_the_models(migrated_db):
    engine = create_engine(f"sqlite:///{migrated_db.as_posix()}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


@pytest.fixture
def spa_client(tmp_path, settings):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app shell</html>")
    (dist / "assets" / "app.js").write_text("console.log('hi')")
    (tmp_path / "secret.txt").write_text("do not serve")
    app = create_app(Settings(**{**settings.model_dump(), "frontend_dist": dist}, _env_file=None))
    with TestClient(app) as c:
        yield c
    app.state.engine.dispose()


def test_spa_serves_assets_and_falls_back_to_index(spa_client):
    assert spa_client.get("/assets/app.js").text == "console.log('hi')"
    assert spa_client.get("/").text == "<html>app shell</html>"
    assert spa_client.get("/tasks").text == "<html>app shell</html>"  # client-side route
    assert "do not serve" not in spa_client.get("/..%2Fsecret.txt").text
    r = spa_client.get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
