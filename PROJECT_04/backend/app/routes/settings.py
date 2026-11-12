"""Profile, password, data export and account deletion."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..models import Checkin, Goal, Session, User, WeeklyAction
from ..security import hash_password, hash_token, verify_password
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
    weekly_capacity_min: int = Form(300),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    name = " ".join(name.split())
    if not name or len(name) > 80:
        raise HTTPException(422, "Name must be 1-80 characters.")
    if not is_valid_timezone(timezone):
        raise HTTPException(422, "Unknown timezone.")
    if not 30 <= weekly_capacity_min <= 3000:
        raise HTTPException(422, "Weekly capacity must be between 30 and 3000 minutes.")
    user = db.merge(c.user)
    user.name = name
    user.timezone = timezone
    user.weekly_capacity_min = weekly_capacity_min
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
    # Sign out other devices, keep the current session.
    db.execute(delete(Session).where(Session.user_id == user.id, Session.id != c.session.id))
    db.commit()
    limiter.reset(key)
    return see_other("/settings?saved=1")


@router.get("/settings/export")
def export_data(c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    goals = list(db.scalars(select(Goal).where(Goal.user_id == c.user.id).order_by(Goal.id)).all())
    actions = list(db.scalars(select(WeeklyAction).where(WeeklyAction.user_id == c.user.id).order_by(WeeklyAction.id)).all())
    checkins = list(db.scalars(select(Checkin).where(Checkin.user_id == c.user.id).order_by(Checkin.id)).all())
    payload = {
        "format": "summit-export-v1",
        "exported_for": c.user.email,
        "goals": [
            {
                "title": g.title,
                "description": g.description,
                "why": g.why,
                "category": g.category,
                "status": g.status,
                "target_date": g.target_date.isoformat() if g.target_date else None,
                "milestones": [
                    {"title": m.title, "detail": m.detail, "due_date": m.due_date.isoformat() if m.due_date else None, "weight": m.weight, "status": m.status}
                    for m in g.milestones
                ],
            }
            for g in goals
        ],
        "actions": [
            {"goal": a.goal.title, "title": a.title, "estimate_min": a.estimate_min, "week_start": a.week_start.isoformat(), "status": a.status, "source": a.source}
            for a in actions
        ],
        "checkins": [
            {"goal": k.goal.title, "day": k.day.isoformat(), "confidence": k.confidence, "note": k.note}
            for k in checkins
        ],
    }
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="summit-export.json"'},
    )


@router.post("/settings/delete")
def delete_account(request: Request, password: str = Form(""), confirm: str = Form(""), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    if confirm.strip().upper() != "DELETE":
        raise HTTPException(422, 'Type DELETE to confirm.')
    if not verify_password(password, c.user.password_hash):
        raise HTTPException(422, "The password is incorrect.")
    user = db.merge(c.user)
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    resp = see_other("/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp
