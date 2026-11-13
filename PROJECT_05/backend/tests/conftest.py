from __future__ import annotations

import re
import shutil
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, run_migrations

TZ = "Asia/Kolkata"
_TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def today_local() -> date:
    return datetime.now(ZoneInfo(TZ)).date()


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
        r = self.c.post(url, data=data, headers=headers, **kw)
        m = _TOKEN.search(r.text)
        if m:
            self.token = m.group(1)
        return r

    def register(self, email="swayam@example.com", name="Swayam", tz=TZ):
        self.get("/register")
        r = self.post("/register", {"name": name, "email": email, "password": "long enough 1", "timezone": tz})
        assert r.status_code == 303, r.text
        self.get("/habits")  # always has a CSRF form, even before the first habit exists
        return self

    def login(self, email="swayam@example.com", password="long enough 1"):
        self.get("/login")
        r = self.post("/login", {"email": email, "password": password})
        if r.status_code == 303:
            self.get("/habits")
        return r

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


def create_habit(browser, title="Read 20 minutes", days=None, cue="After coffee", intention="Think longer.") -> int:
    r = browser.post(
        "/habits",
        {"title": title, "days": days if days is not None else ["0", "1", "2", "3", "4", "5", "6"], "cue": cue, "intention": intention},
    )
    assert r.status_code == 303, r.text
    return int(r.headers["location"].split("/habits/")[1].split("?")[0])


def log_day(browser, habit_id, day, status="done", note="", next_url="/"):
    return browser.post(
        f"/habits/{habit_id}/log",
        {"day": day.isoformat(), "status": status, "note": note, "next": next_url},
    )
