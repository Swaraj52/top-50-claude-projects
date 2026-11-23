"""Request helpers: sessions, CSRF, templates and redirects for the server-rendered UI."""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from . import __version__
from .db import utcnow
from .models import (
    AREAS,
    AREA_LABELS,
    CADENCES,
    CADENCE_LABELS,
    REVIEW_LABELS,
    REVIEW_MONTHS,
    RUN_STATUS_LABELS,
    SOP_STATUSES,
    SOP_STATUS_LABELS,
    Session,
    User,
)
from .security import hash_token
from .timeutil import local_today, relative_label, zone

SESSION_COOKIE = "fd_session"
PRE_CSRF_COOKIE = "fd_csrf"

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _dt(value: datetime | None, tz: ZoneInfo | None = None, fmt: str = "short") -> str:
    if value is None:
        return "—"
    local = value.astimezone(tz) if tz else value
    if fmt == "day":
        return f"{local:%d %b %Y}"
    if fmt == "stamp":
        return f"{local:%d %b %Y, %H:%M}"
    if fmt == "iso":
        return local.strftime("%Y-%m-%dT%H:%M")
    return f"{local:%d %b}"


def _date(value: date | None) -> str:
    return f"{value:%d %b %Y}" if value else "No date"


def _days(value: date | None, today: date | None = None) -> str:
    if value is None:
        return "no date"
    today = today or date.today()
    days = (value - today).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "1 day overdue"
    if days < 0:
        return f"{abs(days)} days overdue"
    return f"in {days} days"


def _initial(value: str | None) -> str:
    return (value or "?").strip()[:1].upper()


templates.env.filters["dt"] = _dt
templates.env.filters["datefmt"] = _date
templates.env.filters["days"] = _days
templates.env.filters["initial"] = _initial
templates.env.filters["area"] = lambda value: AREA_LABELS.get(value, str(value).title())
templates.env.filters["sstatus"] = lambda value: SOP_STATUS_LABELS.get(value, str(value).title())
templates.env.filters["cadence"] = lambda value: CADENCE_LABELS.get(value, str(value).title())
templates.env.filters["rstatus"] = lambda value: RUN_STATUS_LABELS.get(value, str(value).title())
templates.env.filters["review"] = lambda value: REVIEW_LABELS.get(value, f"Every {value} months")
templates.env.filters["relative"] = lambda value: relative_label(value, utcnow()) if value else "—"
templates.env.globals["version"] = __version__
templates.env.globals["AREAS"] = [(key, AREA_LABELS[key]) for key in AREAS]
templates.env.globals["SOP_STATUS_OPTIONS"] = [(key, SOP_STATUS_LABELS[key]) for key in SOP_STATUSES]
templates.env.globals["CADENCE_OPTIONS"] = [(key, CADENCE_LABELS[key]) for key in CADENCES]
templates.env.globals["REVIEW_OPTIONS"] = [(months, REVIEW_LABELS[months]) for months in REVIEW_MONTHS]


class LoginRequired(Exception):
    """Raised by page dependencies; turned into a redirect to /login."""


@dataclass
class Ctx:
    user: User
    session: Session
    tz: ZoneInfo
    today: date
    now: datetime


def get_db(request: Request) -> Iterator[DbSession]:
    db = request.app.state.sessionmaker()
    try:
        yield db
    finally:
        db.close()


def optional_ctx(request: Request, db: DbSession = Depends(get_db)) -> Ctx | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = db.scalar(select(Session).where(Session.token_hash == hash_token(token)))
    if session is None or session.expires_at <= utcnow():
        return None
    return Ctx(
        user=session.user,
        session=session,
        tz=zone(session.user.timezone),
        today=local_today(zone(session.user.timezone)),
        now=utcnow(),
    )


def ctx(c: Ctx | None = Depends(optional_ctx)) -> Ctx:
    if c is None:
        raise LoginRequired()
    return c


async def csrf(request: Request, c: Ctx = Depends(ctx)) -> Ctx:
    sent = request.headers.get("x-csrf-token")
    if not sent:
        form = await request.form()
        sent = str(form.get("csrf_token", ""))
    if not sent or not hmac.compare_digest(sent, c.session.csrf_token):
        raise HTTPException(403, "Your session form expired. Reload the page and try again.")
    return c


async def pre_csrf(request: Request) -> None:
    form = await request.form()
    cookie = request.cookies.get(PRE_CSRF_COOKIE, "")
    sent = str(form.get("csrf_token", ""))
    if not cookie or not hmac.compare_digest(sent, cookie):
        raise HTTPException(403, "The form expired. Reload the page and try again.")


def new_pre_csrf() -> str:
    return secrets.token_urlsafe(24)


def is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def safe_next(value: str | None, fallback: str = "/") -> str:
    """Only same-site absolute paths are allowed as redirect targets."""
    if not value:
        return fallback
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return fallback
    return value


def render(request: Request, name: str, c: Ctx | None, http_status: int = 200, **context):
    settings = request.app.state.settings
    base = {
        "user": c.user if c else None,
        "csrf_token": c.session.csrf_token if c else "",
        "today": c.today if c else None,
        "now": c.now if c else utcnow(),
        "tz": c.tz if c else ZoneInfo("UTC"),
        "ai_enabled": settings.ai_enabled,
        "ai_model": settings.anthropic_model if settings.ai_enabled else None,
        "path": request.url.path,
    }
    return templates.TemplateResponse(request, name, {**base, **context}, status_code=http_status)


def see_other(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)
