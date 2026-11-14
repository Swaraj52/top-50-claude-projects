from __future__ import annotations

import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..models import ActionItem, Decision, Meeting
from ..services import ai
from ..timeutil import parse_attendees, relative_day
from ..web import Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()


def _owned_meeting(db: DbSession, user_id: int, meeting_id: int) -> Meeting:
    meeting = db.scalar(select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == user_id))
    if meeting is None:
        raise HTTPException(404, "That meeting doesn't exist.")
    return meeting


def _owned_action(db: DbSession, user_id: int, action_id: int) -> ActionItem:
    action = db.scalar(select(ActionItem).where(ActionItem.id == action_id, ActionItem.user_id == user_id))
    if action is None:
        raise HTTPException(404, "That follow-up doesn't exist.")
    return action


def _owned_decision(db: DbSession, user_id: int, decision_id: int) -> Decision:
    decision = db.scalar(select(Decision).where(Decision.id == decision_id, Decision.user_id == user_id))
    if decision is None:
        raise HTTPException(404, "That decision doesn't exist.")
    return decision


def _day(value: str, fallback: date) -> date:
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError):
        return fallback
    return parsed if 2000 <= parsed.year <= 2100 else fallback


def _safe_next(value: str, fallback: str = "/actions") -> str:
    """Only allow same-site paths, so a crafted `next` cannot become an open redirect."""
    if not value or not value.startswith("/") or value.startswith(("//", "/\\")):
        return fallback
    return value


def _apply(db: DbSession, meeting: Meeting, result: ai.ExtractResult) -> None:
    """Replace extracted memory with a fresh result. Manual edits are intentionally re-extracted."""
    db.execute(Decision.__table__.delete().where(Decision.meeting_id == meeting.id))
    db.execute(ActionItem.__table__.delete().where(ActionItem.meeting_id == meeting.id))
    meeting.summary = result.extraction.summary
    meeting.source = result.source
    meeting.model = result.model
    meeting.extract_note = result.note
    if result.extraction.attendees:
        meeting.attendees = ", ".join(result.extraction.attendees)
    meeting.updated_at = utcnow()
    for text in result.extraction.decisions:
        db.add(Decision(user_id=meeting.user_id, meeting_id=meeting.id, text=text, status="agreed", decided_on=meeting.occurred_on))
    for draft in result.extraction.actions:
        db.add(
            ActionItem(
                user_id=meeting.user_id,
                meeting_id=meeting.id,
                title=draft.title,
                owner=draft.owner,
                due_date=draft.due_date,
                status="open",
            )
        )
    db.commit()


def _meeting_form(request: Request, c: Ctx, template: str, meeting: Meeting | None = None, error: str | None = None, status: int = 200):
    return render(request, template, c, http_status=status, meeting=meeting, error=error)


@router.get("/")
def dashboard(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    month_start = c.today.replace(day=1)
    meetings = list(db.scalars(select(Meeting).where(Meeting.user_id == c.user.id).order_by(Meeting.occurred_on.desc(), Meeting.id.desc())))
    actions = list(db.scalars(select(ActionItem).where(ActionItem.user_id == c.user.id)))
    decisions = list(db.scalars(select(Decision).where(Decision.user_id == c.user.id).order_by(Decision.decided_on.desc(), Decision.id.desc())))
    open_actions = [a for a in actions if a.status == "open"]
    overdue = [a for a in open_actions if a.due_date and a.due_date < c.today]
    due_soon = [a for a in open_actions if a.due_date and c.today <= a.due_date <= c.today + timedelta(days=7)]
    followups = sorted(
        [a for a in open_actions if a.due_date],
        key=lambda a: (a.due_date, a.id),
    )[:8]
    undated = [a for a in open_actions if not a.due_date][:4]
    this_month = [m for m in meetings if m.occurred_on >= month_start]
    return render(
        request,
        "dashboard.html",
        c,
        meetings=meetings[:5],
        meeting_total=len(meetings),
        this_month=len(this_month),
        open_actions=len(open_actions),
        overdue=len(overdue),
        due_soon=len(due_soon),
        decision_total=len(decisions),
        followups=followups,
        undated=undated,
        recent_decisions=decisions[:5],
        owner_names=sorted({a.owner for a in open_actions if a.owner}),
    )


@router.get("/meetings")
def meetings_page(request: Request, q: str = "", source: str = "", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    stmt = select(Meeting).where(Meeting.user_id == c.user.id)
    q = q.strip()[:120]
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Meeting.title.ilike(like), Meeting.notes.ilike(like), Meeting.attendees.ilike(like), Meeting.summary.ilike(like)))
    if source in ("local", "claude"):
        stmt = stmt.where(Meeting.source == source)
    meetings = list(db.scalars(stmt.order_by(Meeting.occurred_on.desc(), Meeting.id.desc()).limit(200)))
    ids = [m.id for m in meetings]
    counts: dict[int, tuple[int, int]] = {}
    if ids:
        for action in db.scalars(select(ActionItem).where(ActionItem.meeting_id.in_(ids))):
            done, total = counts.get(action.meeting_id, (0, 0))
            counts[action.meeting_id] = (done + (1 if action.status == "done" else 0), total + 1)
    return render(request, "meetings.html", c, meetings=meetings, q=q, source=source, counts=counts)


@router.get("/meetings/new")
def new_meeting(request: Request, c: Ctx = Depends(ctx)):
    meeting = Meeting(title="", occurred_on=c.today, attendees="", notes="")
    return _meeting_form(request, c, "meeting_form.html", meeting)


@router.post("/meetings")
def create_meeting(
    request: Request,
    title: str = Form(""),
    occurred_on: str = Form(""),
    attendees: str = Form(""),
    notes: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    title = title.strip()
    notes = notes.strip()
    values = Meeting(title=title, occurred_on=_day(occurred_on, c.today), attendees=attendees.strip(), notes=notes)
    if not 3 <= len(title) <= 160:
        return _meeting_form(request, c, "meeting_form.html", values, "Give the meeting a title (3–160 characters).", 422)
    if len(notes) < 20:
        return _meeting_form(request, c, "meeting_form.html", values, "Paste at least a couple of lines of notes so there is something to remember.", 422)
    if len(notes) > 60000:
        return _meeting_form(request, c, "meeting_form.html", values, "Those notes are too long. Keep them under 60,000 characters.", 422)

    meeting = Meeting(
        user_id=c.user.id,
        title=title,
        occurred_on=values.occurred_on,
        attendees=", ".join(parse_attendees(attendees)),
        notes=notes,
        summary="",
        source="local",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(meeting)
    db.flush()

    limiter = request.app.state.extract_limiter
    key = f"user:{c.user.id}"
    if limiter.blocked(key):
        result = ai._local_result(meeting, notes, meeting.attendees, "Extraction limit reached; local extractor used.")
    else:
        limiter.hit(key)
        result = ai.suggest(request.app.state.settings, meeting, notes, meeting.attendees)
    _apply(db, meeting, result)
    return see_other(f"/meetings/{meeting.id}?created=1")


@router.get("/meetings/{meeting_id}")
def meeting_detail(
    meeting_id: int,
    request: Request,
    created: int = 0,
    saved: int = 0,
    extracted: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    meeting = _owned_meeting(db, c.user.id, meeting_id)
    actions = sorted(meeting.actions, key=lambda a: (a.status == "done", a.due_date is None, a.due_date or date.max, a.id))
    return render(
        request,
        "meeting_detail.html",
        c,
        meeting=meeting,
        actions=actions,
        created=created,
        saved=saved,
        extracted=extracted,
        error=request.query_params.get("error", ""),
    )


@router.get("/meetings/{meeting_id}/edit")
def edit_meeting(meeting_id: int, request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    return _meeting_form(request, c, "meeting_form.html", _owned_meeting(db, c.user.id, meeting_id))


@router.post("/meetings/{meeting_id}/edit")
def update_meeting(
    meeting_id: int,
    request: Request,
    title: str = Form(""),
    occurred_on: str = Form(""),
    attendees: str = Form(""),
    notes: str = Form(""),
    reextract: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    meeting = _owned_meeting(db, c.user.id, meeting_id)
    title, notes = title.strip(), notes.strip()
    values = Meeting(title=title, occurred_on=_day(occurred_on, c.today), attendees=attendees.strip(), notes=notes)
    values.id = meeting.id
    if not 3 <= len(title) <= 160:
        return _meeting_form(request, c, "meeting_form.html", values, "Give the meeting a title (3–160 characters).", 422)
    if len(notes) < 20:
        return _meeting_form(request, c, "meeting_form.html", values, "Keep at least a couple of lines of notes.", 422)
    meeting.title = title
    meeting.occurred_on = values.occurred_on
    meeting.attendees = ", ".join(parse_attendees(attendees))
    meeting.notes = notes
    meeting.updated_at = utcnow()
    if reextract:
        result = ai.suggest(request.app.state.settings, meeting, notes, meeting.attendees)
        _apply(db, meeting, result)
    for decision in meeting.decisions:
        decision.decided_on = meeting.occurred_on
    db.commit()
    return see_other(f"/meetings/{meeting.id}?saved=1")


@router.post("/meetings/{meeting_id}/extract")
def reextract(meeting_id: int, request: Request, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    meeting = _owned_meeting(db, c.user.id, meeting_id)
    limiter = request.app.state.extract_limiter
    key = f"user:{c.user.id}"
    if limiter.blocked(key):
        return render(
            request,
            "meeting_detail.html",
            c,
            http_status=429,
            meeting=meeting,
            actions=sorted(meeting.actions, key=lambda a: (a.status == "done", a.due_date is None, a.due_date or date.max, a.id)),
            error="Take a short break before re-reading the same notes again.",
        )
    limiter.hit(key)
    result = ai.suggest(request.app.state.settings, meeting, meeting.notes, meeting.attendees)
    _apply(db, meeting, result)
    return see_other(f"/meetings/{meeting.id}?extracted=1")


@router.post("/meetings/{meeting_id}/delete")
def delete_meeting(meeting_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    meeting = _owned_meeting(db, c.user.id, meeting_id)
    db.delete(meeting)
    db.commit()
    return see_other("/meetings?deleted=1")


@router.post("/meetings/{meeting_id}/decisions")
def add_decision(
    meeting_id: int,
    text: str = Form(""),
    status: str = Form("agreed"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    meeting = _owned_meeting(db, c.user.id, meeting_id)
    text = text.strip()
    if not 4 <= len(text) <= 500:
        return see_other(f"/meetings/{meeting.id}?error=decision")
    db.add(
        Decision(
            user_id=c.user.id,
            meeting_id=meeting.id,
            text=text,
            status=status if status in ("agreed", "revisit") else "agreed",
            decided_on=meeting.occurred_on,
        )
    )
    meeting.updated_at = utcnow()
    db.commit()
    return see_other(f"/meetings/{meeting.id}#decisions")


@router.post("/decisions/{decision_id}/status")
def decision_status(decision_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    decision = _owned_decision(db, c.user.id, decision_id)
    decision.status = "revisit" if decision.status == "agreed" else "agreed"
    db.commit()
    return see_other(f"/meetings/{decision.meeting_id}#decisions")


@router.post("/decisions/{decision_id}/delete")
def delete_decision(decision_id: int, c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    decision = _owned_decision(db, c.user.id, decision_id)
    meeting_id = decision.meeting_id
    db.delete(decision)
    db.commit()
    return see_other(f"/meetings/{meeting_id}#decisions")


@router.post("/meetings/{meeting_id}/actions")
def add_action(
    meeting_id: int,
    title: str = Form(""),
    owner: str = Form(""),
    due_date: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    meeting = _owned_meeting(db, c.user.id, meeting_id)
    title = title.strip()
    if not 3 <= len(title) <= 280:
        return see_other(f"/meetings/{meeting.id}?error=action")
    parsed_due = relative_day(due_date, c.today) if due_date.strip() else None
    db.add(
        ActionItem(
            user_id=c.user.id,
            meeting_id=meeting.id,
            title=title,
            owner=owner.strip()[:80],
            due_date=parsed_due,
            status="open",
        )
    )
    meeting.updated_at = utcnow()
    db.commit()
    return see_other(f"/meetings/{meeting.id}#actions")


@router.post("/actions/{action_id}/toggle")
def toggle_action(action_id: int, next: str = Form("/actions"), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    action = _owned_action(db, c.user.id, action_id)
    if action.status == "open":
        action.status = "done"
        action.completed_at = utcnow()
    else:
        action.status = "open"
        action.completed_at = None
    db.commit()
    return see_other(_safe_next(next))


@router.post("/actions/{action_id}/update")
def update_action(
    action_id: int,
    title: str = Form(""),
    owner: str = Form(""),
    due_date: str = Form(""),
    next: str = Form("/actions"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    action = _owned_action(db, c.user.id, action_id)
    title = title.strip()
    if 3 <= len(title) <= 280:
        action.title = title
    action.owner = owner.strip()[:80]
    action.due_date = relative_day(due_date, c.today) if due_date.strip() else None
    db.commit()
    return see_other(_safe_next(next))


@router.post("/actions/{action_id}/delete")
def delete_action(action_id: int, next: str = Form("/actions"), c: Ctx = Depends(csrf), db: DbSession = Depends(get_db)):
    action = _owned_action(db, c.user.id, action_id)
    db.delete(action)
    db.commit()
    return see_other(_safe_next(next))


@router.get("/actions")
def actions_page(request: Request, status: str = "open", owner: str = "", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    stmt = select(ActionItem).where(ActionItem.user_id == c.user.id)
    if status in ("open", "done"):
        stmt = stmt.where(ActionItem.status == status)
    if owner.strip():
        stmt = stmt.where(ActionItem.owner == owner.strip())
    actions = list(db.scalars(stmt.order_by(ActionItem.due_date.is_(None), ActionItem.due_date, ActionItem.id)))
    all_actions = list(db.scalars(select(ActionItem).where(ActionItem.user_id == c.user.id)))
    owners = sorted({a.owner for a in all_actions if a.owner})
    groups: dict[str, list[ActionItem]] = {"Overdue": [], "Today": [], "This week": [], "Later": [], "No date": []}
    if status == "open":
        week_end = c.today + timedelta(days=7)
        for action in actions:
            if not action.due_date:
                groups["No date"].append(action)
            elif action.due_date < c.today:
                groups["Overdue"].append(action)
            elif action.due_date == c.today:
                groups["Today"].append(action)
            elif action.due_date <= week_end:
                groups["This week"].append(action)
            else:
                groups["Later"].append(action)
    else:
        groups = {"Completed": actions} if actions else {}
    groups = {label: rows for label, rows in groups.items() if rows}
    return render(
        request,
        "actions.html",
        c,
        actions=actions,
        groups=groups,
        status=status,
        owner=owner,
        owners=owners,
        open_count=sum(1 for a in all_actions if a.status == "open"),
        done_count=sum(1 for a in all_actions if a.status == "done"),
        today=c.today,
    )


@router.get("/decisions")
def decisions_page(request: Request, q: str = "", status: str = "", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    stmt = select(Decision).where(Decision.user_id == c.user.id)
    q = q.strip()[:120]
    if q:
        stmt = stmt.where(Decision.text.ilike(f"%{q}%"))
    if status in ("agreed", "revisit"):
        stmt = stmt.where(Decision.status == status)
    decisions = list(db.scalars(stmt.order_by(Decision.decided_on.desc(), Decision.id.desc()).limit(300)))
    return render(request, "decisions.html", c, decisions=decisions, q=q, status=status)


@router.get("/memory")
def memory_page(request: Request, q: str = "", c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    q = q.strip()[:120]
    meetings: list[Meeting] = []
    decisions: list[Decision] = []
    actions: list[ActionItem] = []
    if q:
        like = f"%{q}%"
        meetings = list(db.scalars(select(Meeting).where(Meeting.user_id == c.user.id, or_(Meeting.title.ilike(like), Meeting.summary.ilike(like), Meeting.notes.ilike(like))).order_by(Meeting.occurred_on.desc()).limit(20)))
        decisions = list(db.scalars(select(Decision).where(Decision.user_id == c.user.id, Decision.text.ilike(like)).order_by(Decision.decided_on.desc()).limit(30)))
        actions = list(db.scalars(select(ActionItem).where(ActionItem.user_id == c.user.id, or_(ActionItem.title.ilike(like), ActionItem.owner.ilike(like))).order_by(ActionItem.id.desc()).limit(30)))
    return render(
        request,
        "memory.html",
        c,
        q=q,
        meetings=meetings,
        decisions=decisions,
        actions=actions,
        total=len(meetings) + len(decisions) + len(actions),
    )
