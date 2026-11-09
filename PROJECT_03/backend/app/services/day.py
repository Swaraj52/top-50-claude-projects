"""A consistent snapshot of one local day for the Today page and the review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from ..models import Blocker, Checkin, LogEntry, Review, Task, User
from ..timeutil import day_bounds_utc

OPEN = ("todo", "doing")


@dataclass
class DaySnapshot:
    day: date
    done: list[Task]
    open_today: list[Task]
    backlog: list[Task]
    upcoming: list[Task]
    log: list[LogEntry]
    blockers_open: list[Blocker]
    blockers_resolved_today: list[Blocker]
    checkin: Checkin | None
    review: Review | None
    capacity_min: int

    @property
    def done_minutes(self) -> int:
        return sum(t.estimate_min for t in self.done) + sum(e.minutes or 0 for e in self.log if e.kind == "done")

    def entries(self, kind: str) -> list[LogEntry]:
        return [e for e in self.log if e.kind == kind]


def snapshot(db: DbSession, user: User, day: date, tz: ZoneInfo) -> DaySnapshot:
    start, end = day_bounds_utc(day, tz)
    mine = select(Task).where(Task.user_id == user.id)
    order = (Task.priority, Task.created_at)
    return DaySnapshot(
        day=day,
        done=list(db.scalars(mine.where(Task.status == "done", Task.completed_at >= start, Task.completed_at < end).order_by(Task.completed_at))),
        open_today=list(db.scalars(mine.where(Task.status.in_(OPEN), Task.planned_for <= day).order_by(Task.status.desc(), *order))),
        backlog=list(db.scalars(mine.where(Task.status.in_(OPEN), Task.planned_for.is_(None)).order_by(*order))),
        upcoming=list(
            db.scalars(
                mine.where(Task.status.in_(OPEN), Task.planned_for > day, Task.planned_for <= day + timedelta(days=7)).order_by(Task.planned_for, *order)
            )
        ),
        log=list(db.scalars(select(LogEntry).where(LogEntry.user_id == user.id, LogEntry.day == day).order_by(LogEntry.created_at))),
        blockers_open=list(
            db.scalars(select(Blocker).where(Blocker.user_id == user.id, Blocker.resolved_on.is_(None)).order_by(Blocker.opened_on))
        ),
        blockers_resolved_today=list(
            db.scalars(select(Blocker).where(Blocker.user_id == user.id, Blocker.resolved_on == day))
        ),
        checkin=db.scalar(select(Checkin).where(Checkin.user_id == user.id, Checkin.day == day)),
        review=db.scalar(select(Review).where(Review.user_id == user.id, Review.day == day)),
        capacity_min=int(round(user.capacity_hours * 60)),
    )


def recurring_blockers(db: DbSession, user: User, today: date, window: int = 14) -> list[str]:
    """Blocker themes seen on 2+ separate occasions recently, or open for more than 3 days."""

    def key(text: str) -> str:
        words = "".join(ch.lower() if ch.isalnum() or ch == " " else " " for ch in text).split()
        return " ".join(words[:4])

    recent = list(
        db.scalars(
            select(Blocker).where(
                Blocker.user_id == user.id,
                or_(Blocker.opened_on >= today - timedelta(days=window), Blocker.resolved_on.is_(None)),
            )
        )
    )
    counts: dict[str, list[Blocker]] = {}
    for b in recent:
        counts.setdefault(key(b.text), []).append(b)
    out = []
    for group in counts.values():
        latest = max(group, key=lambda b: b.opened_on)
        if len(group) >= 2:
            out.append(f"“{latest.text}” has come up {len(group)} times in {window} days")
        elif latest.resolved_on is None and (today - latest.opened_on).days > 3:
            out.append(f"“{latest.text}” has been open for {(today - latest.opened_on).days} days")
    return out
