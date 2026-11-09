"""Trends, history and settings."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Review
from ..services import charts, trends
from ..services.day import recurring_blockers
from ..timeutil import is_valid_timezone
from ..web import Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()


@router.get("/trends")
def trends_page(request: Request, span: int = 7, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    span = 14 if span == 14 else 7
    t = trends.compute(db, c.user, c.tz, c.today, span)
    figures = {
        "completed": charts.bar_chart("Tasks completed per day", t.labels, [float(v) for v in t.completed]),
        "focus": charts.bar_chart("Focus hours per day", t.labels, [v or 0.0 for v in t.focus], unit="h"),
        "wellbeing": charts.line_chart(
            "Energy and mood (1-5)", t.labels, [("Energy", t.energy, "energy"), ("Mood", t.mood, "mood")], max_v=5
        ),
    }
    return render(request, "trends.html", c, t=t, span=span, figures=figures, recurring=recurring_blockers(db, c.user, c.today, window=span))


@router.get("/history")
def history(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    reviews = db.scalars(select(Review).where(Review.user_id == c.user.id).order_by(Review.day.desc()).limit(90)).all()
    return render(request, "history.html", c, reviews=reviews)


@router.get("/history/{day}")
def history_day(request: Request, day: str, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    try:
        d = date.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(404, "Not found") from exc
    review = db.scalar(select(Review).where(Review.user_id == c.user.id, Review.day == d))
    if review is None:
        raise HTTPException(404, "No review for that day")
    return render(request, "history_day.html", c, review=review)


@router.get("/settings")
def settings_page(request: Request, saved: int = 0, c: Ctx = Depends(ctx)):
    return render(request, "settings.html", c, saved=bool(saved))


@router.post("/settings")
def save_settings(
    name: str = Form(""),
    timezone: str = Form("UTC"),
    capacity_hours: float = Form(6.0),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    name = " ".join(name.split())
    if not name or len(name) > 80:
        raise HTTPException(422, "Name must be 1-80 characters.")
    if not is_valid_timezone(timezone):
        raise HTTPException(422, "Unknown timezone.")
    if not 0.5 <= capacity_hours <= 16:
        raise HTTPException(422, "Capacity must be between 0.5 and 16 hours.")
    user = db.merge(c.user)
    user.name, user.timezone, user.capacity_hours = name, timezone, round(capacity_hours * 4) / 4
    db.commit()
    return see_other("/settings?saved=1")
