"""Goal mathematics: weighted progress, pace, momentum and trend series."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..models import Checkin, Goal, Milestone, WeeklyAction
from ..timeutil import monday_of


def progress(goal: Goal) -> int:
    """Weighted completion of a goal's milestones (0-100)."""
    total = sum(m.weight for m in goal.milestones)
    if not total:
        return 0
    done = sum(m.weight for m in goal.milestones if m.status == "done")
    return round(100 * done / total)


def next_milestone(goal: Goal) -> Milestone | None:
    open_items = [m for m in goal.milestones if m.status != "done"]
    if not open_items:
        return None
    return sorted(open_items, key=lambda m: (m.due_date is None, m.due_date or date.max, m.position, m.id))[0]


def days_left(goal: Goal, today: date) -> int | None:
    return (goal.target_date - today).days if goal.target_date else None


def pace(goal: Goal, today: date) -> dict:
    """Compare actual progress with the straight-line pace to the target date."""
    actual = progress(goal)
    result = {"state": "no-date", "actual": actual, "expected": None, "delta": None, "days_left": None, "needs_milestones": not goal.milestones}
    if goal.status != "active":
        result["state"] = "closed"
        return result
    left = days_left(goal, today)
    result["days_left"] = left
    if goal.target_date is None:
        return result
    start = goal.created_at.date()
    total_days = max(1, (goal.target_date - start).days)
    elapsed = (today - start).days
    expected = max(0, min(100, round(100 * elapsed / total_days)))
    result["expected"] = expected
    result["delta"] = actual - expected
    if goal.target_date < today and actual < 100:
        result["state"] = "overdue"
    elif result["needs_milestones"]:
        result["state"] = "setup"
    elif actual - expected >= 10:
        result["state"] = "ahead"
    elif actual - expected >= -10:
        result["state"] = "on-track"
    else:
        result["state"] = "behind"
    return result


def is_at_risk(goal: Goal, today: date) -> bool:
    if goal.status != "active":
        return False
    p = pace(goal, today)
    if p["state"] in ("overdue", "behind"):
        return True
    left = p["days_left"]
    return left is not None and 0 <= left <= 21 and p["actual"] < 60


def momentum(actions: list[WeeklyAction]) -> int | None:
    """Share of decided actions that were completed (skipped actions don't count)."""
    decided = [a for a in actions if a.status in ("done", "open")]
    if not decided:
        return None
    return round(100 * sum(1 for a in decided if a.status == "done") / len(decided))


def checkin_streak(db: DbSession, user_id: int, today: date) -> int:
    """Consecutive days with at least one goal check-in, ending today or yesterday."""
    days = set(db.scalars(select(Checkin.day).where(Checkin.user_id == user_id)).all())
    if not days:
        return 0
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def week_actions(db: DbSession, user_id: int, week_start: date) -> list[WeeklyAction]:
    return list(
        db.scalars(
            select(WeeklyAction)
            .where(WeeklyAction.user_id == user_id, WeeklyAction.week_start == week_start)
            .order_by(WeeklyAction.status, WeeklyAction.goal_id, WeeklyAction.id)
        ).all()
    )


def week_stats(actions: list[WeeklyAction]) -> dict:
    planned = [a for a in actions if a.status != "skipped"]
    done = [a for a in planned if a.status == "done"]
    return {
        "total": len(planned),
        "done": len(done),
        "open": len(planned) - len(done),
        "minutes": sum(a.estimate_min for a in planned),
        "done_minutes": sum(a.estimate_min for a in done),
        "rate": round(100 * len(done) / len(planned)) if planned else 0,
    }


def weekly_series(db: DbSession, user_id: int, today: date, weeks: int = 8) -> dict:
    """Completion per week for the last `weeks` weeks (oldest first)."""
    this_monday = monday_of(today)
    starts = [this_monday - timedelta(days=7 * i) for i in range(weeks - 1, -1, -1)]
    rows = db.execute(
        select(WeeklyAction.week_start, WeeklyAction.status, func.count(WeeklyAction.id))
        .where(WeeklyAction.user_id == user_id, WeeklyAction.week_start >= starts[0])
        .group_by(WeeklyAction.week_start, WeeklyAction.status)
    ).all()
    counts: dict[date, dict[str, int]] = {}
    for week, status, n in rows:
        counts.setdefault(week, {})[status] = n
    labels, done, total = [], [], []
    for start in starts:
        c = counts.get(start, {})
        d = c.get("done", 0)
        t = d + c.get("open", 0)
        labels.append(f"{start.day} {start:%b}")
        done.append(d)
        total.append(t)
    return {"labels": labels, "done": done, "total": total, "starts": starts}


def confidence_series(db: DbSession, user_id: int, today: date, weeks: int = 8) -> dict:
    start = monday_of(today) - timedelta(days=7 * (weeks - 1))
    rows = db.execute(
        select(Checkin.day, Checkin.confidence).where(Checkin.user_id == user_id, Checkin.day >= start)
    ).all()
    buckets: list[list[int]] = [[] for _ in range(weeks)]
    for day, confidence in rows:
        idx = (monday_of(day) - start).days // 7
        if 0 <= idx < weeks:
            buckets[idx].append(confidence)
    labels = [f"{(start + timedelta(days=7 * i)).day} {(start + timedelta(days=7 * i)):%b}" for i in range(weeks)]
    values = [round(sum(b) / len(b), 2) if b else None for b in buckets]
    counts = [len(b) for b in buckets]
    return {"labels": labels, "values": values, "counts": counts}


def category_summary(goals: list[Goal]) -> list[dict]:
    groups: dict[str, list[Goal]] = {}
    for goal in goals:
        groups.setdefault(goal.category, []).append(goal)
    out = []
    for category, items in sorted(groups.items()):
        out.append(
            {
                "category": category,
                "count": len(items),
                "progress": round(sum(progress(g) for g in items) / len(items)) if items else 0,
            }
        )
    return out


def health_rows(goals: list[Goal], today: date) -> list[dict]:
    rows = []
    for goal in goals:
        if goal.status != "active":
            continue
        p = pace(goal, today)
        rows.append({"goal": goal, "progress": progress(goal), "pace": p, "at_risk": is_at_risk(goal, today), "next": next_milestone(goal)})
    rows.sort(key=lambda r: (not r["at_risk"], r["pace"]["days_left"] is None, r["pace"]["days_left"] or 9999))
    return rows
