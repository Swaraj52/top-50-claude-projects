from __future__ import annotations

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..deps import current_user, get_db, user_zone
from ..models import Briefing, CalendarSource, EmailAccount, User
from ..schemas import BriefingOut, DashboardCounts, DashboardOut, EmailOut, PriorityOut, ReminderOut, TaskOut
from ..services.today import take_snapshot
from .events import to_out

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def latest_briefing(db: DbSession, user: User, day) -> Briefing | None:
    return db.scalar(
        select(Briefing)
        .where(Briefing.user_id == user.id, Briefing.day == day)
        .order_by(Briefing.created_at.desc(), Briefing.id.desc())
        .limit(1)
    )


@router.get("/today", response_model=DashboardOut)
def today(
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
):
    snap = take_snapshot(db, user, tz)
    briefing = latest_briefing(db, user, snap.day)
    calendars = db.scalar(
        select(func.count()).select_from(CalendarSource).where(CalendarSource.user_id == user.id)
    )
    email_connected = db.scalar(select(EmailAccount.id).where(EmailAccount.user_id == user.id)) is not None
    return DashboardOut(
        date=snap.day,
        timezone=user.timezone,
        user_name=user.name,
        events=[to_out(e) for e in snap.events],
        tasks=[TaskOut.model_validate(t) for t in snap.overdue + snap.due_today],
        reminders=[ReminderOut.model_validate(r) for r in snap.reminders],
        priorities=[PriorityOut.model_validate(p) for p in snap.priorities],
        emails=[EmailOut.model_validate(e) for e in snap.emails[:6]],
        email_connected=email_connected,
        calendars_connected=calendars or 0,
        counts=DashboardCounts(
            overdue=len(snap.overdue),
            due_today=len(snap.due_today),
            done_today=snap.done_today,
            upcoming=snap.upcoming_count,
            events_today=len(snap.events),
            unread_emails=snap.unread_emails,
            attention_emails=len(snap.emails),
        ),
        briefing=BriefingOut.model_validate(briefing) if briefing else None,
    )
