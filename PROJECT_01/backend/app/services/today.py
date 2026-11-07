"""One consistent snapshot of "today" for the dashboard and the briefing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession

from ..models import DailyPriority, Email, Event, Reminder, Task, User
from ..routers.events import events_between
from ..routers.tasks import PRIORITY_RANK
from ..timeutil import day_bounds_utc, local_today
from .briefing import DayContext


@dataclass
class TodaySnapshot:
    day: date
    tz: ZoneInfo
    start_utc: datetime
    end_utc: datetime
    events: list[Event]
    overdue: list[Task]
    due_today: list[Task]
    upcoming: list[Task]
    reminders: list[Reminder]
    emails: list[Email]
    priorities: list[DailyPriority]
    done_today: int
    upcoming_count: int
    unread_emails: int


def take_snapshot(db: DbSession, user: User, tz: ZoneInfo) -> TodaySnapshot:
    day = local_today(tz)
    start, end = day_bounds_utc(day, tz)
    todo = select(Task).where(Task.user_id == user.id, Task.status == "todo")
    order = (Task.due_date, PRIORITY_RANK, Task.created_at)

    overdue = list(db.scalars(todo.where(Task.due_date < day).order_by(*order)))
    due_today = list(db.scalars(todo.where(Task.due_date == day).order_by(*order)))
    upcoming = list(
        db.scalars(
            todo.where(Task.due_date > day, Task.due_date <= day + timedelta(days=3)).order_by(*order)
        )
    )
    upcoming_count = db.scalar(
        select(func.count()).select_from(Task).where(
            Task.user_id == user.id, Task.status == "todo", Task.due_date > day
        )
    )
    done_today = db.scalar(
        select(func.count()).select_from(Task).where(
            Task.user_id == user.id,
            Task.status == "done",
            Task.completed_at >= start,
            Task.completed_at < end,
        )
    )
    reminders = list(
        db.scalars(
            select(Reminder)
            .where(
                Reminder.user_id == user.id,
                Reminder.status == "pending",
                Reminder.remind_at < end,
            )
            .order_by(Reminder.remind_at)
        )
    )
    emails = list(
        db.scalars(
            select(Email)
            .where(Email.user_id == user.id, or_(Email.is_unread, Email.is_flagged))
            .order_by(Email.is_flagged.desc(), Email.received_at.desc())
            .limit(50)
        )
    )
    unread = db.scalar(
        select(func.count()).select_from(Email).where(Email.user_id == user.id, Email.is_unread)
    )
    priorities = list(
        db.scalars(
            select(DailyPriority)
            .where(DailyPriority.user_id == user.id, DailyPriority.day == day)
            .order_by(DailyPriority.position)
        )
    )
    return TodaySnapshot(
        day=day,
        tz=tz,
        start_utc=start,
        end_utc=end,
        events=events_between(db, user, start, end),
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        reminders=reminders,
        emails=emails,
        priorities=priorities,
        done_today=done_today or 0,
        upcoming_count=upcoming_count or 0,
        unread_emails=unread or 0,
    )


def _hhmm(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%H:%M")


def to_day_context(snap: TodaySnapshot, now: datetime | None = None) -> DayContext:
    tz = snap.tz
    now = now or datetime.now(timezone.utc)

    def task_dict(t: Task) -> dict:
        return {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }

    events = []
    for e in snap.events:
        # Clip multi-day events to today so times read naturally.
        start = max(e.start_at, snap.start_utc)
        end = min(e.end_at, snap.end_utc - timedelta(minutes=1))
        events.append(
            {
                "title": e.title,
                "start": _hhmm(start, tz),
                "end": _hhmm(end, tz),
                "all_day": e.all_day,
                "location": e.location,
            }
        )
    return DayContext(
        day=snap.day,
        tz=tz,
        now_local=now.astimezone(tz),
        events=events,
        overdue=[task_dict(t) for t in snap.overdue[:15]],
        due_today=[task_dict(t) for t in snap.due_today[:15]],
        upcoming=[task_dict(t) for t in snap.upcoming[:10]],
        reminders=[{"text": r.text, "time": _hhmm(r.remind_at, tz)} for r in snap.reminders[:10]],
        emails=[
            {
                "from": m.from_name or m.from_addr,
                "subject": m.subject,
                "flagged": m.is_flagged,
                "unread": m.is_unread,
            }
            for m in snap.emails[:10]
        ],
        priorities=[{"text": p.text, "done": p.done} for p in snap.priorities],
    )
