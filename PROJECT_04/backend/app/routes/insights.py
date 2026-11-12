"""Insights: weekly completion, confidence, category balance and goal health."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..models import Goal
from ..services import charts, goalmath
from ..web import Ctx, ctx, get_db, render

router = APIRouter()


@router.get("/insights")
def insights(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    goals = list(
        db.scalars(select(Goal).where(Goal.user_id == c.user.id).options(selectinload(Goal.milestones)).order_by(Goal.created_at)).all()
    )
    active = [g for g in goals if g.status == "active"]
    series = goalmath.weekly_series(db, c.user.id, c.today, 8)
    confidence = goalmath.confidence_series(db, c.user.id, c.today, 8)
    rates = [
        round(100 * d / t) if t else None
        for d, t in zip(series["done"], series["total"])
    ]
    figures = {
        "volume": charts.bar_chart(series["labels"], [float(v) for v in series["done"]], title="Completed actions per week"),
        "rate": charts.bar_chart(series["labels"], [float(v or 0) for v in rates], title="Completion rate per week", unit="%"),
        "confidence": charts.line_chart(confidence["labels"], confidence["values"], title="Average weekly confidence (1-5)"),
    }
    total_actions = sum(series["done"])
    avg_rate = round(sum(r for r in rates if r is not None) / len([r for r in rates if r is not None])) if any(r is not None for r in rates) else 0
    return render(
        request,
        "insights.html",
        c,
        figures=figures,
        series=series,
        confidence=confidence,
        categories=goalmath.category_summary(goals),
        health=goalmath.health_rows(goals, c.today),
        total_actions=total_actions,
        avg_rate=avg_rate,
        active_count=len(active),
    )


@router.get("/goals/{goal_id}/review")
def goal_review(goal_id: int, request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    """A printable one-goal review: state, pace, milestones and recent check-ins."""
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == c.user.id).options(selectinload(Goal.milestones)))
    if goal is None:
        raise HTTPException(404, "That goal doesn't exist.")
    actions = goalmath.week_actions(db, c.user.id, c.week_start)
    return render(
        request,
        "goal_review.html",
        c,
        goal=goal,
        progress=goalmath.progress(goal),
        pace=goalmath.pace(goal, c.today),
        actions=[a for a in actions if a.goal_id == goal.id],
        checkins=sorted(goal.checkins, key=lambda x: x.day, reverse=True)[:8],
    )
