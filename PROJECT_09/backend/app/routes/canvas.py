from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session as DbSession

from ..forms import choice, clean
from ..models import CANVAS_BLOCKS, CANVAS_LABELS, CANVAS_PROMPTS, CanvasEntry
from ..services import canvas as canvas_service
from ..web import Ctx, csrf, ctx, get_db, render, see_other
from ._shared import owned_canvas, owned_venture, touch

router = APIRouter()


def _page(request: Request, c: Ctx, db: DbSession, venture, edit_id: int = 0, error: str | None = None, status: int = 200):
    entries = sorted(venture.canvas, key=lambda e: (e.sort_order, e.id))
    edit_entry = next((e for e in entries if e.id == edit_id), None) if edit_id else None
    return render(
        request,
        "canvas.html",
        c,
        http_status=status,
        venture=venture,
        entries=entries,
        grouped=canvas_service.grouped(entries),
        completeness=canvas_service.completeness(entries),
        gaps=canvas_service.gaps(entries),
        blocks=CANVAS_BLOCKS,
        labels=CANVAS_LABELS,
        prompts=CANVAS_PROMPTS,
        edit_entry=edit_entry,
        error=error,
    )


@router.get("/ventures/{venture_id}/canvas")
def canvas_page(
    request: Request,
    venture_id: int,
    edit: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    return _page(request, c, db, venture, edit_id=edit)


@router.post("/ventures/{venture_id}/canvas")
def add_entry(
    request: Request,
    venture_id: int,
    block: str = Form("problem"),
    title: str = Form(""),
    detail: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    block = choice(block, CANVAS_BLOCKS, "problem")
    title, detail = clean(title, 160), clean(detail, 600)
    if len(title) < 3:
        return _page(request, c, db, venture, error="A canvas note needs a title of at least three characters.", status=422)
    order = max([e.sort_order for e in venture.canvas] + [0]) + 1
    db.add(CanvasEntry(venture_id=venture.id, block=block, title=title, detail=detail, sort_order=order))
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/canvas#{block}")


@router.post("/canvas/{entry_id}/edit")
def edit_entry(
    request: Request,
    entry_id: int,
    block: str = Form("problem"),
    title: str = Form(""),
    detail: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    entry, venture = owned_canvas(db, entry_id, c.user.id)
    block = choice(block, CANVAS_BLOCKS, entry.block)
    title, detail = clean(title, 160), clean(detail, 600)
    if len(title) < 3:
        return _page(request, c, db, venture, edit_id=entry.id, error="A canvas note needs a title of at least three characters.", status=422)
    entry.block, entry.title, entry.detail = block, title, detail
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/canvas#{block}")


@router.post("/canvas/{entry_id}/delete")
def delete_entry(
    request: Request,
    entry_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    entry, venture = owned_canvas(db, entry_id, c.user.id)
    block = entry.block
    db.delete(entry)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/canvas#{block}")
