"""Weekly reflection, report and longer-term insights."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..db import utcnow
from ..models import Habit, Reflection
from ..services import charts, habitmath
from ..timeutil import parse_week, week_label
from ..web import Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()


def _habits(db: DbSession, user_id: int) -> list[Habit]:
    return list(
        db.scalars(
            select(Habit)
            .where(Habit.user_id == user_id, Habit.status == "active")
            .options(selectinload(Habit.logs))
            .order_by(Habit.created_at, Habit.id)
        ).all()
    )


@router.get("/reflect")
def reflect_page(request: Request, week: str = "", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    start = parse_week(week, c.today)
    habits = _habits(db, c.user.id)
    reflections = list(
        db.scalars(select(Reflection).where(Reflection.user_id == c.user.id).order_by(Reflection.week_start.desc())).all()
    )
    report = habitmath.weekly_report(habits, {h.id: h.logs for h in habits}, reflections, start, c.today)
    return render(
        request,
        "reflect.html",
        c,
        week_start=start,
        week_label=week_label(start),
        prev_week=(start - timedelta(days=7)).isoformat(),
        next_week=(start + timedelta(days=7)).isoformat(),
        is_current=start == c.week_start,
        report=report,
        reflection=report["reflection"],
        prompts=habitmath.reflection_prompts(start),
        history=reflections[:8],
        reflection_streak=habitmath.reflection_streak(reflections, c.today),
        saved=request.query_params.get("saved") == "1",
    )


@router.post("/reflect")
def save_reflection(
    week: str = Form(""),
    mood: int = Form(3),
    worked: str = Form(""),
    friction: str = Form(""),
    change: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    start = parse_week(week, c.today)
    mood = max(1, min(5, int(mood)))
    reflection = db.scalar(select(Reflection).where(Reflection.user_id == c.user.id, Reflection.week_start == start))
    if reflection is None:
        reflection = Reflection(user_id=c.user.id, week_start=start, created_at=utcnow())
        db.add(reflection)
    reflection.mood = mood
    reflection.worked = (worked or "").strip()[:2000]
    reflection.friction = (friction or "").strip()[:2000]
    reflection.change = (change or "").strip()[:2000]
    db.commit()
    return see_other(f"/reflect?week={start.isoformat()}&saved=1")


@router.get("/insights")
def insights(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    habits = _habits(db, c.user.id)
    logs_by_habit = {h.id: h.logs for h in habits}
    series = habitmath.weekly_series(habits, logs_by_habit, c.today, 8)
    pattern = habitmath.weekday_pattern(habits, logs_by_habit, c.today, 8)
    reflections = list(
        db.scalars(select(Reflection).where(Reflection.user_id == c.user.id).order_by(Reflection.week_start.desc())).all()
    )
    total_done = sum(series["done"])
    total_scheduled = sum(series["scheduled"])
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    best_weekday = max((row for row in pattern if row["rate"] is not None), key=lambda r: r["rate"], default=None)
    consistency = habitmath.habit_consistency(habits, logs_by_habit, c.today)
    return render(
        request,
        "insights.html",
        c,
        series=series,
        pattern=pattern,
        consistency=consistency,
        volume_chart=charts.bar_chart(series["labels"], [float(v) for v in series["done"]], title="Completed habit days per week"),
        pattern_chart=charts.bar_chart(labels, [float(r["rate"] or 0) for r in pattern], title="Completion rate by weekday", unit="%"),
        total_done=total_done,
        total_scheduled=total_scheduled,
        rate=round(100 * total_done / total_scheduled) if total_scheduled else None,
        best_weekday=best_weekday,
        reflection_count=len(reflections),
        reflection_streak=habitmath.reflection_streak(reflections, c.today),
        active_count=sum(1 for h in habits if h.status == "active"),
    )
