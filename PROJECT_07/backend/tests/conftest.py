from __future__ import annotations

import re
import shutil
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, run_migrations

TZ = "Asia/Kolkata"
_CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')


def today_local() -> date:
    return datetime.now(ZoneInfo(TZ)).date()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        self.get("/inbox")
        return self

    def login(self, email="swayam@example.com", password="long enough 1"):
        self.get("/login")
        r = self.post("/login", {"email": email, "password": password})
        if r.status_code == 303:
            self.get("/inbox")
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
    "Hi Swayam,\n\nCould you review the pricing section and confirm the numbers by Friday? "
    "The board pack goes out on Monday.\n\nThanks,\nPriya"
)


def compose(
    browser: Browser,
    *,
    sender="Priya Raman <priya@lumen.example>",
    recipients="swayam@example.com",
    subject="Q4 launch checklist",
    body=DEFAULT_BODY,
    received_at="",
    mailbox_id="",
    files=None,
):
    """Log an email through the real form and return the new thread id."""
    data = {
        "sender": sender,
        "recipients": recipients,
        "subject": subject,
        "body": body,
        "received_at": received_at,
    }
    if mailbox_id != "":
        data["mailbox_id"] = mailbox_id
    r = browser.post("/compose", data, files=files)
    assert r.status_code == 303, r.text
    location = r.headers["location"]
    return int(location.split("/threads/")[1].split("?")[0].split("#")[0])


def make_eml(
    *,
    sender="Priya Raman <priya@lumen.example>",
    recipients="swayam@example.com",
    subject="Import me",
    body="Hello from a real .eml file.\n\nCould you confirm by Friday?",
    message_id="<eml-1@lumen.example>",
    date="Fri, 13 Nov 2026 09:30:00 +0530",
) -> bytes:
    lines = [
        f"From: {sender}",
        f"To: {recipients}",
        f"Subject: {subject}",
        f"Date: {date}",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=utf-8",
    ]
    if message_id:
        lines.append(f"Message-ID: {message_id}")
    return ("\r\n".join(lines) + "\r\n\r\n" + body + "\r\n").encode("utf-8")
