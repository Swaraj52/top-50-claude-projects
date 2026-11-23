from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..forms import choice, clean, parse_date, real_or_none
from ..models import (
    CADENCES,
    DIRECTIONS,
    Kpi,
    KpiReading,
)
from ..services import kpis as kpi_service
from ..web import Ctx, csrf, ctx, get_db, render, see_other
from ._shared import owned_kpi, owned_reading, owned_venture, touch

router = APIRouter()


def _page(
    request: Request,
    c: Ctx,
    venture,
    edit_id: int = 0,
    reading_id: int = 0,
    error: str | None = None,
    status: int = 200,
    saved: bool = False,
):
    kpis = sorted(venture.kpis, key=lambda k: (k.name.lower(), k.id))
    return render(
        request,
        "kpis.html",
        c,
        http_status=status,
        venture=venture,
        kpis=kpis,
        summary=kpi_service.summary(kpis, c.today),
        edit_kpi=next((k for k in kpis if k.id == edit_id), None),
        reading_kpi=next((k for k in kpis if k.id == reading_id), None),
        error=error,
        saved=saved,
    )


@router.get("/ventures/{venture_id}/kpis")
def kpis_page(
    request: Request,
    venture_id: int,
    edit: int = 0,
    reading: int = 0,
    saved: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    return _page(request, c, venture, edit_id=edit, reading_id=reading, saved=bool(saved))


@router.post("/ventures/{venture_id}/kpis")
def add_kpi(
    request: Request,
    venture_id: int,
    name: str = Form(""),
    unit: str = Form(""),
    direction: str = Form("up"),
    baseline: str = Form("0"),
    target: str = Form(""),
    target_date: str = Form(""),
    cadence: str = Form("monthly"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    venture = owned_venture(db, c.user.id, venture_id)
    name, unit = clean(name, 120), clean(unit, 40)
    base_value, target_value = real_or_none(baseline), real_or_none(target)
    if len(name) < 2:
        return _page(request, c, venture, error="Name the KPI (at least two characters).", status=422)
    if base_value is None or target_value is None:
        return _page(request, c, venture, error="Baseline and target must both be numbers.", status=422)
    if base_value == target_value:
        return _page(request, c, venture, error="The target must differ from the baseline.", status=422)
    db.add(
        Kpi(
            venture_id=venture.id,
            name=name,
            unit=unit,
            direction=choice(direction, DIRECTIONS, "up"),
            baseline=base_value,
            target=target_value,
            target_date=parse_date(target_date),
            cadence=choice(cadence, CADENCES, "monthly"),
        )
    )
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/kpis")


@router.post("/kpis/{kpi_id}/edit")
def edit_kpi(
    request: Request,
    kpi_id: int,
    name: str = Form(""),
    unit: str = Form(""),
    direction: str = Form("up"),
    baseline: str = Form("0"),
    target: str = Form(""),
    target_date: str = Form(""),
    cadence: str = Form("monthly"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    kpi, venture = owned_kpi(db, kpi_id, c.user.id)
    name, unit = clean(name, 120), clean(unit, 40)
    base_value, target_value = real_or_none(baseline), real_or_none(target)
    if len(name) < 2:
        return _page(request, c, venture, edit_id=kpi.id, error="Name the KPI (at least two characters).", status=422)
    if base_value is None or target_value is None:
        return _page(request, c, venture, edit_id=kpi.id, error="Baseline and target must both be numbers.", status=422)
    if base_value == target_value:
        return _page(request, c, venture, edit_id=kpi.id, error="The target must differ from the baseline.", status=422)
    kpi.name, kpi.unit = name, unit
    kpi.direction = choice(direction, DIRECTIONS, kpi.direction)
    kpi.baseline, kpi.target = base_value, target_value
    kpi.target_date = parse_date(target_date)
    kpi.cadence = choice(cadence, CADENCES, kpi.cadence)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/kpis")


@router.post("/kpis/{kpi_id}/readings")
def add_reading(
    request: Request,
    kpi_id: int,
    value: str = Form(""),
    recorded_on: str = Form(""),
    note: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    kpi, venture = owned_kpi(db, kpi_id, c.user.id)
    parsed = real_or_none(value)
    if parsed is None:
        return _page(request, c, venture, reading_id=kpi.id, error="A reading needs a number.", status=422)
    day = parse_date(recorded_on) or c.today
    if day > c.today:
        return _page(request, c, venture, reading_id=kpi.id, error="A reading cannot be dated in the future.", status=422)
    existing = db.scalar(
        select(KpiReading).where(KpiReading.kpi_id == kpi.id, KpiReading.recorded_on == day)
    )
    if existing is not None:
        existing.value = parsed
        existing.note = clean(note, 200)
    else:
        db.add(KpiReading(kpi_id=kpi.id, value=parsed, recorded_on=day, note=clean(note, 200)))
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/kpis?saved=1")


@router.post("/readings/{reading_id}/delete")
def delete_reading(
    request: Request,
    reading_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    reading, _kpi, venture = owned_reading(db, reading_id, c.user.id)
    db.delete(reading)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/kpis")


@router.post("/kpis/{kpi_id}/delete")
def delete_kpi(
    request: Request,
    kpi_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    kpi, venture = owned_kpi(db, kpi_id, c.user.id)
    db.delete(kpi)
    touch(venture)
    db.commit()
    return see_other(f"/ventures/{venture.id}/kpis")
