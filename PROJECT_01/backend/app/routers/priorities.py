from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..deps import current_user, get_db, get_owned, user_zone
from ..models import DailyPriority, Task, User
from ..schemas import PrioritiesPut, PriorityOut, PriorityPatch
from ..timeutil import local_today

router = APIRouter(prefix="/priorities", tags=["priorities"])


def _for_day(db: DbSession, user: User, day: date) -> list[DailyPriority]:
    return list(
        db.scalars(
            select(DailyPriority)
            .where(DailyPriority.user_id == user.id, DailyPriority.day == day)
            .order_by(DailyPriority.position)
        )
    )


@router.get("", response_model=list[PriorityOut])
def get_priorities(
    day: date | None = None,
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
):
    return _for_day(db, user, day or local_today(tz))


@router.put("", response_model=list[PriorityOut])
def set_priorities(body: PrioritiesPut, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    """Replace the day's priorities (max three, kept in the given order)."""
    for item in body.items:
        if item.task_id is not None:
            get_owned(db, Task, item.task_id, user)
    db.execute(delete(DailyPriority).where(DailyPriority.user_id == user.id, DailyPriority.day == body.day))
    db.flush()
    db.add_all(
        DailyPriority(
            user_id=user.id,
            day=body.day,
            position=i,
            text=item.text.strip(),
            task_id=item.task_id,
            done=item.done,
        )
        for i, item in enumerate(body.items, start=1)
    )
    db.commit()
    return _for_day(db, user, body.day)


@router.patch("/{priority_id}", response_model=PriorityOut)
def update_priority(
    priority_id: int,
    body: PriorityPatch,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    priority = get_owned(db, DailyPriority, priority_id, user)
    if body.text is not None:
        priority.text = body.text.strip() or priority.text
    if body.done is not None:
        priority.done = body.done
        # Finishing a priority that points at a task finishes the task too.
        if body.done and priority.task_id is not None:
            task = db.get(Task, priority.task_id)
            if task is not None and task.status != "done":
                task.status = "done"
                task.completed_at = utcnow()
    db.commit()
    return priority
