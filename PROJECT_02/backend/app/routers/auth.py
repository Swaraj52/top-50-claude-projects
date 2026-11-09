from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..config import Settings
from ..db import utcnow
from ..deps import SESSION_COOKIE, current_user, get_db, get_settings
from ..models import Session, User
from ..schemas import LoginIn, RegisterIn, UserOut
from ..security import hash_password, hash_token, new_session_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY_HASH = hash_password("timing-equaliser")


def _start_session(response: Response, db: DbSession, user: User, settings: Settings) -> None:
    token, token_hash = new_session_token()
    db.add(Session(user_id=user.id, token_hash=token_hash, expires_at=utcnow() + timedelta(days=settings.session_days)))
    db.execute(delete(Session).where(Session.user_id == user.id, Session.expires_at < utcnow()))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE, token, max_age=settings.session_days * 86400, httponly=True,
        samesite="lax", secure=settings.cookie_secure, path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, response: Response, db: DbSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    _start_session(response, db, user, settings)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: DbSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    email = body.email.lower()
    limiter = request.app.state.login_limiter
    key = f"{email}|{request.client.host if request.client else '-'}"
    if limiter.blocked(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(limiter.retry_after(key))},
        )
    user = db.scalar(select(User).where(User.email == email))
    if not verify_password(body.password, user.password_hash if user else _DUMMY_HASH) or not user:
        limiter.hit(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    limiter.reset(key)
    _start_session(response, db, user, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: DbSession = Depends(get_db)) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
        db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
