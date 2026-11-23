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
_CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')


def ist_today() -> date:
    """Today in the demo account's timezone, matching what the app calls 'today'."""
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


@pytest.fixture
def db(app):
    session = app.state.sessionmaker()
    try:
        yield session
    finally:
        session.close()


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


def add_venture(
    browser: Browser,
    *,
    name="Sahaj",
    one_liner="Scheduling and invoicing for solar installers.",
    stage="validating",
    horizon="90 days",
    currency="INR",
    market="",
    segment="Owner-run solar installers",
    alternatives="",
    differentiation="",
) -> int:
    r = browser.post(
        "/ventures/new",
        {
            "name": name,
            "one_liner": one_liner,
            "stage": stage,
            "horizon": horizon,
            "currency": currency,
            "market": market,
            "segment": segment,
            "alternatives": alternatives,
            "differentiation": differentiation,
        },
    )
    assert r.status_code == 303, r.text
    return int(r.headers["location"].split("/ventures/")[1].split("?")[0])


def add_canvas(browser: Browser, venture_id: int, block="problem", title="A real problem", detail=""):
    r = browser.post(
        f"/ventures/{venture_id}/canvas",
        {"block": block, "title": title, "detail": detail},
    )
    assert r.status_code == 303, r.text
    return r.headers["location"]


def add_swot(browser: Browser, venture_id: int, quadrant="strength", text="A real strength", impact="3", evidence=""):
    r = browser.post(
        f"/ventures/{venture_id}/swot",
        {"quadrant": quadrant, "text": text, "impact": impact, "evidence": evidence},
    )
    assert r.status_code == 303, r.text
    return r.headers["location"]


def add_stream(
    browser: Browser,
    venture_id: int,
    *,
    name="Installer subscription",
    model="subscription",
    price="1499",
    unit="per month",
    volume="40",
    confidence="high",
    notes="",
):
    r = browser.post(
        f"/ventures/{venture_id}/revenue/streams",
        {
            "name": name,
            "model": model,
            "price": price,
            "unit": unit,
            "volume": volume,
            "confidence": confidence,
            "notes": notes,
        },
    )
    assert r.status_code == 303, r.text
    return r.headers["location"]


def add_cost(browser: Browser, venture_id: int, *, name="Support contractor", amount="18000", kind="fixed", notes=""):
    r = browser.post(
        f"/ventures/{venture_id}/revenue/costs",
        {"name": name, "amount": amount, "kind": kind, "notes": notes},
    )
    assert r.status_code == 303, r.text
    return r.headers["location"]


def add_milestone(
    browser: Browser,
    venture_id: int,
    *,
    title="Ten paying customers",
    success_criterion="Ten accounts pay one invoice.",
    owner="Swayam",
    due_date: date | None = None,
    horizon="now",
    status="planned",
):
    r = browser.post(
        f"/ventures/{venture_id}/plan",
        {
            "title": title,
            "success_criterion": success_criterion,
            "owner": owner,
            "due_date": due_date.isoformat() if due_date else "",
            "horizon": horizon,
            "status": status,
        },
    )
    assert r.status_code == 303, r.text
    return r.headers["location"]


def add_kpi(
    browser: Browser,
    venture_id: int,
    *,
    name="Activated installers",
    unit="installers",
    direction="up",
    baseline="0",
    target="40",
    target_date: date | None = None,
    cadence="monthly",
):
    r = browser.post(
        f"/ventures/{venture_id}/kpis",
        {
            "name": name,
            "unit": unit,
            "direction": direction,
            "baseline": baseline,
            "target": target,
            "target_date": target_date.isoformat() if target_date else "",
            "cadence": cadence,
        },
    )
    assert r.status_code == 303, r.text
    return r.headers["location"]


def add_reading(browser: Browser, kpi_id: int, value="12", recorded_on: date | None = None, note=""):
    r = browser.post(
        f"/kpis/{kpi_id}/readings",
        {
            "value": value,
            "recorded_on": recorded_on.isoformat() if recorded_on else "",
            "note": note,
        },
    )
    assert r.status_code == 303, r.text
    return r.headers["location"]


def kpi_id_from(db, venture_name: str, kpi_name: str) -> int:
    from sqlalchemy import select

    from app.models import Kpi, Venture

    venture = db.scalar(select(Venture).where(Venture.name == venture_name))
    kpi = db.scalar(select(Kpi).where(Kpi.venture_id == venture.id, Kpi.name == kpi_name))
    return kpi.id
