from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session as DbSession

from ..forms import choice, clean, integer
from ..models import (
    CONFIDENCE_LEVELS,
    COST_KINDS,
    REVENUE_MODELS,
    CostLine,
    RevenueStream,
)
from ..services import finance as finance_service
from ..web import Ctx, csrf, ctx, get_db, render, see_other
from ._shared import owned_cost, owned_stream, owned_venture, touch

router = APIRouter()
SCENARIO_KEYS = tuple(key for key, _label, _factor in finance_service.SCENARIOS)


def _page(
    request: Request,
    c: Ctx,
    venture,
    scenario: str = "base",
    edit_stream: int = 0,
    edit_cost: int = 0,
    error: str | None = None,
    status: int = 200,
):
    scenario = scenario if scenario in SCENARIO_KEYS else "base"
    streams = sorted(venture.streams, key=lambda s: (-finance_service.stream_expected(s), s.id))
    costs = sorted(venture.costs, key=lambda c: (c.kind, c.name.lower(), c.id))
    return render(
        request,
        "revenue.html",
        c,
        http_status=status,
        venture=venture,
        streams=streams,
        costs=costs,
        summary=finance_service.summary(streams, costs, scenario=scenario, currency=venture.currency),
        scenarios=finance_service.scenario_table(streams, costs),
        models=finance_service.by_model(streams),
        scenario=scenario,
        edit_stream=next((s for s in streams if s.id == edit_stream), None),
        edit_cost=next((c for c in costs if c.id == edit_cost), None),
        error=error,
    )


@router.get("/ventures/{venture_id}/revenue")
def revenue_page(
    request: Request,
    venture_id: int,
    scenario: str = "base",
    edit_stream: int = 0,
    edit_cost: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    return _page(request, c, venture, scenario=scenario, edit_stream=edit_stream, edit_cost=edit_cost)


@router.post("/ventures/{venture_id}/revenue/streams")
def add_stream(
    request: Request,
    venture_id: int,
    name: str = Form(""),
    model: str = Form("subscription"),
    price: str = Form("0"),
    unit: str = Form("per month"),
    volume: str = Form("0"),
    confidence: str = Form("medium"),
    notes: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    name, unit, notes = clean(name, 120), clean(unit, 60) or "per month", clean(notes, 300)
    if len(name) < 2:
        return _page(request, c, venture, error="Name the revenue stream (at least two characters).", status=422)
    db.add(
        RevenueStream(
            venture_id=venture.id,
            name=name,
            model=choice(model, REVENUE_MODELS, "subscription"),
            price=integer(price, 0),
            unit=unit,
            volume=integer(volume, 0),
            confidence=choice(confidence, CONFIDENCE_LEVELS, "medium"),
            notes=notes,
        )
    )
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/revenue#streams")


@router.post("/streams/{stream_id}/edit")
def edit_stream(
    request: Request,
    stream_id: int,
    name: str = Form(""),
    model: str = Form("subscription"),
    price: str = Form("0"),
    unit: str = Form("per month"),
    volume: str = Form("0"),
    confidence: str = Form("medium"),
    notes: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    stream, venture = owned_stream(db, stream_id, c.user.id)
    name, unit, notes = clean(name, 120), clean(unit, 60) or "per month", clean(notes, 300)
    if len(name) < 2:
        return _page(request, c, venture, edit_stream=stream.id, error="Name the revenue stream (at least two characters).", status=422)
    stream.name = name
    stream.model = choice(model, REVENUE_MODELS, stream.model)
    stream.price = integer(price, stream.price)
    stream.unit = unit
    stream.volume = integer(volume, stream.volume)
    stream.confidence = choice(confidence, CONFIDENCE_LEVELS, stream.confidence)
    stream.notes = notes
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/revenue#streams")


@router.post("/streams/{stream_id}/delete")
def delete_stream(
    request: Request,
    stream_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    stream, venture = owned_stream(db, stream_id, c.user.id)
    db.delete(stream)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/revenue#streams")


@router.post("/ventures/{venture_id}/revenue/costs")
def add_cost(
    request: Request,
    venture_id: int,
    name: str = Form(""),
    amount: str = Form("0"),
    kind: str = Form("fixed"),
    notes: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    name, notes = clean(name, 120), clean(notes, 300)
    if len(name) < 2:
        return _page(request, c, venture, error="Name the cost line (at least two characters).", status=422)
    db.add(
        CostLine(
            venture_id=venture.id,
            name=name,
            amount=integer(amount, 0),
            kind=choice(kind, COST_KINDS, "fixed"),
            notes=notes,
        )
    )
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/revenue#costs")


@router.post("/costs/{cost_id}/edit")
def edit_cost(
    request: Request,
    cost_id: int,
    name: str = Form(""),
    amount: str = Form("0"),
    kind: str = Form("fixed"),
    notes: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    cost, venture = owned_cost(db, cost_id, c.user.id)
    name, notes = clean(name, 120), clean(notes, 300)
    if len(name) < 2:
        return _page(request, c, venture, edit_cost=cost.id, error="Name the cost line (at least two characters).", status=422)
    cost.name, cost.notes = name, notes
    cost.amount = integer(amount, cost.amount)
    cost.kind = choice(kind, COST_KINDS, cost.kind)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/revenue#costs")


@router.post("/costs/{cost_id}/delete")
def delete_cost(
    request: Request,
    cost_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    cost, venture = owned_cost(db, cost_id, c.user.id)
    db.delete(cost)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/revenue#costs")
