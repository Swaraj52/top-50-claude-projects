"""Today: tasks, work log, blockers and the check-in. HTMX gets fragments, plain forms redirect."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..models import LOG_KINDS, Blocker, Checkin, LogEntry, Task
from ..services.day import snapshot
from ..web import Ctx, csrf, ctx, get_db, is_htmx, render, see_other

router = APIRouter()


def _owned(db: DbSession, model, obj_id: int, c: Ctx):
    obj = db.get(model, obj_id)
    if obj is None or obj.user_id != c.user.id:
        raise HTTPException(404, "Not found")
    return obj


def _fragment(request: Request, db: DbSession, c: Ctx, partial: str):
    """After a change: HTMX swaps the section; a plain form goes back to the page."""
    if not is_htmx(request):
        return see_other(request.headers.get("referer") or "/today")
    snap = snapshot(db, c.user, c.today, c.tz)
    return render(request, f"partials/{partial}.html", c, snap=snap)


def _clean(text: str, limit: int, what: str) -> str:
    text = " ".join(text.split())
    if not text:
        raise HTTPException(422, f"The {what} can't be empty.")
    return text[:limit]


@router.get("/today")
def today_page(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    return render(request, "today.html", c, snap=snapshot(db, c.user, c.today, c.tz))


# --- tasks -------------------------------------------------------------------------------


@router.post("/tasks")
def add_task(
    request: Request,
    title: str = Form(""),
    area: str = Form(""),
    priority: int = Form(2),
    estimate_min: int = Form(30),
    when: str = Form("today"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    planned = {"today": c.today, "tomorrow": c.today + timedelta(days=1), "backlog": None}.get(when, c.today)
    db.add(
        Task(
            user_id=c.user.id,
            title=_clean(title, 200, "task title"),
            area=" ".join(area.split()).lower()[:40],
            priority=min(max(priority, 1), 3),
            estimate_min=min(max(estimate_min, 5), 8 * 60),
            planned_for=planned,
        )
    )
    db.commit()
    return _fragment(request, db, c, "tasks")


@router.post("/tasks/{task_id}/status")
def set_status(request: Request, task_id: int, status: str = Form(...), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    task = _owned(db, Task, task_id, c)
    if status not in ("todo", "doing", "done", "dropped"):
        raise HTTPException(422, "Unknown status")
    task.status = status
    task.completed_at = utcnow() if status == "done" else None
    if status in ("todo", "doing") and (task.planned_for is None or task.planned_for > c.today):
        task.planned_for = c.today  # starting a backlog/upcoming task pulls it into today
    db.commit()
    return _fragment(request, db, c, "tasks")


@router.post("/tasks/{task_id}/update")
def update_task(
    request: Request,
    task_id: int,
    title: str = Form(""),
    area: str = Form(""),
    priority: int = Form(2),
    estimate_min: int = Form(30),
    due_date: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    task = _owned(db, Task, task_id, c)
    task.title = _clean(title, 200, "task title")
    task.area = " ".join(area.split()).lower()[:40]
    task.priority = min(max(priority, 1), 3)
    task.estimate_min = min(max(estimate_min, 5), 8 * 60)
    try:
        task.due_date = date.fromisoformat(due_date) if due_date else None
    except ValueError as exc:
        raise HTTPException(422, "Due date must be a date") from exc
    db.commit()
    return _fragment(request, db, c, "tasks")


@router.post("/tasks/{task_id}/delete")
def delete_task(request: Request, task_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    db.delete(_owned(db, Task, task_id, c))
    db.commit()
    return _fragment(request, db, c, "tasks")


# --- work log -----------------------------------------------------------------------------


@router.post("/log")
def add_log(
    request: Request,
    kind: str = Form("done"),
    text: str = Form(""),
    minutes: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if kind not in LOG_KINDS:
        raise HTTPException(422, "Unknown entry type")
    mins = int(minutes) if minutes.strip().isdigit() else None
    db.add(LogEntry(user_id=c.user.id, day=c.today, kind=kind, text=_clean(text, 500, "entry"), minutes=min(mins, 16 * 60) if mins else None))
    db.commit()
    return _fragment(request, db, c, "log")


@router.post("/log/{entry_id}/delete")
def delete_log(request: Request, entry_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    db.delete(_owned(db, LogEntry, entry_id, c))
    db.commit()
    return _fragment(request, db, c, "log")


# --- blockers -----------------------------------------------------------------------------


@router.post("/blockers")
def add_blocker(request: Request, text: str = Form(""), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    db.add(Blocker(user_id=c.user.id, text=_clean(text, 300, "blocker"), opened_on=c.today))
    db.commit()
    return _fragment(request, db, c, "blockers")


@router.post("/blockers/{blocker_id}/resolve")
def resolve_blocker(request: Request, blocker_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    blocker = _owned(db, Blocker, blocker_id, c)
    blocker.resolved_on = None if blocker.resolved_on else c.today
    db.commit()
    return _fragment(request, db, c, "blockers")


@router.post("/blockers/{blocker_id}/delete")
def delete_blocker(request: Request, blocker_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    db.delete(_owned(db, Blocker, blocker_id, c))
    db.commit()
    return _fragment(request, db, c, "blockers")


# --- check-in -----------------------------------------------------------------------------


@router.post("/checkin")
def checkin(
    request: Request,
    energy: int = Form(3),
    mood: int = Form(3),
    focus_hours: float = Form(0),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if not (1 <= energy <= 5 and 1 <= mood <= 5 and 0 <= focus_hours <= 16):
        raise HTTPException(422, "Energy and mood go from 1 to 5; focus from 0 to 16 hours.")
    row = db.query(Checkin).filter_by(user_id=c.user.id, day=c.today).one_or_none()
    if row is None:
        row = Checkin(user_id=c.user.id, day=c.today)
        db.add(row)
    row.energy, row.mood, row.focus_hours = energy, mood, round(focus_hours * 4) / 4
    db.commit()
    return _fragment(request, db, c, "checkin")
