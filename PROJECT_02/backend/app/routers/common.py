"""Helpers shared by the routers."""

from __future__ import annotations

import anthropic
from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..config import Settings
from ..models import Item, Tag, User


def ai_client(request: Request) -> anthropic.Anthropic | None:
    """The Anthropic client, or None without a key. Overridden in tests."""
    settings: Settings = request.app.state.settings
    if not settings.ai_enabled:
        return None
    client = getattr(request.app.state, "anthropic_client", None)
    if client is None:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=90.0, max_retries=2)
        request.app.state.anthropic_client = client
    return client


def rate_limit(request: Request, limiter_name: str, key: str, message: str) -> None:
    limiter = getattr(request.app.state, limiter_name)
    if limiter.blocked(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, message, headers={"Retry-After": str(limiter.retry_after(key))}
        )
    limiter.hit(key)


def set_tags(db: DbSession, user: User, item: Item, names: list[str]) -> None:
    existing = {t.name: t for t in db.scalars(select(Tag).where(Tag.user_id == user.id, Tag.name.in_(names)))}
    tags = []
    for name in names:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(user_id=user.id, name=name)
            db.add(tag)
        tags.append(tag)
    item.tags = tags


def drop_orphan_tags(db: DbSession, user: User) -> None:
    for tag in db.scalars(select(Tag).where(Tag.user_id == user.id)):
        if not tag.items:
            db.delete(tag)
