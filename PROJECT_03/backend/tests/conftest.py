from __future__ import annotations

import re
import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, run_migrations

TZ = "Asia/Kolkata"
_TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("template") / "template.db"
    run_migrations(f"sqlite:///{path.as_posix()}")
    return path


@pytest.fixture
def settings(tmp_path, migrated_db) -> Settings:
    db_file = tmp_path / "test.db"
    shutil.copy(migrated_db, db_file)
    return Settings(_env_file=None, database_url=f"sqlite:///{db_file.as_posix()}", anthropic_api_key="", run_migrations=False)


@pytest.fixture
def app(settings):
    application = create_app(settings)
    yield application
    application.state.engine.dispose()


class Browser:
    """A TestClient that fills in CSRF tokens the way the real pages do."""

    def __init__(self, app):
        self.c = TestClient(app, follow_redirects=False)
        self.c.__enter__()
        self.token = ""

    def get(self, url, **kw):
        r = self.c.get(url, **kw)
        m = _TOKEN.search(r.text)
        if m:
            self.token = m.group(1)
        return r

    def post(self, url, data=None, htmx=False, csrf=True, **kw):
        data = dict(data or {})
        if csrf:
            data.setdefault("csrf_token", self.token)
        headers = {"HX-Request": "true"} if htmx else {}
        return self.c.post(url, data=data, headers=headers, **kw)

    def register(self, email="swayam@example.com", name="Swayam", tz=TZ):
        self.get("/register")
        r = self.post("/register", {"name": name, "email": email, "password": "long enough 1", "timezone": tz})
        assert r.status_code == 303, r.text
        self.get("/today")  # pick up the session's CSRF token
        return self

    def close(self):
        self.c.__exit__(None, None, None)


@pytest.fixture
def make_browser(app):
    made = []

    def _make():
        b = Browser(app)
        made.append(b)
        return b

    yield _make
    for b in made:
        b.close()


@pytest.fixture
def browser(make_browser) -> Browser:
    return make_browser().register()
