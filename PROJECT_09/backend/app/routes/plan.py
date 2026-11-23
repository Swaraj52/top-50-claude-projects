from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..forms import choice, clean, parse_date, integer
from ..models import (
    MILESTONE_HORIZONS,
    MILESTONE_STATUSES,
    Milestone,
)
from ..services import milestones as milestone_service
from ..web import Ctx, csrf, ctx, get_db, render, see_other
from ._shared import owned_milestone, owned_venture, touch

router = APIRouter()


def _page(request: Request, c: Ctx, venture, edit_id: int = 0, error: str | None = None, status: int = 200):
    milestones = sorted(venture.milestones, key=milestone_service.sort_key)
    edit_item = next((m for m in milestones if m.id == edit_id), None) if edit_id else None
    return render(
        request,
        "plan.html",
        c,
        http_status=status,
        venture=venture,
        milestones=milestones,
        summary=milestone_service.summary(milestones, c.today),
        board=milestone_service.board(milestones, c.today),
        edit_item=edit_item,
        error=error,
    )


def _values(form, milestone: Milestone | None = None) -> dict:
    return {
        "title": clean(form.get("title"), 160),
        "success_criterion": clean(form.get("success_criterion"), 300),
        "owner": clean(form.get("owner"), 80),
        "due_date": parse_date(form.get("due_date")),
        "horizon": choice(form.get("horizon"), MILESTONE_HORIZONS, milestone.horizon if milestone else "now"),
        "status": choice(form.get("status"), MILESTONE_STATUSES, milestone.status if milestone else "planned"),
    }


@router.get("/ventures/{venture_id}/plan")
def plan_page(
    request: Request,
    venture_id: int,
    edit: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    return _page(request, c, venture, edit_id=edit)


@router.post("/ventures/{venture_id}/plan")
async def add_milestone(
    request: Request,
    venture_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    values = _values(await request.form())
    if len(values["title"]) < 3:
        return _page(request, c, venture, error="A milestone needs a title of at least three characters.", status=422)
    order = max([m.sort_order for m in venture.milestones] + [0]) + 1
    db.add(Milestone(venture_id=venture.id, sort_order=order, **values))
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/plan#{values['horizon']}")


@router.post("/milestones/{milestone_id}/edit")
async def edit_milestone(
    request: Request,
    milestone_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    milestone, venture = owned_milestone(db, milestone_id, c.user.id)
    values = _values(await request.form(), milestone)
    if len(values["title"]) < 3:
        return _page(request, c, venture, edit_id=milestone.id, error="A milestone needs a title of at least three characters.", status=422)
    for key, value in values.items():
        setattr(milestone, key, value)
    if values["status"] == "done" and milestone.completed_at is None:
        milestone.completed_at = utcnow()
    if values["status"] != "done":
        milestone.completed_at = None
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/plan#{values['horizon']}")


@router.post("/milestones/{milestone_id}/status")
def set_status(
    request: Request,
    milestone_id: int,
    status: str = Form("planned"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    milestone, venture = owned_milestone(db, milestone_id, c.user.id)
    milestone.status = choice(status, MILESTONE_STATUSES, milestone.status)
    milestone.completed_at = utcnow() if milestone.status == "done" else None
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/plan#{milestone.horizon}")


@router.post("/milestones/{milestone_id}/delete")
def delete_milestone(
    request: Request,
    milestone_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    milestone, venture = owned_milestone(db, milestone_id, c.user.id)
    horizon = milestone.horizon
    db.delete(milestone)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/plan#{horizon}")
