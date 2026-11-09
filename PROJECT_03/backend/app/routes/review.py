"""The end-of-day review: triage, generate (Claude or rules), commit tomorrow's plan."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import anthropic
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Review, Task
from ..services import planner, reviewer
from ..services.ai import AIError
from ..services.day import recurring_blockers, snapshot
from ..web import Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()
log = logging.getLogger(__name__)


def ai_client(request: Request) -> anthropic.Anthropic | None:
    """The Anthropic client, or None without a key. Overridden in tests."""
    settings = request.app.state.settings
    if not settings.ai_enabled:
        return None
    if getattr(request.app.state, "anthropic_client", None) is None:
        request.app.state.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0, max_retries=2)
    return request.app.state.anthropic_client


@router.get("/review")
def review_page(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    snap = snapshot(db, c.user, c.today, c.tz)
    return render(request, "review.html", c, snap=snap, tomorrow=c.today + timedelta(days=1), recurring=recurring_blockers(db, c.user, c.today))


@router.post("/review/generate")
async def generate(request: Request, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db), client: anthropic.Anthropic | None = Depends(ai_client)):
    form = await request.form()
    limiter = request.app.state.review_limiter
    if limiter.blocked(str(c.user.id)):
        raise HTTPException(429, "A review was just written. Wait a few seconds before regenerating.")
    limiter.hit(str(c.user.id))

    snap = snapshot(db, c.user, c.today, c.tz)
    tomorrow = c.today + timedelta(days=1)
    decisions = {}
    for t in snap.open_today:
        raw = str(form.get(f"decision_{t.id}", "carry"))
        if raw == "later":  # works without JavaScript: the date comes from its own field
            raw = str(form.get(f"later_{t.id}", ""))
        decisions[t.id] = planner.parse_decision(raw, tomorrow)
    cands = planner.candidates(db, c.user, tomorrow, decisions)
    recurring = recurring_blockers(db, c.user, c.today)
    plan, load, over = planner.build_plan(cands, snap.capacity_min, tomorrow)
    all_scored, _, _ = planner.build_plan(cands, 10**6, tomorrow)  # every candidate, scored, for the AI to choose from
    carried = [t.id for t in snap.open_today if decisions.get(t.id) == "carry"]

    source, model, note = "rule", None, None
    content = reviewer.rule_review(snap, plan, recurring, len(carried))
    if client is not None:
        try:
            ai_content, order = reviewer.ai_review(snap, all_scored, recurring, client, request.app.state.settings.anthropic_model)
            plan, load, over = planner.build_plan(cands, snap.capacity_min, tomorrow, preferred_order=order)
            content, source, model = ai_content, "ai", request.app.state.settings.anthropic_model
        except AIError as exc:
            log.warning("AI review failed for user %s: %s", c.user.id, exc)
            note = f"AI review unavailable: {exc}. Showing the rule-based review instead."

    review = snap.review or Review(user_id=c.user.id, day=c.today)
    applied = (snap.review.plan or {}).get("applied_carry_ids", []) if snap.review else []
    if snap.review is None:
        db.add(review)
    review.source, review.model, review.note, review.content = source, model, note, content
    review.plan = {
        "decisions": {str(k): (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in decisions.items()},
        "items": [p.as_dict() for p in plan],
        "load_min": load,
        "capacity_min": snap.capacity_min,
        "over_capacity": over,
        "carried_ids": carried,
        "applied_carry_ids": applied,
    }
    review.committed = False
    db.commit()
    return see_other("/review#plan")


@router.post("/review/commit")
def commit(request: Request, notes: str = Form(""), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    review = db.scalar(select(Review).where(Review.user_id == c.user.id, Review.day == c.today))
    if review is None:
        raise HTTPException(409, "Write the review first.")
    tomorrow = c.today + timedelta(days=1)
    plan = dict(review.plan or {})
    applied = set(plan.get("applied_carry_ids", []))  # carry counts are bumped once per day, even on re-commit
    for tid_str, decision in (plan.get("decisions") or {}).items():
        task = db.get(Task, int(tid_str))
        if task is None or task.user_id != c.user.id or task.status in ("done", "dropped"):
            continue
        if decision == "drop":
            task.status = "dropped"
            continue
        parsed = planner.parse_decision(decision, c.today)
        task.planned_for = parsed if isinstance(parsed, date) else tomorrow
        if decision == "carry" and task.id in plan.get("carried_ids", []) and task.id not in applied:
            task.carry_count += 1
            applied.add(task.id)
    for item in plan.get("items", []):
        task = db.get(Task, item["task_id"])
        if task is not None and task.user_id == c.user.id and task.status in ("todo", "doing"):
            task.planned_for = tomorrow
    plan["applied_carry_ids"] = sorted(applied)
    review.plan = plan
    review.notes = notes.strip()[:2000]
    review.committed = True
    db.commit()
    return see_other("/review?committed=1")
