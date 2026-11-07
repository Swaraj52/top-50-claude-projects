from __future__ import annotations

from collections.abc import Iterator
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .config import Settings
from .db import utcnow
from .models import Session, User
from .security import SecretBox, hash_token
from .timeutil import zone

SESSION_COOKIE = "pd_session"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[DbSession]:
    db = request.app.state.sessionmaker()
    try:
        yield db
    finally:
        db.close()


def get_secret_box(request: Request) -> SecretBox:
    return request.app.state.secret_box


def current_user(request: Request, db: DbSession = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = db.scalar(select(Session).where(Session.token_hash == hash_token(token)))
        if session and session.expires_at > utcnow():
            return session.user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")


def user_zone(user: User = Depends(current_user)) -> ZoneInfo:
    return zone(user.timezone)


def get_owned(db: DbSession, model, obj_id: int, user: User):
    """Fetch a row owned by the user, or 404 (never 403, so ids aren't probeable)."""
    obj = db.get(model, obj_id)
    if obj is None or obj.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return obj
