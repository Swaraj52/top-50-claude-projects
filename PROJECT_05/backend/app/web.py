"""Request helpers: sessions, CSRF, templates and redirects for the server-rendered UI."""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from . import __version__
from .db import utcnow
from .models import Session, User
from .security import hash_token
from .timeutil import WEEKDAYS, local_today, monday_of, parse_days, schedule_label, zone

SESSION_COOKIE = "cd_session"
PRE_CSRF_COOKIE = "cd_csrf"

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _date(value: date | None, fmt: str = "short") -> str:
    if value is None:
        return "No date"
    if fmt == "long":
        return f"{value:%d %b %Y}"
    if fmt == "weekday":
        return f"{value:%a %d %b}"
    return f"{value:%d %b}"


def _pct(value: float | None) -> str:
    return f"{round(value or 0)}%"


templates.env.filters["datefmt"] = _date
templates.env.filters["pct"] = _pct
templates.env.filters["schedule"] = schedule_label
templates.env.filters["dayname"] = lambda d: [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
][int(d)] if 0 <= int(d) <= 6 else "?"
templates.env.globals["version"] = __version__
templates.env.globals["weekdays"] = WEEKDAYS


class LoginRequired(Exception):
    """Raised by page dependencies; turned into a redirect to /login."""


@dataclass
class Ctx:
    user: User
    session: Session
    tz: ZoneInfo
    today: date
    week_start: date


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
    today = local_today(zone(session.user.timezone))
    return Ctx(
        user=session.user,
        session=session,
        tz=zone(session.user.timezone),
        today=today,
        week_start=monday_of(today),
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


def render(request: Request, name: str, c: Ctx | None, status: int = 200, **context):
    settings = request.app.state.settings
    base = {
        "user": c.user if c else None,
        "csrf_token": c.session.csrf_token if c else "",
        "today": c.today if c else None,
        "week_start": c.week_start if c else None,
        "ai_enabled": settings.ai_enabled,
        "ai_model": settings.anthropic_model if settings.ai_enabled else None,
        "path": request.url.path,
        "parse_days": parse_days,
    }
    return templates.TemplateResponse(request, name, {**base, **context}, status_code=status)


def see_other(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)
