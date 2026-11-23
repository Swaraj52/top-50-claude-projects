from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..forms import clean, integer, parse_date
from ..models import Person, Run, Sop
from ..services import runs as run_service
from ..web import Ctx, csrf, ctx, get_db, is_htmx, render, see_other
from ._shared import owned_item, owned_run, owned_sop, person_options

router = APIRouter()


def all_runs(db: DbSession, user_id: int) -> list[Run]:
    return db.scalars(
        select(Run)
        .join(Sop, Sop.id == Run.sop_id)
        .options(selectinload(Run.items), selectinload(Run.sop), selectinload(Run.owner))
        .where(Sop.user_id == user_id)
        .order_by(Run.started_on.desc(), Run.id.desc())
    ).all()


@router.get("/runs")
def runs_page(
    request: Request,
    status: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    status = status if status in ("open", "done", "abandoned") else ""
    runs = all_runs(db, c.user.id)
    if status:
        runs = [run for run in runs if run.status == status]
    return render(
        request,
        "runs.html",
        c,
        runs=runs,
        summary=run_service.summary(all_runs(db, c.user.id), c.today),
        status=status,
    )


@router.post("/sops/{sop_id}/runs")
async def start_run(
    request: Request,
    sop_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    sop = owned_sop(db, c.user.id, sop_id)
    if sop.status != "active":
        raise HTTPException(422, "Only an active process can be run.")
    if not sop.steps:
        raise HTTPException(422, "Add steps before starting a checklist.")
    form = await request.form()
    owner_raw = integer(form.get("owner_id"), 0)
    owner_id = None
    if owner_raw:
        owner = db.scalar(select(Person).where(Person.id == owner_raw, Person.user_id == c.user.id))
        if owner is None:
            raise HTTPException(422, "Choose an owner from your team list.")
        owner_id = owner.id
    due_on = parse_date(form.get("due_on"))
    if form.get("due_on") and due_on is None:
        raise HTTPException(422, "Enter the due date as YYYY-MM-DD.")
    run = run_service.start(sop, c.today, owner_id=owner_id, due_on=due_on)
    db.add(run)
    db.commit()
    return see_other(f"/runs/{run.id}")


@router.get("/runs/{run_id}")
def run_page(
    request: Request,
    run_id: int,
    completed: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    run, sop = owned_run(db, c.user.id, run_id)
    return render(
        request,
        "run_detail.html",
        c,
        run=run,
        sop=sop,
        items=run_service.started_items(run),
        progress=run_service.progress(run),
        due=run_service.due_state(run, c.today),
        people=person_options(db, c.user.id),
        completed_flag=completed == "1",
    )


@router.post("/runs/{run_id}/items/{item_id}/toggle")
def toggle_item(
    request: Request,
    run_id: int,
    item_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    item, run, sop = owned_item(db, c.user.id, item_id)
    if run.id != run_id:
        raise HTTPException(404, "That checklist item doesn't exist.")
    if run.status != "open":
        raise HTTPException(422, "This checklist is closed.")
    run_service.toggle(item)
    db.commit()
    if is_htmx(request):
        return render(
            request,
            "_checklist.html",
            c,
            run=run,
            sop=sop,
            items=run_service.started_items(run),
            progress=run_service.progress(run),
            due=run_service.due_state(run, c.today),
        )
    return see_other(f"/runs/{run.id}#checklist")


@router.post("/runs/{run_id}/items/{item_id}/note")
async def note_item(
    request: Request,
    run_id: int,
    item_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    item, run, _sop = owned_item(db, c.user.id, item_id)
    if run.id != run_id:
        raise HTTPException(404, "That checklist item doesn't exist.")
    form = await request.form()
    item.note = clean(form.get("note"), 300)
    db.commit()
    return see_other(f"/runs/{run.id}#item-{item.id}")


@router.post("/runs/{run_id}/edit")
async def edit_run(
    request: Request,
    run_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    run, _sop = owned_run(db, c.user.id, run_id)
    if run.status != "open":
        raise HTTPException(422, "A closed checklist cannot be edited.")
    form = await request.form()
    owner_raw = integer(form.get("owner_id"), 0)
    if owner_raw:
        owner = db.scalar(select(Person).where(Person.id == owner_raw, Person.user_id == c.user.id))
        if owner is None:
            raise HTTPException(422, "Choose an owner from your team list.")
        run.owner_id = owner.id
    else:
        run.owner_id = None
    if form.get("due_on"):
        due_on = parse_date(form.get("due_on"))
        if due_on is None:
            raise HTTPException(422, "Enter the due date as YYYY-MM-DD.")
        run.due_on = due_on
    else:
        run.due_on = None
    run.notes = clean(form.get("notes"), 1500)
    db.commit()
    return see_other(f"/runs/{run.id}")


@router.post("/runs/{run_id}/complete")
def complete_run(
    run_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    run, _sop = owned_run(db, c.user.id, run_id)
    if run.status != "open":
        raise HTTPException(422, "This checklist is already closed.")
    try:
        run_service.complete(run)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return see_other(f"/runs/{run.id}?completed=1")


@router.post("/runs/{run_id}/abandon")
async def abandon_run(
    request: Request,
    run_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    run, _sop = owned_run(db, c.user.id, run_id)
    if run.status != "open":
        raise HTTPException(422, "This checklist is already closed.")
    form = await request.form()
    if str(form.get("confirm", "")) != "abandon":
        raise HTTPException(422, "Confirm that you want to abandon this checklist.")
    run_service.abandon(run)
    db.commit()
    return see_other(f"/runs/{run.id}")
