from __future__ import annotations

import re
import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, run_migrations

TZ = "Asia/Kolkata"
_CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory):
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
        anthropic_api_key="",
        run_migrations=False,
    )


@pytest.fixture
def app(settings):
    application = create_app(settings)
    yield application
    application.state.engine.dispose()


class Browser:
    """A TestClient that carries the CSRF token the way the real pages do."""

    def __init__(self, app):
        self.c = TestClient(app, follow_redirects=False)
        self.c.__enter__()
        self.token = ""

    def get(self, url, **kw):
        r = self.c.get(url, **kw)
        m = _CSRF.search(r.text)
        if m:
            self.token = m.group(1)
        return r

    def post(self, url, data=None, files=None, csrf=True, **kw):
        data = dict(data or {})
        if csrf:
            data.setdefault("csrf_token", self.token)
        r = self.c.post(url, data=data, files=files, **kw)
        m = _CSRF.search(r.text)
        if m:
            self.token = m.group(1)
        return r

    def register(self, email="swayam@example.com", name="Swayam", tz=TZ, password="long enough 1"):
        self.get("/register")
        r = self.post("/register", {"name": name, "email": email, "password": password, "timezone": tz})
        assert r.status_code == 303, r.text
        self.get("/")
        return self

    def login(self, email="swayam@example.com", password="long enough 1"):
        self.get("/login")
        r = self.post("/login", {"email": email, "password": password})
        if r.status_code == 303:
            self.get("/")
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


DEFAULT_BODY = (
    "We reviewed the pricing page and agreed the Starter plan keeps its current price until the "
    "January renewal cycle. The Growth plan moves to usage-based pricing, reviewed monthly.\n\n"
    "Open question: does the pricing page need a separate calculator, or can the estimate live "
    "inside the trial signup? Priya will test both with five customers."
)


def add_item(
    browser: Browser,
    *,
    title="Pricing review notes",
    body=DEFAULT_BODY,
    kind="note",
    tags="pricing, decisions",
    author="",
    source_url="",
    collection_id="",
    starred="",
):
    """Add an item through the real form and return its id."""
    data = {
        "title": title,
        "body": body,
        "kind": kind,
        "tags": tags,
        "author": author,
        "source_url": source_url,
        "collection_id": collection_id,
        "starred": starred,
    }
    r = browser.post("/items/new", data)
    assert r.status_code == 303, r.text
    return int(r.headers["location"].split("/items/")[1].split("/")[0])


def add_collection(browser: Browser, name="Client work", description=""):
    r = browser.post("/collections", {"name": name, "description": description})
    assert r.status_code == 303, r.text
    return r.headers["location"]
