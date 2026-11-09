"""Weekly trends: per-day series and totals, in the user's local days."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Blocker, Checkin, LogEntry, Review, Task, User
from ..timeutil import day_bounds_utc


@dataclass
class Trends:
    days: list[date]
    labels: list[str]
    completed: list[int]
    carried: list[int]
    focus: list[float | None]
    energy: list[float | None]
    mood: list[float | None]
    blockers_opened: list[int]
    blockers_resolved: list[int]
    area_minutes: list[tuple[str, int]] = field(default_factory=list)
    streak: int = 0

    @property
    def total_completed(self) -> int:
        return sum(self.completed)

    @property
    def total_carried(self) -> int:
        return sum(self.carried)

    @property
    def completion_rate(self) -> int | None:
        total = self.total_completed + self.total_carried
        return round(100 * self.total_completed / total) if total else None

    @property
    def avg_focus(self) -> float | None:
        vals = [v for v in self.focus if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    @property
    def avg_energy(self) -> float | None:
        vals = [v for v in self.energy if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    @property
    def best_day(self) -> str | None:
        if not any(self.completed):
            return None
        i = max(range(len(self.completed)), key=lambda k: (self.completed[k], k))
        return self.labels[i]


def review_streak(db: DbSession, user: User, tz: ZoneInfo, today: date, horizon: int = 90) -> int:
    """Consecutive days ending yesterday (or today, once committed) with a committed review.

    Rest days, with no tasks finished, nothing logged and no check-in, don't break the streak.
    """
    since = today - timedelta(days=horizon)
    start, _ = day_bounds_utc(since, tz)
    committed = {r.day for r in db.scalars(select(Review).where(Review.user_id == user.id, Review.committed, Review.day >= since))}
    active = {t.completed_at.astimezone(tz).date() for t in db.scalars(select(Task).where(Task.user_id == user.id, Task.completed_at >= start))}
    active |= set(db.scalars(select(LogEntry.day).where(LogEntry.user_id == user.id, LogEntry.day >= since)))
    active |= set(db.scalars(select(Checkin.day).where(Checkin.user_id == user.id, Checkin.day >= since)))
    streak, d = 0, today if today in committed else today - timedelta(days=1)
    while d >= since:
        if d in committed:
            streak += 1
        elif d in active:
            break
        d -= timedelta(days=1)
    return streak


def compute(db: DbSession, user: User, tz: ZoneInfo, today: date, span: int = 7) -> Trends:
    days = [today - timedelta(days=span - 1 - i) for i in range(span)]
    first_start, _ = day_bounds_utc(days[0], tz)
    _, last_end = day_bounds_utc(days[-1], tz)

    done = list(
        db.scalars(
            select(Task).where(Task.user_id == user.id, Task.status == "done", Task.completed_at >= first_start, Task.completed_at < last_end)
        )
    )
    completed = Counter(t.completed_at.astimezone(tz).date() for t in done)
    areas = Counter()
    for t in done:
        areas[t.area or "unsorted"] += t.estimate_min or 0

    reviews = {r.day: r for r in db.scalars(select(Review).where(Review.user_id == user.id, Review.day >= days[0], Review.day <= today))}
    checkins = {c.day: c for c in db.scalars(select(Checkin).where(Checkin.user_id == user.id, Checkin.day >= days[0], Checkin.day <= today))}
    blockers = list(db.scalars(select(Blocker).where(Blocker.user_id == user.id)))

    streak = review_streak(db, user, tz, today)

    return Trends(
        days=days,
        labels=[f"{d:%a} {d.day}" for d in days],
        completed=[completed.get(d, 0) for d in days],
        carried=[len((reviews[d].plan or {}).get("carried_ids", [])) if d in reviews and reviews[d].committed else 0 for d in days],
        focus=[checkins[d].focus_hours if d in checkins else None for d in days],
        energy=[float(checkins[d].energy) if d in checkins else None for d in days],
        mood=[float(checkins[d].mood) if d in checkins else None for d in days],
        blockers_opened=[sum(1 for b in blockers if b.opened_on == d) for d in days],
        blockers_resolved=[sum(1 for b in blockers if b.resolved_on == d) for d in days],
        area_minutes=areas.most_common(6),
        streak=streak,
    )
