"""Checklist runs: progress, due state and starting a run from a published SOP."""

from __future__ import annotations

from datetime import date, timedelta

from ..db import utcnow
from ..models import RUN_STATUSES, Run, RunItem, Sop

CADENCE_DAYS = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90, "ad_hoc": None}


def started_items(run: Run) -> list[RunItem]:
    return sorted(run.items, key=lambda item: (item.position, item.id))


def progress(run: Run) -> dict:
    items = started_items(run)
    total = len(items)
    done = sum(1 for item in items if item.done)
    return {
        "total": total,
        "done": done,
        "open": total - done,
        "percent": round(done / total * 100) if total else 0,
        "complete": total > 0 and done == total,
    }


def due_state(run: Run, today: date) -> dict:
    if run.status != "open":
        return {"key": run.status, "label": run.status.title(), "days": None}
    if run.due_on is None:
        return {"key": "no_due", "label": "No due date", "days": None}
    days = (run.due_on - today).days
    if days < 0:
        return {"key": "overdue", "label": f"{abs(days)} days overdue", "days": days}
    if days == 0:
        return {"key": "today", "label": "Due today", "days": 0}
    if days <= 2:
        return {"key": "soon", "label": f"Due in {days} days", "days": days}
    return {"key": "scheduled", "label": f"Due in {days} days", "days": days}


def derive_due(sop: Sop, today: date) -> date | None:
    days = CADENCE_DAYS.get(sop.cadence)
    return today + timedelta(days=days) if days else None


def start(sop: Sop, today: date, owner_id: int | None = None, due_on: date | None = None) -> Run:
    steps = sorted(sop.steps, key=lambda step: (step.position, step.id))
    if not steps:
        raise ValueError("This SOP has no steps to run.")
    run = Run(
        sop_id=sop.id,
        owner_id=owner_id if owner_id is not None else sop.owner_id,
        started_on=today,
        due_on=due_on if due_on is not None else derive_due(sop, today),
        status="open",
    )
    for step in steps:
        run.items.append(
            RunItem(
                position=step.position,
                title=step.title,
                detail=step.detail,
                role=step.role,
            )
        )
    return run


def toggle(item: RunItem, done: bool | None = None) -> None:
    item.done = (not item.done) if done is None else done
    item.done_at = utcnow() if item.done else None


def complete(run: Run) -> None:
    if progress(run)["complete"] is False:
        raise ValueError("Finish every item before completing the run.")
    run.status = "done"
    run.completed_at = utcnow()


def abandon(run: Run) -> None:
    run.status = "abandoned"
    run.completed_at = utcnow()


def summary(runs: list[Run], today: date) -> dict:
    open_runs = [run for run in runs if run.status == "open"]
    rows = [
        {
            "run": run,
            "progress": progress(run),
            "due": due_state(run, today),
        }
        for run in open_runs
    ]
    rows.sort(key=lambda row: (row["due"]["days"] is None, row["due"]["days"] or 10**9, row["run"].id))
    by_status = {key: 0 for key in RUN_STATUSES}
    for run in runs:
        by_status[run.status] = by_status.get(run.status, 0) + 1
    return {
        "total": len(runs),
        "open": rows,
        "open_count": len(open_runs),
        "overdue": sum(1 for row in rows if row["due"]["key"] == "overdue"),
        "done": by_status.get("done", 0),
        "abandoned": by_status.get("abandoned", 0),
        "by_status": by_status,
    }
