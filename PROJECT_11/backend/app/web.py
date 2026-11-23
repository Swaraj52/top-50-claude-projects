"""Request helpers: sessions, CSRF, templates and redirects for the server-rendered UI."""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import TypedDict
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from . import __version__
from .db import utcnow

from .models import User, Session as SessionModel

SESSION_COOKIE = "fd_session"
PRE_CSRF_COOKIE = "fd_csrf"

templates = None  # Will be initialized in main.py


def init_templates(directory: str = "templates") -> None:
    """Initialize the Jinja2 templates directory."""
    global templates
    from pathlib import Path
    templates = Jinja2Templates(directory=str(Path(directory)))


# Context type for dependency injection
class Ctx(TypedDict):
    user_id: int
    """Current user's ID"""
    today: str
    """Current date in user's timezone"""
    now: datetime
    """Current datetime"""
    csrf_token: str
    """CSRF token from session"""


def render(request: Request, template: str, context: dict | None = None,
           http_status: int = 200, **values) -> Response:
    """Render a Jinja2 template with the given context."""
    if templates is None:
        from . import __version__
        from pathlib import Path
        templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    if context is None:
        context = {}

    context.update({
        "request": request,
        "version": __version__,
        **values,
    })

    return templates.TemplateResponse(template, context, request=request)


def see_other(location: str, status_code: int = 303) -> RedirectResponse:
    """Return a 303 See Other redirect response."""
    return RedirectResponse(url=location, status_code=status_code)


def csrf_token(request: Request) -> str:
    """Extract CSRF token from request form or cookie."""
    # Try form data first, then cookie
    form_token = request.form.get("csrf_token") if hasattr(request, 'form') else None
    if form_token:
        return form_token

    # Check cookie
    cookie_token = request.cookies.get(PRE_CSRF_COOKIE)
    if cookie_token:
        return cookie_token

    return ""


def pre_csrf(request: Request) -> dict:
    """CSRF protection dependency. Validates form CSRF token against cookie."""
    token = csrf_token(request)
    cookie_token = request.cookies.get(PRE_CSRF_COOKIE)

    if not cookie_token:
        return {"csrf_error": "CSRF cookie missing"}

    if not token or hmac.compare_digest(token, cookie_token) is False:
        return {"csrf_error": "Invalid CSRF token"}

    return {}


def LoginRequired():
    """Dependency to check if user is logged in."""
    # This will be implemented per-route
    return {}


def is_htmx(request: Request) -> bool:
    """Check if the request comes from HTMX."""
    return request.headers.get("HX-Request") == "true"


def optional_ctx(request: Request, db) -> Ctx:
    """Provide optional context from session."""
    # Read the session from cookies
    session_token = request.cookies.get(SESSION_COOKIE)
    csrf_token = request.cookies.get(PRE_CSRF_COOKIE)

    return {
        "user_id": 0,  # Will be set by auth middleware
        "today": datetime.utcnow().strftime("%Y-%m-%d"),
        "now": datetime.utcnow(),
        "csrf_token": csrf_token or "",
    }


def ctx(request: Request, db) -> Ctx:
    """Provide context from the current session."""
    # This is a simplified version - in production,
    # would verify the session token against the database
    return optional_ctx(request, db)


def get_db(request: Request) -> DbSession:
    """Get database session from app state."""
    sessionmaker = getattr(request.app, "sessionmaker", None)
    if sessionmaker is None:
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        engine = create_engine("sqlite:///data/foundry.db")
        sessionmaker = sessionmaker(bind=engine)
        request.app.sessionmaker = sessionmaker
    return sessionmaker()