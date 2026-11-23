from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.web import utcnow, get_db
from app.models import User, Session as SessionModel
from app.security import hash_password, verify_password, new_session_token
from app.web import Ctx, csrf, ctx, get_db as _get_db, render, see_other, pre_csrf

router = APIRouter()


@router.get("/login")
async def login_get(request: Request, db=Depends(get_db), user=Depends(ctx)):
    """Login page."""
    if user.is_authenticated:
        return see_other("/")
    return render(request, "login.html", {"form_csrf": ctx(request, db).get("csrf_token", "")})


@router.post("/login")
async def login_post(request: Request, db=Depends(get_db), user=Depends(ctx), c=Depends(csrf)):
    """Process login form."""
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")

    db_user = db.scalar(select(User).where(User.email == email))
    if not db_user or not verify_password(password, db_user.password_hash):
        return _auth_page(request, "login.html", "Invalid email or password", status=400,
                          form_csrf=ctx(request, db).get("csrf_token", ""))

    # Create session
    token = new_session_token()
    session = SessionModel(
        user_id=db_user.id,
        token_hash=hash_token(token),
        csrf_token=secrets.token_urlsafe(32),
        expires_at=utcnow() + timedelta(days=30),
    )
    db.add(session)
    db.commit()

    # Set session cookie and delete CSRF cookie
    response = see_other("/")
    response.set_cookie("fd_session", token, httponly=True, secure=False, samesite="lax")
    response.delete_cookie("fd_csrf")

    return response


@router.get("/register")
async def register_get(request: Request, db=Depends(get_db)):
    """Register page."""
    if user.is_authenticated:
        return see_other("/")
    return render(request, "register.html", {"form_csrf": ctx(request).get("csrf_token", "")})


@router.post("/register")
async def register_post(request: Request, db=Depends(get_db), user=Depends(ctx), c=Depends(csrf)):
    """Process registration form."""
    form = await request.form()
    name = form.get("name", "")
    email = form.get("email", "")
    password = form.get("password", "")
    timezone = form.get("timezone", "UTC")

    if not email or not password:
        return _auth_page(request, "register.html", "Email and password required",
                          form_csrf=ctx(request, db).get("csrf_token", ""))

    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        return _auth_page(request, "register.html", "Email already registered",
                          form_csrf=ctx(request, db).get("csrf_token", ""))

    password_hash = hash_password(password)
    db_user = User(
        email=email,
        name=name,
        password_hash=password_hash,
        timezone=timezone,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    token = new_session_token()
    session = SessionModel(
        user_id=db_user.id,
        token_hash=hash_token(token),
        csrf_token=secrets.token_urlsafe(32),
        expires_at=utcnow() + timedelta(days=30),
    )
    db.add(session)
    db.commit()

    response = see_other("/")
    response.set_cookie("fd_session", token, httponly=True, secure=False, samesite="lax")
    response.delete_cookie("fd_csrf")

    return response


@router.post("/logout")
async def logout(request: Request, db=Depends(get_db)):
    """Process logout."""
    response = see_other("/login")
    response.delete_cookie("fd_session")
    response.delete_cookie("fd_csrf")
    return response


def _auth_page(request: Request, template: str, error: str | None = None,
               status: int = 200, **values) -> Response:
    """Render an auth page with CSRF token."""
    token = secrets.token_urlsafe(32)
    resp = render(request, template, None, http_status=status, form_csrf=token, error=error, **values)
    return resp