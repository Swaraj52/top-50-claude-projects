from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from ..models import (
    CanvasEntry,
    CostLine,
    Kpi,
    KpiReading,
    Milestone,
    RevenueStream,
    Session,
    SwotItem,
    User,
    Venture,
)
from ..security import hash_password, verify_password
from ..timeutil import is_valid_timezone
from ..web import SESSION_COOKIE, Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()


def _context(db: DbSession, user_id: int) -> dict:
    counts = {
        "ventures": db.scalar(select(func.count(Venture.id)).where(Venture.user_id == user_id)) or 0,
        "canvas": db.scalar(
            select(func.count(CanvasEntry.id))
            .join(Venture, Venture.id == CanvasEntry.venture_id)
            .where(Venture.user_id == user_id)
        )
        or 0,
        "swot": db.scalar(
            select(func.count(SwotItem.id))
            .join(Venture, Venture.id == SwotItem.venture_id)
            .where(Venture.user_id == user_id)
        )
        or 0,
        "milestones": db.scalar(
            select(func.count(Milestone.id))
            .join(Venture, Venture.id == Milestone.venture_id)
            .where(Venture.user_id == user_id)
        )
        or 0,
        "kpis": db.scalar(
            select(func.count(Kpi.id)).join(Venture, Venture.id == Kpi.venture_id).where(Venture.user_id == user_id)
        )
        or 0,
        "readings": db.scalar(
            select(func.count(KpiReading.id))
            .join(Kpi, Kpi.id == KpiReading.kpi_id)
            .join(Venture, Venture.id == Kpi.venture_id)
            .where(Venture.user_id == user_id)
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
    ventures = list(
        db.scalars(
            select(Venture).where(Venture.user_id == c.user.id).order_by(Venture.created_at, Venture.id)
        ).all()
    )
    payload = {
        "format": "keystone-export-v1",
        "exported_for": c.user.email,
        "ventures": [
            {
                "name": venture.name,
                "one_liner": venture.one_liner,
                "stage": venture.stage,
                "horizon": venture.horizon,
                "currency": venture.currency,
                "market": venture.market,
                "segment": venture.segment,
                "alternatives": venture.alternatives,
                "differentiation": venture.differentiation,
                "archived": venture.archived,
                "narrative": venture.narrative,
                "narrative_source": venture.narrative_source,
                "narrative_at": venture.narrative_at.isoformat() if venture.narrative_at else None,
                "canvas": [
                    {"block": e.block, "title": e.title, "detail": e.detail, "sort_order": e.sort_order}
                    for e in sorted(venture.canvas, key=lambda e: (e.sort_order, e.id))
                ],
                "swot": [
                    {"quadrant": i.quadrant, "text": i.text, "impact": i.impact, "evidence": i.evidence}
                    for i in venture.swot
                ],
                "streams": [
                    {
                        "name": s.name,
                        "model": s.model,
                        "price": s.price,
                        "unit": s.unit,
                        "volume": s.volume,
                        "confidence": s.confidence,
                        "notes": s.notes,
                    }
                    for s in venture.streams
                ],
                "costs": [
                    {"name": c_line.name, "amount": c_line.amount, "kind": c_line.kind, "notes": c_line.notes}
                    for c_line in venture.costs
                ],
                "milestones": [
                    {
                        "title": m.title,
                        "success_criterion": m.success_criterion,
                        "owner": m.owner,
                        "due_date": m.due_date.isoformat() if m.due_date else None,
                        "horizon": m.horizon,
                        "status": m.status,
                        "sort_order": m.sort_order,
                        "completed_at": m.completed_at.isoformat() if m.completed_at else None,
                    }
                    for m in venture.milestones
                ],
                "kpis": [
                    {
                        "name": k.name,
                        "unit": k.unit,
                        "direction": k.direction,
                        "baseline": k.baseline,
                        "target": k.target,
                        "target_date": k.target_date.isoformat() if k.target_date else None,
                        "cadence": k.cadence,
                        "readings": [
                            {"value": r.value, "recorded_on": r.recorded_on.isoformat(), "note": r.note}
                            for r in sorted(k.readings, key=lambda r: (r.recorded_on, r.id))
                        ],
                    }
                    for k in venture.kpis
                ],
            }
            for venture in ventures
        ],
    }
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="keystone-export.json"'},
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
