"""Deterministic habit coach: small, realistic changes based on the actual logs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..models import Habit, HabitLog
from ..timeutil import parse_days
from . import habitmath


@dataclass
class Suggestion:
    title: str
    rationale: str


def rule_suggestions(habit: Habit, logs: list[HabitLog], today: date, limit: int = 3) -> list[Suggestion]:
    stats = habitmath.habit_stats(habit, logs, today)
    month = stats["month"]
    rate = month["rate"]
    days = parse_days(habit.days)
    out: list[Suggestion] = []

    def add(title: str, rationale: str) -> None:
        if all(s.title.lower() != title.lower() for s in out):
            out.append(Suggestion(title, rationale))

    if month["scheduled"] >= 4 and rate is not None and rate < 60:
        add(
            "Halve the ask on hard days",
            f"You completed {rate}% of decided days in the last four weeks. A 5-minute version counts; "
            "protecting the cue matters more than the volume right now.",
        )
        if len(days) >= 5:
            add(
                "Cut back to 3 days a week",
                f"You are scheduled {len(days)} days a week and missing often. Three reliable days build more "
                "trust than seven intentions.",
            )

    if not habit.cue.strip():
        add(
            "Anchor it to an existing routine",
            "This habit has no cue yet. Name the thing you already do right before it (after coffee, after "
            "brushing teeth, after logging off) so the decision is made once.",
        )

    if stats["streak"] >= 7:
        add(
            "Plan one deliberate rest day",
            f"Your current streak is {stats['streak']} scheduled days. A planned rest day protects the habit "
            "from an all-or-nothing crash.",
        )

    if month["missed"]:
        weekday = _weakest_weekday(habit, logs, today)
        if weekday is not None:
            add(
                f"Protect {weekday}",
                f"Most missed days cluster around {weekday}. Move the habit to a different time that day or "
                "shrink it in advance instead of negotiating at the last minute.",
            )

    if rate is not None and rate >= 80 and stats["streak"] >= 3:
        add(
            "Change one variable, not the whole habit",
            f"You are at {rate}% over four weeks. Keep the cue and add two minutes, one extra day, or a "
            "slightly harder version — one variable at a time.",
        )

    if month["skipped"] >= 3:
        add(
            "Make rest explicit",
            "Several days are marked as rest. Keep that, but write the rest day into the schedule so the "
            "calendar tells the truth.",
        )

    fallback = [
        Suggestion(
            "Keep the cue, shrink the first step",
            "Start with a two-minute version you cannot talk yourself out of. Consistency is built at the "
            "point where the habit starts, not where it ends.",
        ),
        Suggestion(
            "Review this habit on Sunday",
            "A five-minute weekly check is enough to notice drift. Look at the misses, change one thing, "
            "and leave the rest alone.",
        ),
        Suggestion(
            "Make the next rep visible",
            "Put the book, shoes or notebook where you will see it. Remove one point of friction before "
            "adding any ambition.",
        ),
    ]
    for item in fallback:
        if len(out) >= limit:
            break
        add(item.title, item.rationale)
    return out[:limit]


def _weakest_weekday(habit: Habit, logs: list[HabitLog], today: date) -> str | None:
    start = today - timedelta(days=27)
    by_day = habitmath.log_map(logs)
    counts = {i: {"scheduled": 0, "missed": 0} for i in range(7)}
    cursor = max(start, habit.created_at.date())
    while cursor <= today:
        if habitmath.scheduled(habit, cursor):
            counts[cursor.weekday()]["scheduled"] += 1
            if cursor not in by_day:
                counts[cursor.weekday()]["missed"] += 1
        cursor += timedelta(days=1)
    candidates = [(i, c) for i, c in counts.items() if c["missed"] >= 2]
    if not candidates:
        return None
    weekday = max(candidates, key=lambda item: (item[1]["missed"], -item[0]))[0]
    return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]

