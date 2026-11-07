from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..deps import current_user, get_db, get_owned
from ..models import Event, User
from ..schemas import EventIn, EventOut, EventPatch

router = APIRouter(prefix="/events", tags=["events"])

LOCAL_COLOR = "#0f9d8a"
MAX_RANGE = timedelta(days=62)


def to_out(event: Event) -> EventOut:
    source = event.source
    return EventOut(
        id=event.id,
        title=event.title,
        location=event.location,
        description=event.description,
        start_at=event.start_at,
        end_at=event.end_at,
        all_day=event.all_day,
        source_id=event.source_id,
        source_name=source.name if source else None,
        color=source.color if source else LOCAL_COLOR,
        read_only=source is not None,
    )


def events_between(db: DbSession, user: User, start: datetime, end: datetime) -> list[Event]:
    return list(
        db.scalars(
            select(Event)
            .options(selectinload(Event.source))
            .where(Event.user_id == user.id, Event.start_at < end, Event.end_at > start)
            .order_by(Event.all_day.desc(), Event.start_at, Event.title)
        )
    )


@router.get("", response_model=list[EventOut])
def list_events(
    start: AwareDatetime = Query(),
    end: AwareDatetime = Query(),
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    if end <= start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end must be after start")
    if end - start > MAX_RANGE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "range may span at most 62 days")
    return [to_out(e) for e in events_between(db, user, start, end)]


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(body: EventIn, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    event = Event(user_id=user.id, **body.model_dump())
    db.add(event)
    db.commit()
    return to_out(event)


def _editable(db: DbSession, event_id: int, user: User) -> Event:
    event = get_owned(db, Event, event_id, user)
    if event.source_id is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This event comes from a subscribed calendar and is read-only here",
        )
    return event


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int,
    body: EventPatch,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    event = _editable(db, event_id, user)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(event, field, value)
    if event.end_at < event.start_at:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end_at must not be before start_at")
    db.commit()
    return to_out(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    db.delete(_editable(db, event_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
