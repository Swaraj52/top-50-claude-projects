from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..models import Session, User
from ..security import hash_password, hash_token, new_session_token, verify_password
from ..timeutil import is_valid_timezone
from ..web import PRE_CSRF_COOKIE, SESSION_COOKIE, Ctx, csrf, get_db, new_pre_csrf, optional_ctx, pre_csrf, render, see_other

router = APIRouter()
_DUMMY = hash_password("timing-equaliser")
_EMAIL = TypeAdapter(EmailStr)


def _auth_page(request: Request, template: str, error: str | None = None, status: int = 200, **values) -> Response:
    token = new_pre_csrf()
    resp = render(request, template, None, status=status, form_csrf=token, error=error, values=values)
    resp.set_cookie(PRE_CSRF_COOKIE, token, httponly=True, samesite="strict", secure=request.app.state.settings.cookie_secure)
    return resp


def _sign_in(request: Request, db: DbSession, user: User) -> Response:
    settings = request.app.state.settings
    token, token_hash = new_session_token()
    db.add(Session(user_id=user.id, token_hash=token_hash, csrf_token=secrets.token_urlsafe(32), expires_at=utcnow() + timedelta(days=settings.session_days)))
    db.execute(delete(Session).where(Session.user_id == user.id, Session.expires_at < utcnow()))
    db.commit()
    resp = see_other("/today")
    resp.set_cookie(SESSION_COOKIE, token, max_age=settings.session_days * 86400, httponly=True, samesite="lax", secure=settings.cookie_secure)
    resp.delete_cookie(PRE_CSRF_COOKIE)
    return resp


@router.get("/")
def home(c: Ctx | None = Depends(optional_ctx)):
    return see_other("/today" if c else "/login")


@router.get("/login")
def login_page(request: Request, c: Ctx | None = Depends(optional_ctx)):
    return see_other("/today") if c else _auth_page(request, "login.html")


@router.post("/login", dependencies=[Depends(pre_csrf)])
def login(request: Request, email: str = Form(""), password: str = Form(""), db: DbSession = Depends(get_db)):
    email = email.strip().lower()
    limiter = request.app.state.login_limiter
    key = f"{email}|{request.client.host if request.client else '-'}"
    if limiter.blocked(key):
        return _auth_page(request, "login.html", "Too many failed attempts. Try again in a few minutes.", 429, email=email)
    user = db.scalar(select(User).where(User.email == email))
    if not verify_password(password, user.password_hash if user else _DUMMY) or not user:
        limiter.hit(key)
        return _auth_page(request, "login.html", "Incorrect email or password.", 401, email=email)
    limiter.reset(key)
    return _sign_in(request, db, user)


@router.get("/register")
def register_page(request: Request, c: Ctx | None = Depends(optional_ctx)):
    return see_other("/today") if c else _auth_page(request, "register.html")


@router.post("/register", dependencies=[Depends(pre_csrf)])
def register(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    timezone: str = Form("UTC"),
    db: DbSession = Depends(get_db),
):
    name, email = name.strip(), email.strip().lower()
    values = {"name": name, "email": email}
    try:
        _EMAIL.validate_python(email)
    except ValidationError:
        return _auth_page(request, "register.html", "Enter a valid email address.", 422, **values)
    if not name or len(name) > 80:
        return _auth_page(request, "register.html", "Tell us your name (up to 80 characters).", 422, **values)
    if not 8 <= len(password) <= 128:
        return _auth_page(request, "register.html", "Use a password of at least 8 characters.", 422, **values)
    if db.scalar(select(User.id).where(User.email == email)):
        return _auth_page(request, "register.html", "An account with this email already exists.", 409, **values)
    user = User(name=name, email=email, password_hash=hash_password(password), timezone=timezone if is_valid_timezone(timezone) else "UTC")
    db.add(user)
    db.commit()
    return _sign_in(request, db, user)


@router.post("/logout")
def logout(request: Request, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    db.execute(delete(Session).where(Session.token_hash == hash_token(request.cookies.get(SESSION_COOKIE, ""))))
    db.commit()
    resp = see_other("/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp
