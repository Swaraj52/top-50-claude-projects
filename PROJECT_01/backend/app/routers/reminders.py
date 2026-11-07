from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..deps import current_user, get_db, get_owned
from ..models import Reminder, Task, User
from ..schemas import ReminderIn, ReminderOut, ReminderPatch, SnoozeIn

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderOut])
def list_reminders(
    status_filter: Literal["pending", "all"] = Query("pending", alias="status"),
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    q = select(Reminder).where(Reminder.user_id == user.id)
    if status_filter == "pending":
        q = q.where(Reminder.status == "pending")
    return db.scalars(q.order_by(Reminder.remind_at).limit(500)).all()


@router.get("/due", response_model=list[ReminderOut])
def due_reminders(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    """Pending reminders whose time has come; the UI polls this to raise notifications."""
    return db.scalars(
        select(Reminder)
        .where(
            Reminder.user_id == user.id,
            Reminder.status == "pending",
            Reminder.remind_at <= utcnow(),
        )
        .order_by(Reminder.remind_at)
    ).all()


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
def create_reminder(
    body: ReminderIn, user: User = Depends(current_user), db: DbSession = Depends(get_db)
):
    if body.task_id is not None:
        get_owned(db, Task, body.task_id, user)
    reminder = Reminder(user_id=user.id, **body.model_dump())
    db.add(reminder)
    db.commit()
    return reminder


@router.patch("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: int,
    body: ReminderPatch,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    reminder = get_owned(db, Reminder, reminder_id, user)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(reminder, field, value)
    if body.remind_at is not None:
        reminder.status = "pending"
    db.commit()
    return reminder


@router.post("/{reminder_id}/snooze", response_model=ReminderOut)
def snooze(
    reminder_id: int,
    body: SnoozeIn,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    reminder = get_owned(db, Reminder, reminder_id, user)
    reminder.remind_at = utcnow() + timedelta(minutes=body.minutes)
    reminder.status = "pending"
    db.commit()
    return reminder


@router.post("/{reminder_id}/dismiss", response_model=ReminderOut)
def dismiss(reminder_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    reminder = get_owned(db, Reminder, reminder_id, user)
    reminder.status = "dismissed"
    db.commit()
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)
):
    db.delete(get_owned(db, Reminder, reminder_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
