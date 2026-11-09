"""Deterministic tomorrow planner: score candidate tasks, fill up to the user's capacity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from ..models import Task, User

PRIORITY_POINTS = {1: 30, 2: 15, 3: 5}


@dataclass
class PlanItem:
    task_id: int
    title: str
    estimate_min: int
    score: float
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"task_id": self.task_id, "title": self.title, "estimate_min": self.estimate_min, "reasons": self.reasons}


def parse_decision(value: str, today: date) -> str | date:
    """'carry' / 'drop' / an ISO date later than tomorrow (anything else means carry)."""
    if value in ("carry", "drop"):
        return value
    try:
        d = date.fromisoformat(value)
    except ValueError:
        return "carry"
    return d if d > today else "carry"


def candidates(db: DbSession, user: User, tomorrow: date, decisions: dict[int, str | date]) -> list[Task]:
    rows = db.scalars(
        select(Task).where(
            Task.user_id == user.id,
            Task.status.in_(("todo", "doing")),
            or_(Task.planned_for.is_(None), Task.planned_for <= tomorrow, Task.due_date <= tomorrow),
        )
    )
    return [t for t in rows if decisions.get(t.id, "carry") == "carry"]


def score(task: Task, tomorrow: date, now: datetime | None = None) -> tuple[float, list[str]]:
    now = now or datetime.now(timezone.utc)
    points = float(PRIORITY_POINTS.get(task.priority, 10))
    reasons = [f"Priority {task.priority}"]
    if task.due_date is not None:
        if task.due_date < tomorrow:
            late = (tomorrow - task.due_date).days
            points += 12 + 6 * min(late, 5)
            reasons.append(f"overdue by {late} day{'s' if late != 1 else ''}")
        elif task.due_date == tomorrow:
            points += 12
            reasons.append("due tomorrow")
    if task.status == "doing":
        points += 8
        reasons.append("already in progress")
    if task.carry_count:
        points += min(task.carry_count * 4, 20)
        reasons.append(f"carried over {task.carry_count}×")
    age_days = max(0, (now - task.created_at).days)
    points += min(age_days * 0.5, 7)
    if task.planned_for is None:
        points -= 5  # backlog items yield to things already scheduled
    return points, reasons


def build_plan(
    tasks: list[Task], capacity_min: int, tomorrow: date, preferred_order: list[int] | None = None, now: datetime | None = None
) -> tuple[list[PlanItem], int, bool]:
    """Greedy fill to capacity. Returns (items, load_minutes, over_capacity)."""
    scored = {t.id: PlanItem(t.id, t.title, t.estimate_min or 30, *score(t, tomorrow, now)) for t in tasks}
    order = sorted(scored.values(), key=lambda p: (-p.score, p.task_id))
    if preferred_order:
        first = [scored[i] for i in preferred_order if i in scored]
        order = first + [p for p in order if p.task_id not in set(preferred_order)]
    items, load = [], 0
    for item in order:
        if load + item.estimate_min <= capacity_min:
            items.append(item)
            load += item.estimate_min
    over = False
    if not items and order:  # one task bigger than the whole day: still plan it, flagged
        items, load, over = [order[0]], order[0].estimate_min, True
    return items, load, over
