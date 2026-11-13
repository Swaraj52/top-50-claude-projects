"""Profile, password, data export and account deletion."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..models import Habit, Reflection, Session, User
from ..security import hash_password, verify_password
from ..timeutil import is_valid_timezone
from ..web import SESSION_COOKIE, Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()


@router.get("/settings")
def settings_page(request: Request, saved: int = 0, c: Ctx = Depends(ctx)):
    return render(request, "settings.html", c, saved=bool(saved), error=None)


@router.post("/settings")
def save_settings(
    name: str = Form(""),
    timezone: str = Form("UTC"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    name = " ".join(name.split())
    if not name or len(name) > 80:
        raise HTTPException(422, "Name must be 1-80 characters.")
    if not is_valid_timezone(timezone):
        raise HTTPException(422, "Unknown timezone.")
    user = db.merge(c.user)
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
    limiter = request.app.state.login_limiter
    key = f"pw|{c.user.id}"
    if limiter.blocked(key):
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
    if not verify_password(current_password, c.user.password_hash):
        limiter.hit(key)
        raise HTTPException(422, "The current password is incorrect.")
    if not 8 <= len(new_password) <= 128:
        raise HTTPException(422, "Use a new password of at least 8 characters.")
    user = db.merge(c.user)
    user.password_hash = hash_password(new_password)
    db.execute(delete(Session).where(Session.user_id == user.id, Session.id != c.session.id))
    db.commit()
    limiter.reset(key)
    return see_other("/settings?saved=1")


@router.get("/settings/export")
def export_data(c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    habits = list(
        db.scalars(select(Habit).where(Habit.user_id == c.user.id).order_by(Habit.created_at, Habit.id)).all()
    )
    reflections = list(
        db.scalars(select(Reflection).where(Reflection.user_id == c.user.id).order_by(Reflection.week_start)).all()
    )
    payload = {
        "format": "cadence-export-v1",
        "exported_for": c.user.email,
        "habits": [
            {
                "title": h.title,
                "intention": h.intention,
                "cue": h.cue,
                "days": h.days,
                "status": h.status,
                "created_at": h.created_at.date().isoformat(),
                "logs": [
                    {"day": log.day.isoformat(), "status": log.status, "note": log.note}
                    for log in sorted(h.logs, key=lambda x: x.day)
                ],
            }
            for h in habits
        ],
        "reflections": [
            {
                "week_start": r.week_start.isoformat(),
                "mood": r.mood,
                "worked": r.worked,
                "friction": r.friction,
                "change": r.change,
            }
            for r in reflections
        ],
    }
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="cadence-export.json"'},
    )


@router.post("/settings/delete")
def delete_account(
    request: Request,
    password: str = Form(""),
    confirm: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if confirm.strip().upper() != "DELETE":
        raise HTTPException(422, "Type DELETE to confirm.")
    if not verify_password(password, c.user.password_hash):
        raise HTTPException(422, "The password is incorrect.")
    user = db.merge(c.user)
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    resp = see_other("/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp
