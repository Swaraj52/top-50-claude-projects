from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..forms import choice, clean
from ..models import (
    CURRENCIES,
    HORIZONS,
    STAGES,
    Venture,
)
from ..services import brief as brief_service
from ..services import overview as overview_service
from ..web import Ctx, csrf, ctx, get_db, is_htmx, render, see_other
from ._shared import owned_venture, touch

router = APIRouter()


def _form_values(venture: Venture | None = None, **overrides) -> dict:
    values = {
        "name": venture.name if venture else "",
        "one_liner": venture.one_liner if venture else "",
        "stage": venture.stage if venture else "idea",
        "horizon": venture.horizon if venture else "90 days",
        "currency": venture.currency if venture else "INR",
        "segment": venture.segment if venture else "",
        "market": venture.market if venture else "",
        "alternatives": venture.alternatives if venture else "",
        "differentiation": venture.differentiation if venture else "",
    }
    values.update(overrides)
    return values


def _read_form(request_form: dict) -> dict:
    return {
        "name": clean(request_form.get("name"), 120),
        "one_liner": clean(request_form.get("one_liner"), 240),
        "stage": choice(request_form.get("stage"), STAGES, "idea"),
        "horizon": choice(request_form.get("horizon"), HORIZONS, "90 days"),
        "currency": choice(request_form.get("currency"), CURRENCIES, "INR"),
        "segment": clean(request_form.get("segment"), 240),
        "market": clean(request_form.get("market"), 2000),
        "alternatives": clean(request_form.get("alternatives"), 2000),
        "differentiation": clean(request_form.get("differentiation"), 2000),
    }


@router.get("/")
def dashboard(
    request: Request,
    archived: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    ventures = list(
        db.scalars(
            select(Venture)
            .where(Venture.user_id == c.user.id, Venture.archived == bool(archived))
            .order_by(Venture.updated_at.desc(), Venture.id)
        ).all()
    )
    cards = [{"venture": v, "snap": overview_service.snapshot(v, c.today)} for v in ventures]
    archived_count = db.scalar(
        select(func.count(Venture.id)).where(Venture.user_id == c.user.id, Venture.archived.is_(True))
    )
    totals = {
        "ventures": len(ventures),
        "milestones": sum(card["snap"]["plan"]["open"] for card in cards),
        "overdue": sum(card["snap"]["plan"]["overdue_count"] for card in cards),
        "attention": sum(len(card["snap"]["kpis"]["attention"]) for card in cards),
    }
    return render(
        request,
        "dashboard.html",
        c,
        cards=cards,
        totals=totals,
        archived=bool(archived),
        archived_count=archived_count or 0,
    )


@router.get("/ventures/new")
def new_venture(request: Request, c: Ctx = Depends(ctx)):
    return render(request, "venture_form.html", c, values=_form_values(), error=None, editing=False)


@router.post("/ventures/new")
async def create_venture(
    request: Request,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    form = await request.form()
    values = _read_form(form)
    if len(values["name"]) < 2:
        return render(
            request,
            "venture_form.html",
            c,
            http_status=422,
            values=values,
            error="Give the venture a name of at least two characters.",
            editing=False,
        )
    exists = db.scalar(
        select(Venture.id).where(Venture.user_id == c.user.id, Venture.name == values["name"])
    )
    if exists:
        return render(
            request,
            "venture_form.html",
            c,
            http_status=409,
            values=values,
            error="You already have a venture with that name.",
            editing=False,
        )
    venture = Venture(user_id=c.user.id, **values)
    db.add(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}?saved=1")


@router.get("/ventures/{venture_id}")
def overview(
    request: Request,
    venture_id: int,
    saved: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    snap = overview_service.snapshot(venture, c.today)
    return render(
        request,
        "venture_overview.html",
        c,
        venture=venture,
        snap=snap,
        headline=overview_service.headline(venture, snap),
        saved=bool(saved),
    )


@router.get("/ventures/{venture_id}/edit")
def edit_page(
    request: Request,
    venture_id: int,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    return render(
        request,
        "venture_form.html",
        c,
        values=_form_values(venture),
        error=None,
        editing=True,
        venture=venture,
    )


@router.post("/ventures/{venture_id}/edit")
async def edit_venture(
    request: Request,
    venture_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    values = _read_form(await request.form())
    if len(values["name"]) < 2:
        return render(
            request,
            "venture_form.html",
            c,
            http_status=422,
            values=values,
            error="Give the venture a name of at least two characters.",
            editing=True,
            venture=venture,
        )
    clash = db.scalar(
        select(Venture.id).where(
            Venture.user_id == c.user.id, Venture.name == values["name"], Venture.id != venture.id
        )
    )
    if clash:
        return render(
            request,
            "venture_form.html",
            c,
            http_status=409,
            values=values,
            error="Another venture already uses that name.",
            editing=True,
            venture=venture,
        )
    for key, value in values.items():
        setattr(venture, key, value)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}?saved=1")


@router.post("/ventures/{venture_id}/archive")
def archive(
    request: Request,
    venture_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    venture.archived = not venture.archived
    touch(venture)
    db.commit()
    return see_other("/?archived=1" if venture.archived else f"/ventures/{venture.id}")


@router.post("/ventures/{venture_id}/delete")
def delete_venture(
    request: Request,
    venture_id: int,
    confirm: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    if confirm.strip() != venture.name:
        raise HTTPException(422, "Type the venture name exactly to delete it.")
    db.delete(venture)
    db.commit()
    return see_other("/")


def _brief_context(venture: Venture, c: Ctx) -> dict:
    snap = overview_service.snapshot(venture, c.today)
    blocks = brief_service.sections(
        venture, snap["entries"], snap["finance"], snap["plan"], snap["kpis"], snap["swot"]
    )
    generated = brief_service.memo(
        venture, snap["entries"], snap["finance"], snap["plan"], snap["kpis"], snap["swot"]
    )
    saved = bool(venture.narrative)
    return {
        "venture": venture,
        "snap": snap,
        "blocks": blocks,
        "generated": generated,
        "narrative": venture.narrative or generated,
        "saved": saved,
        "source": venture.narrative_source if saved else "draft",
        "generated_at": venture.narrative_at,
    }


@router.get("/ventures/{venture_id}/brief")
def brief_page(
    request: Request,
    venture_id: int,
    ai: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    context = _brief_context(venture, c)
    return render(request, "brief.html", c, **context, ai=ai or None)


@router.post("/ventures/{venture_id}/brief")
def save_local_brief(
    request: Request,
    venture_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    context = _brief_context(venture, c)
    venture.narrative = context["generated"]
    venture.narrative_source = "local"
    venture.narrative_at = utcnow()
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/brief?saved=1")


@router.post("/ventures/{venture_id}/brief/ai")
def rewrite_brief(
    request: Request,
    venture_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    from ..services import ai as ai_service

    venture = owned_venture(db, c.user.id, venture_id)
    context = _brief_context(venture, c)
    settings = request.app.state.settings
    narrative, note = ai_service.rewrite(settings, venture, context["generated"], context["blocks"])
    if narrative is not None:
        venture.narrative = narrative
        venture.narrative_source = "claude"
        venture.narrative_at = utcnow()
        touch(venture)
        db.commit()
        note = "Claude rewrote the memo from the stored facts. Check it before sending."
    if is_htmx(request):
        refreshed = _brief_context(venture, c)
        refreshed["note"] = note if narrative is None else ""
        refreshed["ai"] = None
        return render(request, "_memo.html", c, **refreshed)
    return see_other(f"/ventures/{venture.id}/brief?ai={'saved' if narrative else 'failed'}")


@router.post("/ventures/{venture_id}/brief/reset")
def reset_brief(
    request: Request,
    venture_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    venture.narrative = ""
    venture.narrative_source = "local"
    venture.narrative_at = None
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/brief")
