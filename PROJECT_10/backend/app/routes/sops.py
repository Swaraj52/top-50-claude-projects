from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..db import utcnow
from ..forms import choice, clean, integer
from ..models import (
    AREAS,
    CADENCES,
    REVIEW_MONTHS,
    Person,
    Run,
    Sop,
    SopStep,
)
from ..services import draft as draft_service
from ..services import sops as sop_service
from ..web import Ctx, csrf, ctx, get_db, render, see_other
from ._shared import owned_person, owned_sop, person_options, touch

router = APIRouter()


def library(db: DbSession, user_id: int) -> list[Sop]:
    return db.scalars(
        select(Sop)
        .options(selectinload(Sop.owner), selectinload(Sop.steps))
        .where(Sop.user_id == user_id)
        .order_by(Sop.code)
    ).all()


def blank_values(area: str = "operations") -> dict:
    return {
        "code": "",
        "title": "",
        "area": area,
        "purpose": "",
        "scope": "",
        "owner_id": "",
        "cadence": "monthly",
        "review_months": 6,
    }


def values_from(sop: Sop) -> dict:
    return {
        "code": sop.code,
        "title": sop.title,
        "area": sop.area,
        "purpose": sop.purpose,
        "scope": sop.scope,
        "owner_id": sop.owner_id or "",
        "cadence": sop.cadence,
        "review_months": sop.review_months,
    }


def read_form(form, db: DbSession, user_id: int) -> tuple[dict, list[str]]:
    owner_raw = integer(form.get("owner_id"), 0)
    owner_id = None
    errors = []
    if owner_raw:
        person = db.scalar(select(Person).where(Person.id == owner_raw, Person.user_id == user_id))
        if person is None:
            errors.append("Choose an owner from your team list.")
        else:
            owner_id = person.id
    months = integer(form.get("review_months"), 6)
    values = {
        "code": clean(form.get("code"), 20).upper(),
        "title": clean(form.get("title"), 160),
        "area": choice(form.get("area"), AREAS, "operations"),
        "purpose": clean(form.get("purpose"), 1500),
        "scope": clean(form.get("scope"), 800),
        "owner_id": owner_id or "",
        "cadence": choice(form.get("cadence"), CADENCES, "monthly"),
        "review_months": months if months in REVIEW_MONTHS else 6,
    }
    if len(values["code"]) < 3:
        errors.append("Give the process a code of at least 3 characters, for example OPS-01.")
    if len(values["title"]) < 3:
        errors.append("Give the process a title of at least 3 characters.")
    return values, errors


def unique_code(db: DbSession, user_id: int, base: str) -> str:
    candidate = base or "OPS-01"
    suffix = 2
    while db.scalar(select(Sop.id).where(Sop.user_id == user_id, Sop.code == candidate)):
        candidate = f"{base}-{suffix}"[:20]
        suffix += 1
    return candidate


def apply_values(sop: Sop, values: dict) -> None:
    sop.code = values["code"]
    sop.title = values["title"]
    sop.area = values["area"]
    sop.purpose = values["purpose"]
    sop.scope = values["scope"]
    sop.owner_id = values["owner_id"] or None
    sop.cadence = values["cadence"]
    sop.review_months = values["review_months"]


@router.get("/sops")
def library_page(
    request: Request,
    q: str = "",
    status: str = "",
    area: str = "",
    owner: str = "",
    attention: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    sops = library(db, c.user.id)
    status = status if status in ("draft", "active", "retired") else ""
    area = area if area in AREAS else ""
    owner_id = integer(owner, 0) or None
    rows = sop_service.filtered(
        sops,
        q=clean(q, 120),
        status=status,
        area=area,
        owner_id=owner_id,
        attention=attention == "1",
        today=c.today,
    )
    return render(
        request,
        "library.html",
        c,
        sops=rows,
        all_counts=sop_service.counts(sops, c.today),
        states={sop.id: sop_service.review_state(sop, c.today) for sop in sops},
        step_counts={sop.id: len(sop.steps) for sop in sops},
        people=person_options(db, c.user.id),
        q=q,
        status=status,
        area=area,
        owner=owner_id or "",
        attention=attention == "1",
    )


@router.get("/sops/new")
def new_page(
    request: Request,
    area: str = "operations",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    area = area if area in AREAS else "operations"
    values = blank_values(area)
    values["code"] = sop_service.next_code(library(db, c.user.id), area)
    return render(
        request,
        "sop_form.html",
        c,
        mode="new",
        sop=None,
        values=values,
        errors=[],
        people=person_options(db, c.user.id),
    )


@router.post("/sops/new")
async def create_sop(
    request: Request,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    form = await request.form()
    values, errors = read_form(form, db, c.user.id)
    existing = db.scalar(select(Sop.id).where(Sop.user_id == c.user.id, Sop.code == values["code"]))
    if existing and not errors:
        errors.append("That code is already used by another process.")
    if errors:
        return render(
            request,
            "sop_form.html",
            c,
            http_status=409 if existing else 422,
            mode="new",
            sop=None,
            values=values,
            errors=errors,
            people=person_options(db, c.user.id),
        )
    sop = Sop(user_id=c.user.id, status="draft", version=1)
    apply_values(sop, values)
    db.add(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}?created=1")


@router.get("/sops/draft")
def draft_page(
    request: Request,
    area: str = "operations",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    area = area if area in AREAS else "operations"
    return render(
        request,
        "draft_form.html",
        c,
        area=area,
        description="",
        error=None,
    )


@router.post("/sops/draft")
async def draft_sop(
    request: Request,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    form = await request.form()
    description = clean(form.get("description"), draft_service.MAX_DESCRIPTION)
    area = choice(form.get("area"), AREAS, "operations")
    if len(description) < draft_service.MIN_DESCRIPTION:
        return render(
            request,
            "draft_form.html",
            c,
            http_status=422,
            area=area,
            description=description,
            error=f"Describe the process in at least {draft_service.MIN_DESCRIPTION} characters.",
        )
    limiter = request.app.state.ai_limiter
    key = str(c.user.id)
    if limiter.blocked(key):
        return render(
            request,
            "draft_form.html",
            c,
            http_status=429,
            area=area,
            description=description,
            error="Too many drafts in a short time. Try again in a few minutes.",
        )
    limiter.hit(key)
    proposal, note, source = draft_service.draft(request.app.state.settings, description, area)
    return render(
        request,
        "draft_result.html",
        c,
        http_status=200,
        proposal=proposal,
        note=note,
        source=source,
        area=area,
        description=description,
        people=person_options(db, c.user.id),
        code=sop_service.next_code(library(db, c.user.id), area),
    )


@router.post("/sops/draft/accept")
async def accept_draft(
    request: Request,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    form = await request.form()
    titles = form.getlist("step_title")
    details = form.getlist("step_detail")
    roles = form.getlist("step_role")
    owner_raw = integer(form.get("owner_id"), 0)
    owner_id = None
    if owner_raw:
        owner = db.scalar(select(Person).where(Person.id == owner_raw, Person.user_id == c.user.id))
        owner_id = owner.id if owner else None
    values = {
        "code": unique_code(db, c.user.id, clean(form.get("code"), 20).upper()),
        "title": clean(form.get("title"), 160),
        "area": choice(form.get("area"), AREAS, "operations"),
        "purpose": clean(form.get("purpose"), 1500),
        "scope": clean(form.get("scope"), 800),
        "owner_id": owner_id or "",
        "cadence": choice(form.get("cadence"), CADENCES, "monthly"),
        "review_months": integer(form.get("review_months"), 6),
    }
    if values["review_months"] not in REVIEW_MONTHS:
        values["review_months"] = 6
    if len(values["title"]) < 3 or len(values["purpose"]) < draft_service.MIN_DESCRIPTION:
        raise HTTPException(422, "The draft is missing a title or purpose. Start the draft again.")
    sop = Sop(user_id=c.user.id, status="draft", version=1)
    apply_values(sop, values)
    seen_positions = set()
    for index, title in enumerate(titles[:40], start=1):
        step_title = clean(title, 160)
        if len(step_title) < 3 or index in seen_positions:
            continue
        seen_positions.add(index)
        sop.steps.append(
            SopStep(
                position=index,
                title=step_title,
                detail=clean(details[index - 1] if index - 1 < len(details) else "", 600),
                role=clean(roles[index - 1] if index - 1 < len(roles) else "", 80),
            )
        )
    db.add(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}?created=1")


@router.get("/sops/{sop_id}")
def detail_page(
    request: Request,
    sop_id: int,
    created: str = "",
    reviewed: str = "",
    saved: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    sop = owned_sop(db, c.user.id, sop_id)
    runs = sorted(sop.runs, key=lambda run: (run.started_on, run.id), reverse=True)[:8]
    ready, problems = sop_service.ready_to_activate(sop)
    return render(
        request,
        "sop_detail.html",
        c,
        sop=sop,
        steps=sop_service.step_totals(sop),
        review=sop_service.review_state(sop, c.today),
        runs=runs,
        ready=ready,
        problems=problems,
        people=person_options(db, c.user.id),
        created=created == "1",
        reviewed=reviewed == "1",
        saved=saved == "1",
    )


@router.get("/sops/{sop_id}/edit")
def edit_page(
    request: Request,
    sop_id: int,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    sop = owned_sop(db, c.user.id, sop_id)
    return render(
        request,
        "sop_form.html",
        c,
        mode="edit",
        sop=sop,
        values=values_from(sop),
        errors=[],
        people=person_options(db, c.user.id, include_id=sop.owner_id),
    )


@router.post("/sops/{sop_id}/edit")
async def update_sop(
    request: Request,
    sop_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    sop = owned_sop(db, c.user.id, sop_id)
    form = await request.form()
    values, errors = read_form(form, db, c.user.id)
    clash = db.scalar(
        select(Sop.id).where(Sop.user_id == c.user.id, Sop.code == values["code"], Sop.id != sop.id)
    )
    if clash and not errors:
        errors.append("That code is already used by another process.")
    if errors:
        return render(
            request,
            "sop_form.html",
            c,
            http_status=409 if clash else 422,
            mode="edit",
            sop=sop,
            values=values,
            errors=errors,
            people=person_options(db, c.user.id, include_id=sop.owner_id),
        )
    before = (sop.code, sop.title, sop.area, sop.purpose, sop.scope)
    apply_values(sop, values)
    if before != (sop.code, sop.title, sop.area, sop.purpose, sop.scope):
        sop.version += 1
    touch(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}?saved=1")


@router.post("/sops/{sop_id}/status")
async def change_status(
    request: Request,
    sop_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    sop = owned_sop(db, c.user.id, sop_id)
    form = await request.form()
    action = str(form.get("action", ""))
    if action == "activate":
        ready, problems = sop_service.ready_to_activate(sop)
        if not ready:
            raise HTTPException(422, " ".join(problems))
        sop.status = "active"
    elif action == "retire":
        sop.status = "retired"
    elif action == "draft":
        sop.status = "draft"
    else:
        raise HTTPException(422, "Unknown status change.")
    touch(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}")


@router.post("/sops/{sop_id}/review")
def mark_reviewed(
    request: Request,
    sop_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    sop = owned_sop(db, c.user.id, sop_id)
    sop.last_reviewed_on = c.today
    touch(sop)
    db.commit()
    return see_other(f"/sops/{sop.id}?reviewed=1")


@router.post("/sops/{sop_id}/delete")
async def delete_sop(
    request: Request,
    sop_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    sop = owned_sop(db, c.user.id, sop_id)
    form = await request.form()
    if str(form.get("confirm", "")).strip() != sop.code:
        raise HTTPException(422, f"Type {sop.code} exactly to delete this process.")
    db.delete(sop)
    db.commit()
    return see_other("/sops")
