"""Weekly plan: the week's actions, grouped by goal, with carry-over."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..models import Goal, WeeklyAction
from ..services import goalmath
from ..timeutil import parse_week, week_label
from ..web import Ctx, csrf, ctx, get_db, is_htmx, render, see_other

router = APIRouter()


def _safe_next(value: str, fallback: str) -> str:
    value = (value or "").strip()
    return value if value.startswith("/") and not value.startswith("//") else fallback


def _action(db: DbSession, user_id: int, action_id: int) -> WeeklyAction:
    action = db.scalar(select(WeeklyAction).where(WeeklyAction.id == action_id, WeeklyAction.user_id == user_id))
    if action is None:
        raise HTTPException(404, "That action doesn't exist.")
    return action


def _parse_monday(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value) - timedelta(days=date.fromisoformat(value).weekday())
    except (ValueError, TypeError):
        return fallback


@router.get("/weekly")
def weekly_page(request: Request, week: str = "", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    start = parse_week(week, c.today)
    actions = goalmath.week_actions(db, c.user.id, start)
    goals = list(db.scalars(select(Goal).where(Goal.user_id == c.user.id, Goal.status.in_(("active", "paused"))).order_by(Goal.title)).all())
    grouped: dict[int, list[WeeklyAction]] = {}
    for action in actions:
        grouped.setdefault(action.goal_id, []).append(action)
    goal_map = {g.id: g for g in goals}
    for action in actions:
        goal_map.setdefault(action.goal_id, action.goal)
    return render(
        request,
        "weekly.html",
        c,
        week_start=start,
        week_label=week_label(start),
        prev_week=(start - timedelta(days=7)).isoformat(),
        next_week=(start + timedelta(days=7)).isoformat(),
        is_current=start == c.week_start,
        actions=actions,
        grouped=grouped,
        goals=goals,
        goal_map=goal_map,
        stats=goalmath.week_stats(actions),
        capacity=c.user.weekly_capacity_min,
        carried=int(request.query_params.get("carried", "0") or 0),
    )


@router.post("/weekly/actions")
def create_action(
    title: str = Form(""),
    goal_id: int = Form(0),
    milestone_id: str = Form(""),
    estimate_min: int = Form(45),
    week_start: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    title = " ".join(title.split())
    if not 3 <= len(title) <= 200:
        raise HTTPException(422, "Give the action a title of 3-200 characters.")
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == c.user.id))
    if goal is None:
        raise HTTPException(404, "Choose one of your goals.")
    milestone_pk = None
    if (milestone_id or "").strip():
        try:
            milestone_pk = int(milestone_id)
        except ValueError:
            milestone_pk = None
        if milestone_pk and not any(m.id == milestone_pk for m in goal.milestones):
            raise HTTPException(422, "That milestone doesn't belong to the chosen goal.")
    start = _parse_monday(week_start, c.week_start)
    db.add(
        WeeklyAction(
            user_id=c.user.id,
            goal_id=goal.id,
            milestone_id=milestone_pk,
            title=title,
            estimate_min=max(5, min(600, int(estimate_min))),
            week_start=start,
            source="manual",
        )
    )
    db.commit()
    return see_other(f"/weekly?week={start.isoformat()}")


@router.post("/weekly/actions/{action_id}/toggle")
def toggle_action(
    request: Request,
    action_id: int,
    next: str = Form("/weekly"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    action = _action(db, c.user.id, action_id)
    if action.status == "done":
        action.status, action.done_at = "open", None
    else:
        action.status, action.done_at = "done", utcnow()
    db.commit()
    if is_htmx(request):
        return render(request, "partials/action_row.html", c, action=action, next_url=_safe_next(next, "/weekly"))
    return see_other(_safe_next(next, "/weekly"))


@router.post("/weekly/actions/{action_id}/delete")
def delete_action(action_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    action = _action(db, c.user.id, action_id)
    week = action.week_start
    db.delete(action)
    db.commit()
    return see_other(f"/weekly?week={week.isoformat()}")


@router.post("/weekly/carry")
def carry_open(week_start: str = Form(""), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    """Carry last week's unfinished actions into this week (copying, with no duplicates)."""
    start = _parse_monday(week_start, c.week_start)
    previous = start - timedelta(days=7)
    old = list(db.scalars(select(WeeklyAction).where(WeeklyAction.user_id == c.user.id, WeeklyAction.week_start == previous, WeeklyAction.status == "open")).all())
    existing_titles = {
        a.title.strip().lower()
        for a in db.scalars(select(WeeklyAction).where(WeeklyAction.user_id == c.user.id, WeeklyAction.week_start == start)).all()
    }
    created = 0
    for action in old:
        if action.title.strip().lower() in existing_titles:
            continue
        db.add(
            WeeklyAction(
                user_id=c.user.id,
                goal_id=action.goal_id,
                milestone_id=action.milestone_id,
                title=action.title,
                estimate_min=action.estimate_min,
                week_start=start,
                source="manual",
            )
        )
        existing_titles.add(action.title.strip().lower())
        created += 1
    db.commit()
    return see_other(f"/weekly?week={start.isoformat()}&carried={created}")
