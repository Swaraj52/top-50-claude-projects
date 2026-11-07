from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, run_migrations

TZ = "Asia/Kolkata"  # +05:30, no DST: makes "today" differ from UTC near midnight


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory) -> Path:
    """Run the Alembic migrations once; each test gets a copy of the result."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    run_migrations(f"sqlite:///{path.as_posix()}")
    return path


@pytest.fixture
def settings(tmp_path, migrated_db) -> Settings:
    db_file = tmp_path / "test.db"
    shutil.copy(migrated_db, db_file)
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_file.as_posix()}",
        app_secret_key="test-secret-key",
        anthropic_api_key="",
        run_migrations=False,
        frontend_dist=tmp_path / "no-frontend",
    )


@pytest.fixture
def app(settings):
    application = create_app(settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def make_client(app) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def _make(email: str | None = None, name: str = "Ana", tz: str = TZ) -> TestClient:
        c = TestClient(app, headers={"X-Requested-With": "dashboard"})
        c.__enter__()
        clients.append(c)
        if email:
            r = c.post(
                "/api/auth/register",
                json={"email": email, "password": "correct horse 1", "name": name, "timezone": tz},
            )
            assert r.status_code == 201, r.text
        return c

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    """A signed-in client for ana@example.com in Asia/Kolkata."""
    return make_client("ana@example.com")


@pytest.fixture
def anon(make_client) -> TestClient:
    return make_client()
