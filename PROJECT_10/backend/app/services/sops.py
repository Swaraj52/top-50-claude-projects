"""SOP library arithmetic: review windows, completeness, codes and filtering.

Everything here is derived from stored rows. A review date is never stored as "due"; it is computed
from the last review and the cadence, so a handbook cannot go quietly stale.
"""

from __future__ import annotations

from datetime import date

from ..models import AREAS, SOP_STATUSES, Sop
from ..timeutil import add_months

AREA_PREFIX = {
    "sales": "SAL",
    "delivery": "DEL",
    "finance": "FIN",
    "people": "PEO",
    "operations": "OPS",
    "product": "PRO",
}

REVIEW_SOON_DAYS = 14


def next_review_on(sop: Sop) -> date:
    base = sop.last_reviewed_on or sop.created_at.date()
    return add_months(base, sop.review_months)


def review_state(sop: Sop, today: date) -> dict:
    """Where this SOP sits in its review window."""
    next_on = next_review_on(sop)
    days = (next_on - today).days
    if sop.status != "active":
        key, label = "inactive", "Not in force"
    elif sop.last_reviewed_on is None:
        key, label = "never", "Never reviewed"
    elif days < 0:
        key, label = "overdue", f"Review {abs(days)} days overdue"
    elif days <= REVIEW_SOON_DAYS:
        key, label = "soon", f"Review in {days} days"
    else:
        key, label = "current", "Review current"
    return {"key": key, "label": label, "next_on": next_on, "days": days}


def step_totals(sop: Sop) -> dict:
    steps = sorted(sop.steps, key=lambda step: (step.position, step.id))
    return {
        "count": len(steps),
        "minutes": sum(max(0, step.minutes) for step in steps),
        "roles": sorted({step.role for step in steps if step.role}),
        "steps": steps,
    }


def ready_to_activate(sop: Sop) -> tuple[bool, list[str]]:
    problems = []
    if len(sop.steps) == 0:
        problems.append("Add at least one step before activating.")
    if len((sop.purpose or "").strip()) < 20:
        problems.append("Write a purpose of at least 20 characters.")
    if sop.owner_id is None:
        problems.append("Give the process an owner.")
    return (not problems, problems)


def next_code(sops: list[Sop], area: str) -> str:
    prefix = AREA_PREFIX.get(area, "OPS")
    highest = 0
    for sop in sops:
        code = (sop.code or "").upper()
        if code.startswith(prefix + "-"):
            tail = code[len(prefix) + 1 :]
            if tail.isdigit():
                highest = max(highest, int(tail))
    return f"{prefix}-{highest + 1:02d}"


def filtered(
    sops: list[Sop],
    q: str = "",
    status: str = "",
    area: str = "",
    owner_id: int | None = None,
    attention: bool = False,
    today: date | None = None,
) -> list[Sop]:
    text = q.strip().lower()
    rows = []
    for sop in sops:
        if status and sop.status != status:
            continue
        if status == "" and sop.status == "retired":
            continue
        if area and sop.area != area:
            continue
        if owner_id is not None and sop.owner_id != owner_id:
            continue
        if attention and today is not None:
            state = review_state(sop, today)["key"]
            if sop.status != "active" or state in ("current", "inactive"):
                continue
        if text:
            haystack = " ".join(
                [
                    sop.code,
                    sop.title,
                    sop.purpose,
                    sop.scope,
                    sop.area,
                    sop.owner.name if sop.owner else "",
                    " ".join(step.title for step in sop.steps),
                ]
            ).lower()
            if text not in haystack:
                continue
        rows.append(sop)
    return sorted(rows, key=lambda s: (s.status != "active", s.code, s.title))


def counts(sops: list[Sop], today: date) -> dict:
    by_status = {key: 0 for key in SOP_STATUSES}
    for sop in sops:
        by_status[sop.status] = by_status.get(sop.status, 0) + 1
    active = [sop for sop in sops if sop.status == "active"]
    return {
        "total": len(sops),
        "by_status": by_status,
        "active": len(active),
        "draft": by_status.get("draft", 0),
        "retired": by_status.get("retired", 0),
        "unowned": sum(1 for sop in active if sop.owner_id is None),
        "no_steps": sum(1 for sop in active if not sop.steps),
        "review_due": sum(
            1 for sop in active if review_state(sop, today)["key"] in ("overdue", "never")
        ),
    }
