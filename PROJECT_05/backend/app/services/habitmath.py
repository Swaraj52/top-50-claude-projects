"""Habit mathematics: schedules, streaks, calendars, weekly stats and reports."""

from __future__ import annotations

from datetime import date, timedelta

from ..models import Habit, HabitLog, Reflection
from ..timeutil import month_grid, parse_days

PROMPTS = [
    {
        "worked": "What felt easy or surprisingly good this week?",
        "friction": "Where did the plan meet real life?",
        "change": "What is one small adjustment for next week?",
    },
    {
        "worked": "Which habit gave you energy back?",
        "friction": "Which cue or time of day failed you?",
        "change": "What would make the hardest habit 10% easier?",
    },
    {
        "worked": "What did you protect time for?",
        "friction": "What got in the way most often?",
        "change": "What will you deliberately drop or shrink next week?",
    },
    {
        "worked": "Where did consistency feel automatic?",
        "friction": "Which day was the honest warning sign?",
        "change": "What is the smallest version you could keep on a bad day?",
    },
]


def scheduled(habit: Habit, day: date) -> bool:
    return day.weekday() in parse_days(habit.days)


def log_map(logs: list[HabitLog]) -> dict[date, HabitLog]:
    return {log.day: log for log in logs}


def streak(habit: Habit, logs: list[HabitLog], today: date) -> int:
    """Consecutive scheduled days completed. Explicit rest days are neutral, misses break it.

    If today is scheduled but not logged yet, the streak is measured up to yesterday so an
    unchecked morning does not look like a failure.
    """
    created = habit.created_at.date()
    by_day = log_map(logs)
    cursor = today
    if scheduled(habit, cursor) and cursor not in by_day:
        cursor -= timedelta(days=1)
    count = 0
    while cursor >= created:
        if scheduled(habit, cursor):
            log = by_day.get(cursor)
            if log is None:
                break
            if log.status == "done":
                count += 1
        cursor -= timedelta(days=1)
    return count


def longest_streak(habit: Habit, logs: list[HabitLog], today: date) -> int:
    created = habit.created_at.date()
    by_day = log_map(logs)
    best = 0
    current = 0
    cursor = created
    while cursor <= today:
        if scheduled(habit, cursor):
            log = by_day.get(cursor)
            if log is None:
                current = 0
            elif log.status == "done":
                current += 1
                best = max(best, current)
            # skipped: neutral, keeps the run alive without adding to it
        cursor += timedelta(days=1)
    return best


def range_stats(habit: Habit, logs: list[HabitLog], start: date, end: date, today: date) -> dict:
    first = max(start, habit.created_at.date())
    last = min(end, today)
    by_day = log_map(logs)
    scheduled_count = done = skipped = missed = 0
    cursor = first
    while cursor <= last:
        if scheduled(habit, cursor):
            scheduled_count += 1
            log = by_day.get(cursor)
            if log is None:
                # Today is still open: an unchecked morning is not a failure.
                if cursor != today:
                    missed += 1
            elif log.status == "done":
                done += 1
            else:
                skipped += 1
        cursor += timedelta(days=1)
    decided = done + missed
    return {
        "scheduled": scheduled_count,
        "done": done,
        "skipped": skipped,
        "missed": missed,
        "rate": round(100 * done / decided) if decided else None,
    }


def habit_stats(habit: Habit, logs: list[HabitLog], today: date) -> dict:
    week = range_stats(habit, logs, today - timedelta(days=6), today, today)
    month = range_stats(habit, logs, today - timedelta(days=27), today, today)
    return {
        "streak": streak(habit, logs, today),
        "longest": longest_streak(habit, logs, today),
        "week": week,
        "month": month,
        "at_risk": bool(month["scheduled"] >= 4 and month["rate"] is not None and month["rate"] < 60),
    }


def calendar_status(habit: Habit, logs: list[HabitLog], day: date, today: date) -> str:
    if not scheduled(habit, day):
        return "off"
    if day > today:
        return "future"
    log = log_map(logs).get(day)
    if log is not None:
        return log.status
    if day == today:
        return "pending"
    return "missed"


def calendar_weeks(habit: Habit, logs: list[HabitLog], year: int, month: int, today: date) -> list[list[dict | None]]:
    weeks = []
    for week in month_grid(year, month):
        row = []
        for day in week:
            if day is None:
                row.append(None)
            else:
                row.append({"day": day, "status": calendar_status(habit, logs, day, today), "today": day == today})
        weeks.append(row)
    return weeks


def week_grid(habits: list[Habit], logs_by_habit: dict[int, list[HabitLog]], start: date, today: date) -> list[dict]:
    rows = []
    for habit in habits:
        cells = []
        for offset in range(7):
            day = start + timedelta(days=offset)
            status = calendar_status(habit, logs_by_habit.get(habit.id, []), day, today)
            cells.append({"day": day, "status": status, "today": day == today})
        rows.append({"habit": habit, "cells": cells})
    return rows


def weekly_series(habits: list[Habit], logs_by_habit: dict[int, list[HabitLog]], today: date, weeks: int = 8) -> dict:
    this_monday = today - timedelta(days=today.weekday())
    starts = [this_monday - timedelta(days=7 * i) for i in range(weeks - 1, -1, -1)]
    labels, done, scheduled_counts = [], [], []
    for start in starts:
        end = min(start + timedelta(days=6), today)
        d = s = 0
        for habit in habits:
            stats = range_stats(habit, logs_by_habit.get(habit.id, []), start, end, today)
            d += stats["done"]
            s += stats["done"] + stats["missed"]
        labels.append(f"{start.day} {start:%b}")
        done.append(d)
        scheduled_counts.append(s)
    return {"labels": labels, "done": done, "scheduled": scheduled_counts, "starts": starts}


def weekday_pattern(habits: list[Habit], logs_by_habit: dict[int, list[HabitLog]], today: date, weeks: int = 8) -> list[dict]:
    start = today - timedelta(days=today.weekday()) - timedelta(days=7 * (weeks - 1))
    totals = {i: {"scheduled": 0, "done": 0} for i in range(7)}
    for habit in habits:
        for offset in range((today - start).days + 1):
            day = start + timedelta(days=offset)
            if day > today or day < habit.created_at.date() or not scheduled(habit, day):
                continue
            totals[day.weekday()]["scheduled"] += 1
            log = log_map(logs_by_habit.get(habit.id, [])).get(day)
            if log is not None and log.status == "done":
                totals[day.weekday()]["done"] += 1
    return [
        {
            "weekday": i,
            "scheduled": totals[i]["scheduled"],
            "done": totals[i]["done"],
            "rate": round(100 * totals[i]["done"] / totals[i]["scheduled"]) if totals[i]["scheduled"] else None,
        }
        for i in range(7)
    ]


def habit_consistency(habits: list[Habit], logs_by_habit: dict[int, list[HabitLog]], today: date) -> list[dict]:
    rows = []
    for habit in habits:
        stats = range_stats(habit, logs_by_habit.get(habit.id, []), today - timedelta(days=27), today, today)
        rows.append({"habit": habit, "stats": stats, "streak": streak(habit, logs_by_habit.get(habit.id, []), today)})
    rows.sort(key=lambda r: (r["stats"]["rate"] is None, r["stats"]["rate"] or 0))
    return rows


def reflection_prompts(day: date) -> dict:
    return PROMPTS[day.isocalendar().week % len(PROMPTS)]


def reflection_streak(reflections: list[Reflection], today: date) -> int:
    weeks = {r.week_start for r in reflections}
    cursor = today - timedelta(days=today.weekday())
    if cursor not in weeks:
        cursor -= timedelta(days=7)
    count = 0
    while cursor in weeks:
        count += 1
        cursor -= timedelta(days=7)
    return count


def weekly_report(habits: list[Habit], logs_by_habit: dict[int, list[HabitLog]], reflections: list[Reflection], start: date, today: date) -> dict:
    end = start + timedelta(days=6)
    per_habit = []
    totals = {"scheduled": 0, "done": 0, "missed": 0, "skipped": 0}
    for habit in habits:
        stats = range_stats(habit, logs_by_habit.get(habit.id, []), start, end, today)
        for key in totals:
            totals[key] += stats[key]
        per_habit.append({"habit": habit, "stats": stats})

    rated = [row for row in per_habit if row["stats"]["done"] + row["stats"]["missed"] > 0]
    best = max(rated, key=lambda r: r["stats"]["rate"] or 0, default=None)
    worst = min(rated, key=lambda r: r["stats"]["rate"] or 0, default=None)

    by_weekday = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        if day > today:
            continue
        done = scheduled_count = 0
        for habit in habits:
            if day < habit.created_at.date() or not scheduled(habit, day):
                continue
            scheduled_count += 1
            log = log_map(logs_by_habit.get(habit.id, [])).get(day)
            if log is not None and log.status == "done":
                done += 1
        if scheduled_count:
            by_weekday.append({"day": day, "done": done, "scheduled": scheduled_count})
    best_day = max(by_weekday, key=lambda d: (d["done"] / d["scheduled"], -d["day"].weekday()), default=None)
    decided = totals["done"] + totals["missed"]
    rate = round(100 * totals["done"] / decided) if decided else None

    reflection = next((r for r in reflections if r.week_start == start), None)
    lines = []
    if decided:
        lines.append(f"You completed {totals['done']} of {decided} decided habit days ({rate}%).")
    else:
        lines.append("No habit days were scheduled this week yet.")
    if best and best["stats"]["scheduled"]:
        lines.append(f"Strongest routine: {best['habit'].title} ({best['stats']['done']}/{best['stats']['done'] + best['stats']['missed']}).")
    if worst and worst is not best and worst["stats"]["scheduled"]:
        lines.append(f"Needs a smaller ask: {worst['habit'].title} ({worst['stats']['done']}/{worst['stats']['done'] + worst['stats']['missed']}).")
    if best_day:
        lines.append(f"Best day: {best_day['day']:%A} ({best_day['done']}/{best_day['scheduled']}).")
    if reflection:
        lines.append("Your reflection is saved; the adjustment you chose is the plan for next week.")

    return {
        "start": start,
        "end": end,
        "totals": totals,
        "rate": rate,
        "per_habit": per_habit,
        "best": best,
        "worst": worst,
        "best_day": best_day,
        "reflection": reflection,
        "lines": lines,
    }
