"""Dashboard (home), goal CRUD, milestones, check-ins and the coach."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..db import utcnow
from ..models import GOAL_CATEGORIES, GOAL_STATUSES, Checkin, Goal, Milestone, WeeklyAction
from ..services import ai, goalmath
from ..timeutil import parse_week, week_label
from ..web import Ctx, csrf, ctx, get_db, is_htmx, render, see_other

router = APIRouter()
CATEGORY_LABELS = {
    "career": "Career",
    "health": "Health",
    "learning": "Learning",
    "finance": "Finance",
    "personal": "Personal",
    "creative": "Creative",
}


def _goals(db: DbSession, user_id: int, status: str | None = None) -> list[Goal]:
    stmt = select(Goal).where(Goal.user_id == user_id).options(selectinload(Goal.milestones)).order_by(Goal.created_at.desc())
    if status and status in GOAL_STATUSES:
        stmt = stmt.where(Goal.status == status)
    return list(db.scalars(stmt).all())


def owned_goal(db: DbSession, user_id: int, goal_id: int) -> Goal:
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id).options(selectinload(Goal.milestones)))
    if goal is None:
        raise HTTPException(404, "That goal doesn't exist.")
    return goal


def _clean_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(422, "Use a valid date.") from exc


def _clean_text(value: str, field: str, limit: int, minimum: int = 0) -> str:
    value = " ".join((value or "").split())
    if len(value) < minimum:
        raise HTTPException(422, f"Please add a {field}.")
    if len(value) > limit:
        raise HTTPException(422, f"The {field} is too long (max {limit} characters).")
    return value


def _clean_long(value: str, limit: int = 4000) -> str:
    return (value or "").strip()[:limit]


@router.get("/")
def dashboard(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    goals = _goals(db, c.user.id)
    active = [g for g in goals if g.status == "active"]
    actions = goalmath.week_actions(db, c.user.id, c.week_start)
    stats = goalmath.week_stats(actions)
    streak = goalmath.checkin_streak(db, c.user.id, c.today)
    health = goalmath.health_rows(goals, c.today)
    at_risk = [row for row in health if row["at_risk"]]
    goals_by_id = {g.id: g for g in goals}
    series = goalmath.weekly_series(db, c.user.id, c.today, 6)
    avg = round(sum(goalmath.progress(g) for g in active) / len(active)) if active else 0
    return render(
        request,
        "dashboard.html",
        c,
        goals=active,
        health=health,
        at_risk=at_risk,
        week_actions=actions,
        week_stats=stats,
        week_label=week_label(c.week_start),
        streak=streak,
        avg_progress=avg,
        goals_by_id=goals_by_id,
        series=series,
        categories=CATEGORY_LABELS,
        planned=int(request.query_params.get("planned", "0") or 0),
        coach_source=request.query_params.get("source", ""),
    )


@router.get("/goals")
def goals_page(
    request: Request,
    status: str = "active",
    category: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    status = status if status in (*GOAL_STATUSES, "all") else "active"
    goals = _goals(db, c.user.id, None if status == "all" else status)
    if category in GOAL_CATEGORIES:
        goals = [g for g in goals if g.category == category]
    rows = [{"goal": g, "progress": goalmath.progress(g), "next": goalmath.next_milestone(g), "pace": goalmath.pace(g, c.today)} for g in goals]
    counts = {s: sum(1 for g in _goals(db, c.user.id) if g.status == s) for s in GOAL_STATUSES}
    return render(request, "goals.html", c, rows=rows, current_status=status, category=category, counts=counts, categories=CATEGORY_LABELS)


@router.post("/goals")
def create_goal(
    title: str = Form(""),
    description: str = Form(""),
    why: str = Form(""),
    category: str = Form("personal"),
    target_date: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    title = _clean_text(title, "goal title", 160, 3)
    if category not in GOAL_CATEGORIES:
        raise HTTPException(422, "Choose a valid category.")
    goal = Goal(
        user_id=c.user.id,
        title=title,
        description=_clean_long(description),
        why=_clean_long(why, 1200),
        category=category,
        target_date=_clean_date(target_date),
    )
    db.add(goal)
    db.commit()
    return see_other(f"/goals/{goal.id}")


@router.get("/goals/{goal_id}")
def goal_detail(request: Request, goal_id: int, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    goal = owned_goal(db, c.user.id, goal_id)
    actions = list(
        db.scalars(select(WeeklyAction).where(WeeklyAction.goal_id == goal.id, WeeklyAction.week_start == c.week_start).order_by(WeeklyAction.status, WeeklyAction.id)).all()
    )
    checkins = list(db.scalars(select(Checkin).where(Checkin.goal_id == goal.id).order_by(Checkin.day.desc()).limit(12)).all())
    return render(
        request,
        "goal_detail.html",
        c,
        goal=goal,
        progress=goalmath.progress(goal),
        pace=goalmath.pace(goal, c.today),
        next_ms=goalmath.next_milestone(goal),
        actions=actions,
        checkins=checkins,
        week_label=week_label(c.week_start),
        categories=CATEGORY_LABELS,
        planned=int(request.query_params.get("planned", "0") or 0),
        coach_source=request.query_params.get("source", ""),
        saved=bool(request.query_params.get("saved")),
    )


@router.post("/goals/{goal_id}/update")
def update_goal(
    goal_id: int,
    title: str = Form(""),
    description: str = Form(""),
    why: str = Form(""),
    category: str = Form("personal"),
    target_date: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    goal = owned_goal(db, c.user.id, goal_id)
    if category not in GOAL_CATEGORIES:
        raise HTTPException(422, "Choose a valid category.")
    goal.title = _clean_text(title, "goal title", 160, 3)
    goal.description = _clean_long(description)
    goal.why = _clean_long(why, 1200)
    goal.category = category
    goal.target_date = _clean_date(target_date)
    db.commit()
    return see_other(f"/goals/{goal.id}?saved=1")


@router.post("/goals/{goal_id}/status")
def set_status(goal_id: int, status: str = Form(""), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    if status not in GOAL_STATUSES:
        raise HTTPException(422, "Unknown goal status.")
    goal = owned_goal(db, c.user.id, goal_id)
    goal.status = status
    goal.achieved_at = utcnow() if status == "achieved" else None
    db.commit()
    return see_other(f"/goals/{goal.id}")


@router.post("/goals/{goal_id}/delete")
def delete_goal(goal_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    goal = owned_goal(db, c.user.id, goal_id)
    db.delete(goal)
    db.commit()
    return see_other("/goals")


@router.post("/goals/{goal_id}/milestones")
def add_milestone(
    goal_id: int,
    title: str = Form(""),
    detail: str = Form(""),
    due_date: str = Form(""),
    weight: int = Form(1),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    goal = owned_goal(db, c.user.id, goal_id)
    weight = max(1, min(5, int(weight)))
    position = max([m.position for m in goal.milestones] or [0]) + 1
    db.add(
        Milestone(
            goal_id=goal.id,
            title=_clean_text(title, "milestone", 160, 2),
            detail=_clean_long(detail, 1000),
            due_date=_clean_date(due_date),
            weight=weight,
            position=position,
        )
    )
    db.commit()
    return see_other(f"/goals/{goal.id}")


@router.post("/milestones/{milestone_id}/toggle")
def toggle_milestone(milestone_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    milestone = db.scalar(select(Milestone).where(Milestone.id == milestone_id).join(Goal).where(Goal.user_id == c.user.id))
    if milestone is None:
        raise HTTPException(404, "That milestone doesn't exist.")
    milestone.status = "open" if milestone.status == "done" else "done"
    milestone.completed_at = utcnow() if milestone.status == "done" else None
    db.commit()
    return see_other(f"/goals/{milestone.goal_id}")


@router.post("/milestones/{milestone_id}/delete")
def delete_milestone(milestone_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    milestone = db.scalar(select(Milestone).where(Milestone.id == milestone_id).join(Goal).where(Goal.user_id == c.user.id))
    if milestone is None:
        raise HTTPException(404, "That milestone doesn't exist.")
    goal_id = milestone.goal_id
    db.delete(milestone)
    db.commit()
    return see_other(f"/goals/{goal_id}")


@router.post("/goals/{goal_id}/checkins")
def add_checkin(
    goal_id: int,
    confidence: int = Form(3),
    note: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    goal = owned_goal(db, c.user.id, goal_id)
    confidence = max(1, min(5, int(confidence)))
    note = _clean_long(note, 500)
    checkin = db.scalar(select(Checkin).where(Checkin.goal_id == goal.id, Checkin.day == c.today))
    if checkin is None:
        db.add(Checkin(user_id=c.user.id, goal_id=goal.id, day=c.today, confidence=confidence, note=note))
    else:
        checkin.confidence, checkin.note = confidence, note
    db.commit()
    return see_other(f"/goals/{goal.id}")


@router.post("/goals/{goal_id}/coach")
def run_coach(request: Request, goal_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    """Ask the coach for a plan and file the accepted actions into this week."""
    limiter = request.app.state.coach_limiter
    key = str(c.user.id)
    if limiter.blocked(key):
        raise HTTPException(429, "The coach is taking a short break. Try again in a few minutes.")
    limiter.hit(key)

    goal = owned_goal(db, c.user.id, goal_id)
    checkins = list(db.scalars(select(Checkin).where(Checkin.goal_id == goal.id).order_by(Checkin.day.desc()).limit(8)).all())
    result = ai.plan(request.app.state.settings, goal, goal.milestones, checkins, c.today, c.week_start)
    for suggestion in result.suggestions:
        milestone = next((m for m in goal.milestones if m.id == suggestion.milestone_id), None)
        db.add(
            WeeklyAction(
                user_id=c.user.id,
                goal_id=goal.id,
                milestone_id=milestone.id if milestone else None,
                title=suggestion.title,
                estimate_min=suggestion.estimate_min,
                week_start=c.week_start,
                source="coach",
            )
        )
    db.commit()
    source = "claude" if result.source == "claude" else "local"
    if is_htmx(request):
        # The client reloads the goal page to show the new actions.
        from fastapi.responses import Response

        return Response(status_code=204, headers={"HX-Redirect": f"/goals/{goal.id}?planned={len(result.suggestions)}&source={source}"})
    return see_other(f"/goals/{goal.id}?planned={len(result.suggestions)}&source={source}")
