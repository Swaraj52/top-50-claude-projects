from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from ..models import (
    Person,
    Run,
    RunItem,
    Session,
    Sop,
    SopStep,
    User,
)
from ..security import hash_password, verify_password
from ..timeutil import is_valid_timezone
from ..web import SESSION_COOKIE, Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()


def _context(db: DbSession, user_id: int) -> dict:
    counts = {
        "people": db.scalar(
            select(func.count(Person.id)).where(Person.user_id == user_id)
        )
        or 0,
        "sops": db.scalar(select(func.count(Sop.id)).where(Sop.user_id == user_id)) or 0,
        "steps": db.scalar(
            select(func.count(SopStep.id))
            .join(Sop, Sop.id == SopStep.sop_id)
            .where(Sop.user_id == user_id)
        )
        or 0,
        "runs": db.scalar(
            select(func.count(Run.id))
            .join(Sop, Sop.id == Run.sop_id)
            .where(Sop.user_id == user_id)
        )
        or 0,
        "items": db.scalar(
            select(func.count(RunItem.id))
            .join(Run, Run.id == RunItem.run_id)
            .join(Sop, Sop.id == Run.sop_id)
            .where(Sop.user_id == user_id)
        )
        or 0,
    }
    return {"counts": counts}


@router.get("/settings")
def settings_page(
    request: Request,
    saved: int = 0,
    error: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    return render(
        request, "settings.html", c, saved=saved, error=error or None, **_context(db, c.user.id)
    )


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
    people = list(
        db.scalars(
            select(Person).where(Person.user_id == c.user.id).order_by(Person.created_at, Person.id)
        ).all()
    )
    sops = list(
        db.scalars(
            select(Sop).where(Sop.user_id == c.user.id).order_by(Sop.created_at, Sop.id)
        ).all()
    )
    runs = list(
        db.scalars(
            select(Run)
            .join(Sop, Sop.id == Run.sop_id)
            .where(Sop.user_id == c.user.id)
            .order_by(Run.started_on, Run.id)
        ).all()
    )
    people_by_id = {person.id: person for person in people}
    sops_by_id = {sop.id: sop for sop in sops}

    payload = {
        "format": "foundry-export-v1",
        "exported_for": c.user.email,
        "people": [
            {
                "name": person.name,
                "role": person.role,
                "email": person.email,
                "notes": person.notes,
                "active": person.active,
            }
            for person in people
        ],
        "sops": [
            {
                "code": sop.code,
                "title": sop.title,
                "area": sop.area,
                "status": sop.status,
                "purpose": sop.purpose,
                "scope": sop.scope,
                "owner": people_by_id[sop.owner_id].name if sop.owner_id in people_by_id else None,
                "cadence": sop.cadence,
                "review_months": sop.review_months,
                "last_reviewed_on": sop.last_reviewed_on.isoformat()
                if sop.last_reviewed_on
                else None,
                "version": sop.version,
                "steps": [
                    {
                        "position": step.position,
                        "title": step.title,
                        "detail": step.detail,
                        "role": step.role,
                        "minutes": step.minutes,
                    }
                    for step in sorted(sop.steps, key=lambda step: (step.position, step.id))
                ],
            }
            for sop in sops
        ],
        "runs": [
            {
                "sop_code": sops_by_id[run.sop_id].code if run.sop_id in sops_by_id else None,
                "owner": people_by_id[run.owner_id].name if run.owner_id in people_by_id else None,
                "started_on": run.started_on.isoformat(),
                "due_on": run.due_on.isoformat() if run.due_on else None,
                "status": run.status,
                "notes": run.notes,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "items": [
                    {
                        "position": item.position,
                        "title": item.title,
                        "detail": item.detail,
                        "role": item.role,
                        "done": item.done,
                        "done_at": item.done_at.isoformat() if item.done_at else None,
                        "note": item.note,
                    }
                    for item in sorted(run.items, key=lambda item: (item.position, item.id))
                ],
            }
            for run in runs
        ],
    }
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="foundry-export.json"'},
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
