from __future__ import annotations

from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import case, select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..deps import current_user, get_db, get_owned, user_zone
from ..models import Task, User
from ..schemas import TaskIn, TaskOut, TaskPatch
from ..timeutil import local_today

router = APIRouter(prefix="/tasks", tags=["tasks"])

View = Literal["today", "overdue", "upcoming", "all", "done"]

PRIORITY_RANK = case(
    {"high": 0, "medium": 1, "low": 2}, value=Task.priority, else_=3
)


def task_query(user: User, view: View, tz: ZoneInfo):
    today = local_today(tz)
    q = select(Task).where(Task.user_id == user.id)
    if view == "done":
        return q.where(Task.status == "done").order_by(Task.completed_at.desc()).limit(200)
    q = q.where(Task.status == "todo")
    if view == "today":
        q = q.where(Task.due_date == today)
    elif view == "overdue":
        q = q.where(Task.due_date < today)
    elif view == "upcoming":
        q = q.where(Task.due_date > today)
    # Dated tasks first by date, undated last; then priority, then newest.
    return q.order_by(
        Task.due_date.is_(None), Task.due_date, PRIORITY_RANK, Task.created_at.desc()
    )


@router.get("", response_model=list[TaskOut])
def list_tasks(
    view: View = "all",
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
):
    return db.scalars(task_query(user, view, tz)).all()


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskIn, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    task = Task(user_id=user.id, **body.model_dump())
    db.add(task)
    db.commit()
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    body: TaskPatch,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    task = get_owned(db, Task, task_id, user)
    changes = body.model_dump(exclude_unset=True)
    for field in ("title", "notes", "priority", "status"):
        if changes.get(field) is None:
            changes.pop(field, None)
    if "title" in changes:
        changes["title"] = changes["title"].strip() or task.title
    if "status" in changes and changes["status"] != task.status:
        task.completed_at = utcnow() if changes["status"] == "done" else None
    for field, value in changes.items():
        setattr(task, field, value)
    db.commit()
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    db.delete(get_owned(db, Task, task_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
