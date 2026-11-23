from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..forms import clean, integer
from ..models import MAX_STEPS, SopStep
from ..web import Ctx, csrf, ctx, get_db, see_other
from ._shared import owned_sop, owned_step, touch

router = APIRouter()


def _renumber(sop) -> None:
    """Rewrite positions 1..n without tripping the (sop_id, position) unique index."""
    steps = sorted(sop.steps, key=lambda step: (step.position, step.id))
    for step in steps:
        step.position = -step.id
    for index, step in enumerate(steps, start=1):
        step.position = index


def _read(form) -> tuple[str, str, str, int, list[str]]:
    title = clean(form.get("title"), 160)
    detail = clean(form.get("detail"), 600)
    role = clean(form.get("role"), 80)
    minutes = integer(form.get("minutes"), 0, 0, 1440)
    errors = []
    if len(title) < 3:
        errors.append("Give the step a title of at least 3 characters.")
    return title, detail, role, minutes, errors


@router.post("/sops/{sop_id}/steps")
async def add_step(
    request: Request,
    sop_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    sop = owned_sop(db, c.user.id, sop_id)
    form = await request.form()
    title, detail, role, minutes, errors = _read(form)
    if len(sop.steps) >= MAX_STEPS:
        raise HTTPException(422, f"A process can have at most {MAX_STEPS} steps.")
    if errors:
        raise HTTPException(422, errors[0])
    position = max((step.position for step in sop.steps), default=0) + 1
    sop.steps.append(
        SopStep(position=position, title=title, detail=detail, role=role, minutes=minutes)
    )
    sop.version += 1
    touch(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}")


@router.post("/steps/{step_id}/edit")
async def edit_step(
    request: Request,
    step_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    step, sop = owned_step(db, c.user.id, step_id)
    form = await request.form()
    title, detail, role, minutes, errors = _read(form)
    if errors:
        raise HTTPException(422, errors[0])
    step.title = title
    step.detail = detail
    step.role = role
    step.minutes = minutes
    sop.version += 1
    touch(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}")


@router.post("/steps/{step_id}/move")
async def move_step(
    request: Request,
    step_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    step, sop = owned_step(db, c.user.id, step_id)
    form = await request.form()
    direction = str(form.get("direction", ""))
    ordered = sorted(sop.steps, key=lambda row: (row.position, row.id))
    index = next((i for i, row in enumerate(ordered) if row.id == step.id), None)
    if index is None:
        raise HTTPException(404, "That step doesn't exist.")
    target = index - 1 if direction == "up" else index + 1 if direction == "down" else None
    if target is None or not 0 <= target < len(ordered):
        return see_other(f"/sops/{sop.id}")
    other = ordered[target]
    step_position, other_position = step.position, other.position
    step.position = -step.id
    db.flush()
    other.position = step_position
    db.flush()
    step.position = other_position
    sop.version += 1
    touch(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}")


@router.post("/steps/{step_id}/delete")
def delete_step(
    step_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    step, sop = owned_step(db, c.user.id, step_id)
    db.delete(step)
    db.flush()
    _renumber(sop)
    sop.version += 1
    touch(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}")
