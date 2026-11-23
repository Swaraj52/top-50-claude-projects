from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session as DbSession

from ..forms import choice, clean, integer
from ..models import QUADRANTS, QUADRANT_HELP, QUADRANT_LABELS, SwotItem
from ..services import swot as swot_service
from ..web import Ctx, csrf, ctx, get_db, render, see_other
from ._shared import owned_swot, owned_venture, touch

router = APIRouter()


def _page(request: Request, c: Ctx, venture, edit_id: int = 0, error: str | None = None, status: int = 200):
    items = sorted(venture.swot, key=lambda i: (-i.impact, i.id))
    edit_item = next((i for i in items if i.id == edit_id), None) if edit_id else None
    return render(
        request,
        "swot.html",
        c,
        http_status=status,
        venture=venture,
        summary=swot_service.summary(items),
        quadrants=QUADRANTS,
        labels=QUADRANT_LABELS,
        help_text=QUADRANT_HELP,
        edit_item=edit_item,
        error=error,
    )


@router.get("/ventures/{venture_id}/swot")
def swot_page(
    request: Request,
    venture_id: int,
    edit: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    return _page(request, c, venture, edit_id=edit)


@router.post("/ventures/{venture_id}/swot")
def add_item(
    request: Request,
    venture_id: int,
    quadrant: str = Form("strength"),
    text: str = Form(""),
    impact: str = Form("3"),
    evidence: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    quadrant = choice(quadrant, QUADRANTS, "strength")
    text, evidence = clean(text, 300), clean(evidence, 300)
    if len(text) < 3:
        return _page(request, c, venture, error="Write at least three characters.", status=422)
    db.add(
        SwotItem(
            venture_id=venture.id,
            quadrant=quadrant,
            text=text,
            impact=integer(impact, 3, 1, 5),
            evidence=evidence,
        )
    )
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/swot#{quadrant}")


@router.post("/swot/{item_id}/edit")
def edit_item(
    request: Request,
    item_id: int,
    quadrant: str = Form("strength"),
    text: str = Form(""),
    impact: str = Form("3"),
    evidence: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    item, venture = owned_swot(db, item_id, c.user.id)
    quadrant = choice(quadrant, QUADRANTS, item.quadrant)
    text, evidence = clean(text, 300), clean(evidence, 300)
    if len(text) < 3:
        return _page(request, c, venture, edit_id=item.id, error="Write at least three characters.", status=422)
    item.quadrant, item.text, item.evidence = quadrant, text, evidence
    item.impact = integer(impact, item.impact, 1, 5)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/swot#{quadrant}")


@router.post("/swot/{item_id}/delete")
def delete_item(
    request: Request,
    item_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    item, venture = owned_swot(db, item_id, c.user.id)
    quadrant = item.quadrant
    db.delete(item)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/swot#{quadrant}")
