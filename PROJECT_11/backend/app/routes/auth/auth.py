from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.web import get_db, utcnow
from app.models import User, Session as SessionModel
from app.security import hash_password, verify_password, new_session_token
from app.web import render, see_other

router = APIRouter()


def _auth_page(request: Request, template: str, error: str | None = None,
               status: int = 200, **values) -> Response:
    """Render an auth page with CSRF token."""
    token = secrets.token_urlsafe(32)
    resp = render(request, template, None, http_status=status, form_csrf=token, error=error, **values)
    return resp


@router.get("/login")
async def login_get(request: Request, db=Depends(get_db)):
    """Login page."""
    if request.cookies.get("fd_session"):
        return see_other("/")
    return render(request, "login.html", {"form_csrf": ""})


@router.post("/login")
async def login_post(request: Request, db=Depends(get_db), form: dict = Depends(lambda: dict())):
    """Process login form."""
    form_data = await request.form()
    email = form_data.get("email", "")
    password = form_data.get("password", "")
    
    # Find user by email
    db_user = db.scalar(select(User).where(User.email == email))
    if not db_user or not verify_password(password, db_user.password_hash):
        return _auth_page(request, "login.html", "Invalid email or password", status=400)
    
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
    if request.cookies.get("fd_session"):
        return see_other("/")
    return render(request, "register.html", {"form_csrf": ""})


@router.post("/register")
async def register_post(request: Request, db=Depends(get_db), form: dict = Depends(lambda: dict())):
    """Process registration form."""
    form_data = await request.form()
    name = form_data.get("name", "")
    email = form_data.get("email", "")
    password = form_data.get("password", "")
    timezone = form_data.get("timezone", "UTC")
    
    # Validate
    if not email or not password:
        return _auth_page(request, "register.html", "Email and password required")
    
    # Check if user already exists
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        return _auth_page(request, "register.html", "Email already registered")
    
    # Create user
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


@router.post("/logout")
async def logout(request: Request, db=Depends(get_db)):
    """Process logout."""
    # Delete session from database
    # We don't have user id easily here, just clear cookies
    response = see_other("/login")
    response.delete_cookie("fd_session")
    response.delete_cookie("fd_csrf")
    
    return response