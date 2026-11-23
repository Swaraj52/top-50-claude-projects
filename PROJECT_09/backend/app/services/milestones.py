"""Milestones: horizon groups, roll-up progress and honest overdue handling.

A milestone is overdue when it is not done and its due date has passed. That is derived on every
read rather than stored, so a plan cannot quietly go stale.
"""

from __future__ import annotations

from datetime import date

from ..models import (
    MILESTONE_HORIZON_LABELS,
    MILESTONE_HORIZONS,
    MILESTONE_STATUS_LABELS,
    Milestone,
)


def visible_status(milestone: Milestone, today: date) -> str:
    if milestone.status == "done":
        return "done"
    if milestone.due_date is not None and milestone.due_date < today:
        return "overdue"
    return milestone.status


def status_label(value: str) -> str:
    return MILESTONE_STATUS_LABELS.get(value, value.replace("_", " ").title())


def sort_key(milestone: Milestone):
    return (milestone.due_date is None, milestone.due_date or date.max, milestone.sort_order, milestone.id)


def groups(milestones: list[Milestone], today: date) -> list[dict]:
    rows = []
    for horizon in MILESTONE_HORIZONS:
        items = sorted([m for m in milestones if m.horizon == horizon], key=sort_key)
        rows.append(
            {
                "key": horizon,
                "label": MILESTONE_HORIZON_LABELS[horizon],
                "items": items,
                "done": sum(1 for m in items if m.status == "done"),
                "total": len(items),
            }
        )
    return rows


def board(milestones: list[Milestone], today: date) -> list[dict]:
    """Horizon columns with each milestone's derived status, ready for the page."""
    rows = []
    for horizon in MILESTONE_HORIZONS:
        items = sorted([m for m in milestones if m.horizon == horizon], key=sort_key)
        cards = []
        for milestone in items:
            key = visible_status(milestone, today)
            cards.append(
                {
                    "m": milestone,
                    "status": key,
                    "label": status_label(key),
                    "days": (milestone.due_date - today).days if milestone.due_date else None,
                }
            )
        rows.append(
            {
                "key": horizon,
                "label": MILESTONE_HORIZON_LABELS[horizon],
                "cards": cards,
                "done": sum(1 for m in items if m.status == "done"),
                "total": len(items),
            }
        )
    return rows


def summary(milestones: list[Milestone], today: date) -> dict:
    done = [m for m in milestones if m.status == "done"]
    open_items = [m for m in milestones if m.status != "done"]
    overdue = [m for m in open_items if m.due_date is not None and m.due_date < today]
    upcoming = sorted(
        [m for m in open_items if m.due_date is not None and m.due_date >= today], key=sort_key
    )
    undated = [m for m in open_items if m.due_date is None]
    next_due = (upcoming or undated or [None])[0]
    total = len(milestones)
    return {
        "total": total,
        "done": len(done),
        "open": len(open_items),
        "overdue": overdue,
        "overdue_count": len(overdue),
        "next_due": next_due,
        "progress": round(len(done) / total * 100) if total else 0,
        "groups": groups(milestones, today),
        "by_status": {
            status: sum(1 for m in milestones if visible_status(m, today) == status)
            for status in ("planned", "in_progress", "at_risk", "done", "overdue")
        },
    }
