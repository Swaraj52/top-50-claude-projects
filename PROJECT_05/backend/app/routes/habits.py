"""Dashboard, habit CRUD, daily logs, calendar and the coach."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..db import utcnow
from ..models import HABIT_STATUSES, Habit, HabitLog, Reflection, Suggestion
from ..services import ai, charts, habitmath
from ..timeutil import days_to_string, month_bounds, parse_days, parse_week, week_label
from ..web import Ctx, csrf, ctx, get_db, is_htmx, render, see_other

router = APIRouter()


def _safe_next(value: str, fallback: str) -> str:
    value = (value or "").strip()
    return value if value.startswith("/") and not value.startswith("//") else fallback


def _habits(db: DbSession, user_id: int, status: str | None = None) -> list[Habit]:
    stmt = select(Habit).where(Habit.user_id == user_id).options(selectinload(Habit.logs)).order_by(Habit.created_at, Habit.id)
    if status and status in HABIT_STATUSES:
        stmt = stmt.where(Habit.status == status)
    return list(db.scalars(stmt).all())


def owned_habit(db: DbSession, user_id: int, habit_id: int) -> Habit:
    habit = db.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id).options(selectinload(Habit.logs)))
    if habit is None:
        raise HTTPException(404, "That habit doesn't exist.")
    return habit


def _clean(value: str, field: str, limit: int, minimum: int = 0) -> str:
    value = " ".join((value or "").split())
    if len(value) < minimum:
        raise HTTPException(422, f"Please add a {field}.")
    if len(value) > limit:
        raise HTTPException(422, f"The {field} is too long (max {limit} characters).")
    return value


def _long(value: str, limit: int = 1000) -> str:
    return (value or "").strip()[:limit]


def _days(values: list[str]) -> str:
    parsed = sorted({int(v) for v in values if str(v).isdigit() and 0 <= int(v) <= 6})
    if not parsed:
        raise HTTPException(422, "Choose at least one day for this habit.")
    return days_to_string(parsed)


def _parse_day(value: str, habit: Habit, today: date) -> date:
    try:
        day = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Use a valid date.") from exc
    if day > today:
        raise HTTPException(422, "You can't log a future day.")
    if day < habit.created_at.date():
        raise HTTPException(422, "That day is before this habit existed.")
    return day


def _logs_map(habits: list[Habit]) -> dict[int, list[HabitLog]]:
    return {habit.id: list(habit.logs) for habit in habits}


@router.get("/")
def dashboard(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    habits = _habits(db, c.user.id, "active")
    logs_by_habit = _logs_map(habits)
    today_rows = []
    for habit in habits:
        if not habitmath.scheduled(habit, c.today):
            continue
        log = habitmath.log_map(habit.logs).get(c.today)
        today_rows.append({"habit": habit, "log": log, "streak": habitmath.streak(habit, habit.logs, c.today)})
    stats = {habit.id: habitmath.habit_stats(habit, habit.logs, c.today) for habit in habits}
    at_risk = [habit for habit in habits if stats[habit.id]["at_risk"]]
    today_done = sum(1 for row in today_rows if row["log"] is not None and row["log"].status == "done")

    start = c.week_start
    end = start + timedelta(days=6)
    totals = {"scheduled": 0, "done": 0, "missed": 0, "skipped": 0}
    for habit in habits:
        week = habitmath.range_stats(habit, habit.logs, start, min(end, c.today), c.today)
        for key in totals:
            totals[key] += week[key]
    decided = totals["done"] + totals["missed"]
    week_rate = round(100 * totals["done"] / decided) if decided else None
    series = habitmath.weekly_series(habits, logs_by_habit, c.today, 6)
    reflections = list(db.scalars(select(Reflection).where(Reflection.user_id == c.user.id).order_by(Reflection.week_start.desc())).all())
    suggestions = list(
        db.scalars(select(Suggestion).where(Suggestion.user_id == c.user.id).order_by(Suggestion.created_at.desc(), Suggestion.id.desc()).limit(3)).all()
    )
    return render(
        request,
        "dashboard.html",
        c,
        habits=habits,
        today_rows=today_rows,
        stats=stats,
        at_risk=at_risk,
        totals=totals,
        week_rate=week_rate,
        series=series,
        chart=charts.bar_chart(series["labels"], [float(v) for v in series["done"]], title="Completed habit days per week"),
        reflection=next((r for r in reflections if r.week_start == c.week_start), None),
        reflection_prompts=habitmath.reflection_prompts(c.today),
        reflection_streak=habitmath.reflection_streak(reflections, c.today),
        suggestions=suggestions,
        week_label=week_label(c.week_start),
        coach_source=request.query_params.get("source", ""),
        today_done=today_done,
        today_total=len(today_rows),
    )


@router.get("/habits")
def habits_page(request: Request, status: str = "active", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    status = status if status in (*HABIT_STATUSES, "all") else "active"
    habits = _habits(db, c.user.id, None if status == "all" else status)
    all_habits = _habits(db, c.user.id)
    counts = {s: sum(1 for h in all_habits if h.status == s) for s in HABIT_STATUSES}
    rows = []
    for habit in habits:
        strip = []
        for offset in range(13, -1, -1):
            day = c.today - timedelta(days=offset)
            strip.append({"day": day, "status": habitmath.calendar_status(habit, habit.logs, day, c.today)})
        rows.append({"habit": habit, "stats": habitmath.habit_stats(habit, habit.logs, c.today), "strip": strip})
    return render(request, "habits.html", c, rows=rows, counts=counts, current_status=status)


@router.post("/habits")
def create_habit(
    title: str = Form(""),
    intention: str = Form(""),
    cue: str = Form(""),
    days: list[str] = Form(default=[]),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    habit = Habit(
        user_id=c.user.id,
        title=_clean(title, "habit", 120, 2),
        intention=_long(intention),
        cue=_clean(cue, "cue", 160) if cue.strip() else "",
        days=_days(days),
        created_at=utcnow(),
    )
    db.add(habit)
    db.commit()
    return see_other(f"/habits/{habit.id}")


@router.get("/habits/{habit_id}")
def habit_detail(habit_id: int, request: Request, month: str = "", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    habit = owned_habit(db, c.user.id, habit_id)
    year, mon = c.today.year, c.today.month
    if month:
        try:
            parsed = date.fromisoformat(f"{month}-01")
            year, mon = parsed.year, parsed.month
        except ValueError:
            pass
    first, last = month_bounds(date(year, mon, 1))
    prev_month = (first - timedelta(days=1)).strftime("%Y-%m")
    next_month = (last + timedelta(days=1)).strftime("%Y-%m")
    logs = sorted(habit.logs, key=lambda x: x.day, reverse=True)
    suggestions = list(
        db.scalars(
            select(Suggestion).where(Suggestion.habit_id == habit.id).order_by(Suggestion.created_at.desc(), Suggestion.id.desc()).limit(3)
        ).all()
    )
    return render(
        request,
        "habit_detail.html",
        c,
        habit=habit,
        stats=habitmath.habit_stats(habit, habit.logs, c.today),
        weeks=habitmath.calendar_weeks(habit, habit.logs, year, mon, c.today),
        month_label=f"{calendar.month_name[mon]} {year}",
        prev_month=prev_month,
        next_month=next_month,
        logs=logs[:20],
        checked_today=habitmath.log_map(habit.logs).get(c.today),
        suggestions=suggestions,
        today_scheduled=habitmath.scheduled(habit, c.today),
        coached=request.query_params.get("coached", ""),
    )


@router.post("/habits/{habit_id}/update")
def update_habit(
    habit_id: int,
    title: str = Form(""),
    intention: str = Form(""),
    cue: str = Form(""),
    days: list[str] = Form(default=[]),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    habit = owned_habit(db, c.user.id, habit_id)
    habit.title = _clean(title, "habit", 120, 2)
    habit.intention = _long(intention)
    habit.cue = _clean(cue, "cue", 160) if cue.strip() else ""
    habit.days = _days(days)
    db.commit()
    return see_other(f"/habits/{habit.id}?saved=1")


@router.post("/habits/{habit_id}/status")
def set_status(habit_id: int, status: str = Form(""), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    if status not in HABIT_STATUSES:
        raise HTTPException(422, "Unknown habit status.")
    habit = owned_habit(db, c.user.id, habit_id)
    habit.status = status
    habit.archived_at = utcnow() if status == "archived" else None
    db.commit()
    return see_other(f"/habits/{habit.id}")


@router.post("/habits/{habit_id}/delete")
def delete_habit(habit_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    habit = owned_habit(db, c.user.id, habit_id)
    db.delete(habit)
    db.commit()
    return see_other("/habits")


@router.post("/habits/{habit_id}/log")
def log_day(
    request: Request,
    habit_id: int,
    day: str = Form(""),
    status: str = Form("done"),
    note: str = Form(""),
    next: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    habit = owned_habit(db, c.user.id, habit_id)
    parsed_day = _parse_day(day, habit, c.today)
    existing = db.scalar(select(HabitLog).where(HabitLog.habit_id == habit.id, HabitLog.day == parsed_day))
    if status == "clear":
        if existing is not None:
            db.delete(existing)
    else:
        if status not in ("done", "skipped"):
            raise HTTPException(422, "Unknown log status.")
        if existing is None:
            db.add(
                HabitLog(
                    user_id=c.user.id,
                    habit_id=habit.id,
                    day=parsed_day,
                    status=status,
                    note=_long(note, 300),
                    created_at=utcnow(),
                )
            )
        else:
            existing.status = status
            existing.note = _long(note, 300)
    db.commit()
    fallback = f"/habits/{habit.id}"
    target = _safe_next(next, fallback)
    if is_htmx(request):
        from fastapi.responses import Response

        return Response(status_code=204, headers={"HX-Redirect": target})
    return see_other(target)


@router.post("/habits/{habit_id}/coach")
def run_coach(request: Request, habit_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    limiter = request.app.state.coach_limiter
    key = str(c.user.id)
    if limiter.blocked(key):
        raise HTTPException(429, "The coach is taking a short break. Try again in a few minutes.")
    limiter.hit(key)
    habit = owned_habit(db, c.user.id, habit_id)
    result = ai.suggest(request.app.state.settings, habit, habit.logs, c.today)
    for suggestion in result.suggestions:
        db.add(
            Suggestion(
                user_id=c.user.id,
                habit_id=habit.id,
                title=suggestion.title,
                rationale=suggestion.rationale,
                source=result.source,
                model=result.model,
                created_at=utcnow(),
            )
        )
    db.commit()
    source = "claude" if result.source == "claude" else "local"
    return see_other(f"/habits/{habit.id}?coached={source}")


@router.get("/week")
def week_page(request: Request, week: str = "", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    start = parse_week(week, c.today)
    habits = list(
        db.scalars(
            select(Habit)
            .where(Habit.user_id == c.user.id, Habit.status == "active")
            .options(selectinload(Habit.logs))
            .order_by(Habit.title)
        ).all()
    )
    logs_by_habit = _logs_map(habits)
    rows = habitmath.week_grid(habits, logs_by_habit, start, c.today)
    end = start + timedelta(days=6)
    report = habitmath.weekly_report(habits, logs_by_habit, [], start, c.today)
    stats = {habit.id: habitmath.range_stats(habit, logs_by_habit.get(habit.id, []), start, min(end, c.today), c.today) for habit in habits}
    return render(
        request,
        "week.html",
        c,
        week_start=start,
        week_label=week_label(start),
        prev_week=(start - timedelta(days=7)).isoformat(),
        next_week=(start + timedelta(days=7)).isoformat(),
        is_current=start == c.week_start,
        rows=rows,
        habits=habits,
        stats=stats,
        report=report,
        days=[start + timedelta(days=i) for i in range(7)],
    )
