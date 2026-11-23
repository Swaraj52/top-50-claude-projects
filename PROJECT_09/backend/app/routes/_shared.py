"""Ownership checks and small route helpers shared by the workspace modules."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..models import CanvasEntry, CostLine, Kpi, KpiReading, Milestone, RevenueStream, SwotItem, Venture


def owned_venture(db: DbSession, user_id: int, venture_id: int) -> Venture:
    venture = db.scalar(select(Venture).where(Venture.id == venture_id, Venture.user_id == user_id))
    if venture is None:
        raise HTTPException(404, "That venture doesn't exist.")
    return venture


def touch(venture: Venture) -> None:
    venture.updated_at = utcnow()


def _owned_child(db: DbSession, model, child_id: int, user_id: int):
    row = db.get(model, child_id)
    if row is None:
        raise HTTPException(404, "That entry doesn't exist.")
    venture = owned_venture(db, user_id, row.venture_id)
    return row, venture


def owned_canvas(db: DbSession, entry_id: int, user_id: int) -> tuple[CanvasEntry, Venture]:
    return _owned_child(db, CanvasEntry, entry_id, user_id)


def owned_swot(db: DbSession, item_id: int, user_id: int) -> tuple[SwotItem, Venture]:
    return _owned_child(db, SwotItem, item_id, user_id)


def owned_stream(db: DbSession, stream_id: int, user_id: int) -> tuple[RevenueStream, Venture]:
    return _owned_child(db, RevenueStream, stream_id, user_id)


def owned_cost(db: DbSession, cost_id: int, user_id: int) -> tuple[CostLine, Venture]:
    return _owned_child(db, CostLine, cost_id, user_id)


def owned_milestone(db: DbSession, milestone_id: int, user_id: int) -> tuple[Milestone, Venture]:
    return _owned_child(db, Milestone, milestone_id, user_id)


def owned_kpi(db: DbSession, kpi_id: int, user_id: int) -> tuple[Kpi, Venture]:
    return _owned_child(db, Kpi, kpi_id, user_id)


def owned_reading(db: DbSession, reading_id: int, user_id: int) -> tuple[KpiReading, Kpi, Venture]:
    reading = db.get(KpiReading, reading_id)
    if reading is None:
        raise HTTPException(404, "That reading doesn't exist.")
    kpi, venture = owned_kpi(db, reading.kpi_id, user_id)
    return reading, kpi, venture
