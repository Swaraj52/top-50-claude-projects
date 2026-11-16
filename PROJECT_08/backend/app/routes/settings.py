from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..models import Collection, Item, Session, User
from ..security import hash_password, verify_password
from ..services.search import split_tags
from ..timeutil import is_valid_timezone
from ..web import SESSION_COOKIE, Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()


def _context(db: DbSession, user_id: int) -> dict:
    items = list(db.scalars(select(Item).where(Item.user_id == user_id)).all())
    collections = list(db.scalars(select(Collection).where(Collection.user_id == user_id)).all())
    tags: set[str] = set()
    for item in items:
        tags.update(tag.lower() for tag in split_tags(item.tags))
    return {
        "counts": {
            "items": len(items),
            "collections": len(collections),
            "tags": len(tags),
            "words": sum(len((item.body or "").split()) for item in items),
        }
    }


@router.get("/settings")
def settings_page(
    request: Request,
    saved: int = 0,
    error: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    return render(request, "settings.html", c, saved=saved, error=error or None, **_context(db, c.user.id))


@router.post("/settings")
def save_settings(
    request: Request,
    name: str = Form(""),
    timezone: str = Form("UTC"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    name = name.strip()
    if not name or len(name) > 80:
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Name must be between 1 and 80 characters.",
            **_context(db, c.user.id),
        )
    if not is_valid_timezone(timezone):
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Unknown timezone. Pick a value like Asia/Kolkata.",
            **_context(db, c.user.id),
        )
    user = db.get(User, c.user.id)
    user.name = name
    user.timezone = timezone
    db.commit()
    return see_other("/settings?saved=1")


@router.post("/settings/password")
def change_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if not verify_password(current_password, c.user.password_hash):
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Your current password is incorrect.",
            **_context(db, c.user.id),
        )
    if not 8 <= len(new_password) <= 128:
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Use a new password of at least 8 characters.",
            **_context(db, c.user.id),
        )
    user = db.get(User, c.user.id)
    user.password_hash = hash_password(new_password)
    db.execute(delete(Session).where(Session.user_id == user.id, Session.id != c.session.id))
    db.commit()
    return see_other("/settings?saved=1")


@router.get("/settings/export")
def export_data(c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    collections = list(
        db.scalars(select(Collection).where(Collection.user_id == c.user.id).order_by(Collection.name)).all()
    )
    items = list(
        db.scalars(select(Item).where(Item.user_id == c.user.id).order_by(Item.created_at, Item.id)).all()
    )
    payload = {
        "format": "loom-export-v1",
        "exported_for": c.user.email,
        "collections": [
            {"name": collection.name, "description": collection.description} for collection in collections
        ],
        "items": [
            {
                "title": item.title,
                "body": item.body,
                "kind": item.kind,
                "origin": item.origin,
                "source_url": item.source_url,
                "author": item.author,
                "tags": split_tags(item.tags),
                "starred": item.starred,
                "collection": item.collection.name if item.collection else None,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ],
    }
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="loom-export.json"'},
    )


@router.post("/settings/delete")
def delete_account(
    request: Request,
    password: str = Form(""),
    confirm: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if confirm != "DELETE":
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Type DELETE to confirm.",
            **_context(db, c.user.id),
        )
    if not verify_password(password, c.user.password_hash):
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Your password is incorrect.",
            **_context(db, c.user.id),
        )
    db.execute(delete(User).where(User.id == c.user.id))
    db.commit()
    resp = see_other("/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp
