from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..models import ActionItem, Decision, Meeting, Session, User
from ..security import hash_password, hash_token, verify_password
from ..timeutil import is_valid_timezone
from ..web import SESSION_COOKIE, Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()


def _counts(db: DbSession, user_id: int) -> dict[str, int]:
    return {
        "meetings": len(list(db.scalars(select(Meeting.id).where(Meeting.user_id == user_id)))),
        "decisions": len(list(db.scalars(select(Decision.id).where(Decision.user_id == user_id)))),
        "actions": len(list(db.scalars(select(ActionItem.id).where(ActionItem.user_id == user_id)))),
    }


@router.get("/settings")
def settings_page(request: Request, saved: int = 0, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    return render(request, "settings.html", c, saved=saved, counts=_counts(db, c.user.id))


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
            counts=_counts(db, c.user.id),
        )
    if not is_valid_timezone(timezone):
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Unknown timezone. Pick a value like Asia/Kolkata.",
            counts=_counts(db, c.user.id),
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
        return render(request, "settings.html", c, http_status=422, error="Your current password is incorrect.", counts=_counts(db, c.user.id))
    if not 8 <= len(new_password) <= 128:
        return render(request, "settings.html", c, http_status=422, error="Use a new password of at least 8 characters.", counts=_counts(db, c.user.id))
    user = db.get(User, c.user.id)
    user.password_hash = hash_password(new_password)
    db.execute(delete(Session).where(Session.user_id == user.id, Session.id != c.session.id))
    db.commit()
    return see_other("/settings?saved=1")


@router.get("/settings/export")
def export_data(c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    meetings = list(
        db.scalars(select(Meeting).where(Meeting.user_id == c.user.id).order_by(Meeting.occurred_on, Meeting.id)).all()
    )
    payload = {
        "format": "quorum-export-v1",
        "exported_for": c.user.email,
        "meetings": [
            {
                "title": m.title,
                "occurred_on": m.occurred_on.isoformat(),
                "attendees": m.attendees,
                "summary": m.summary,
                "notes": m.notes,
                "source": m.source,
                "decisions": [{"text": d.text, "status": d.status} for d in sorted(m.decisions, key=lambda d: d.id)],
                "actions": [
                    {
                        "title": a.title,
                        "owner": a.owner,
                        "due_date": a.due_date.isoformat() if a.due_date else None,
                        "status": a.status,
                    }
                    for a in sorted(m.actions, key=lambda a: a.id)
                ],
            }
            for m in meetings
        ],
    }
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="quorum-export.json"'},
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
        return render(request, "settings.html", c, http_status=422, error="Type DELETE to confirm.", counts=_counts(db, c.user.id))
    if not verify_password(password, c.user.password_hash):
        return render(request, "settings.html", c, http_status=422, error="Your password is incorrect.", counts=_counts(db, c.user.id))
    db.execute(delete(User).where(User.id == c.user.id))
    db.commit()
    resp = see_other("/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp
