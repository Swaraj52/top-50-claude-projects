"""The goal coach: a small, deterministic weekly planner used with or without an LLM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..models import Checkin, Goal, Milestone
from . import goalmath


@dataclass
class Suggestion:
    title: str
    rationale: str
    estimate_min: int = 45
    milestone_id: int | None = None


def _estimate(weight: int) -> int:
    return {1: 30, 2: 45, 3: 45, 4: 60, 5: 90}.get(weight, 45)


def rule_plan(
    goal: Goal,
    milestones: list[Milestone],
    checkins: list[Checkin],
    today: date,
    week_start: date,
) -> list[Suggestion]:
    """Build 3-5 concrete actions for the given week from the goal's real state."""
    open_items = sorted(
        [m for m in milestones if m.status != "done"],
        key=lambda m: (m.due_date is None, m.due_date or date.max, m.position, m.id),
    )
    latest = max(checkins, key=lambda c: (c.day, c.id)) if checkins else None
    pace = goalmath.pace(goal, today)
    suggestions: list[Suggestion] = []

    if not open_items:
        suggestions.extend(
            [
                Suggestion(
                    "Define what 'done' looks like in one sentence",
                    "This goal has no open milestones, so progress can't be measured yet. A crisp definition of done unlocks the rest of the plan.",
                    20,
                ),
                Suggestion(
                    "Break the goal into three milestones",
                    "Three checkpoints give you a pace to manage instead of one distant finish line.",
                    30,
                ),
            ]
        )

    for milestone in open_items[:2]:
        due = f" (due {milestone.due_date:%d %b})" if milestone.due_date else ""
        suggestions.append(
            Suggestion(
                f"Advance: {milestone.title}",
                f"The nearest open milestone{due}. Block one focused session and finish the smallest useful piece of it.",
                _estimate(milestone.weight),
                milestone.id,
            )
        )

    if pace["state"] in ("behind", "overdue"):
        days = pace["days_left"]
        timing = "the target date has passed" if pace["state"] == "overdue" else f"{days} days remain"
        suggestions.append(
            Suggestion(
                "Choose scope over speed",
                f"You are behind the straight-line pace and {timing}. Pick the one milestone that matters most this week and postpone the rest deliberately.",
                30,
            )
        )
    elif pace["state"] == "ahead":
        suggestions.append(
            Suggestion(
                "Raise the bar for one milestone",
                "You are ahead of pace. Use the margin to make one milestone noticeably stronger rather than adding new work.",
                30,
            )
        )

    if latest and latest.confidence <= 2:
        suggestions.append(
            Suggestion(
                "Do a 10-minute reset on this goal",
                f"Your last check-in rated confidence {latest.confidence}/5. A tiny, visible step is a better fix than a bigger plan.",
                10,
            )
        )
    elif latest is None:
        suggestions.append(
            Suggestion(
                "Write an honest first check-in",
                "There is no check-in yet. Rate your confidence and note what is actually in the way; the plan adapts to it.",
                5,
            )
        )

    if not suggestions:
        suggestions.append(
            Suggestion(
                "Review the goal and pick one next step",
                "Everything on record is on track. Keep the weekly rhythm with one deliberate step.",
                30,
            )
        )

    # Keep the list short and the titles unique.
    seen: set[str] = set()
    unique: list[Suggestion] = []
    for s in suggestions:
        key = s.title.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique[:5]


def next_week_anchor(today: date, week_start: date) -> date:
    """The week coach suggestions are filed to: always the current (or next) week."""
    return week_start if today <= week_start + timedelta(days=6) else week_start + timedelta(days=7)
