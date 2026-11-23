"""One dashboard view assembled from the library, the runs and the ownership tracker."""

from __future__ import annotations

from datetime import date

from ..models import Person, Run, Sop
from . import ownership as ownership_service
from . import runs as run_service
from . import sops as sop_service


def dashboard(sops: list[Sop], runs: list[Run], people: list[Person], today: date) -> dict:
    counts = sop_service.counts(sops, today)
    run_summary = run_service.summary(runs, today)
    cover = ownership_service.coverage(people, sops, today)

    active = [sop for sop in sops if sop.status == "active"]
    review_due = []
    for sop in active:
        state = sop_service.review_state(sop, today)
        if state["key"] in ("overdue", "never", "soon"):
            review_due.append({"sop": sop, "state": state})
    review_due.sort(key=lambda row: (row["state"]["days"], row["sop"].code))

    no_steps = [sop for sop in active if not sop.steps]
    attention = []
    if cover["unowned_count"]:
        attention.append(
            {
                "key": "unowned",
                "title": f"{cover['unowned_count']} active process{'es' if cover['unowned_count'] != 1 else ''} with no owner",
                "detail": "An unowned process is nobody's job until something breaks.",
                "href": "/ownership",
                "action": "Assign owners",
            }
        )
    overdue_reviews = [row for row in review_due if row["state"]["key"] in ("overdue", "never")]
    if overdue_reviews:
        attention.append(
            {
                "key": "review",
                "title": f"{len(overdue_reviews)} process{'es' if len(overdue_reviews) != 1 else ''} past review",
                "detail": "A process that has not been read in its review window may not match reality.",
                "href": "/sops?attention=1",
                "action": "Review the library",
            }
        )
    if run_summary["overdue"]:
        attention.append(
            {
                "key": "runs",
                "title": f"{run_summary['overdue']} checklist{'s' if run_summary['overdue'] != 1 else ''} overdue",
                "detail": "Open runs past their due date are the cheapest thing to fix today.",
                "href": "/runs",
                "action": "Open the runs",
            }
        )
    if no_steps:
        attention.append(
            {
                "key": "steps",
                "title": f"{len(no_steps)} active process{'es' if len(no_steps) != 1 else ''} with no steps",
                "detail": "An active SOP without steps cannot be handed over or run.",
                "href": "/sops?status=active",
                "action": "Add steps",
            }
        )

    recent = sorted(
        [run for run in runs if run.status in ("done", "abandoned")],
        key=lambda run: (run.completed_at or run.created_at, run.id),
        reverse=True,
    )[:5]

    return {
        "counts": counts,
        "runs": run_summary,
        "cover": cover,
        "review_due": review_due[:6],
        "attention": attention[:4],
        "recent": recent,
        "open_runs": run_summary["open"][:5],
    }
