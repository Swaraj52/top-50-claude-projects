from __future__ import annotations

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..deps import current_user, get_db, get_owned, get_secret_box, user_zone
from ..models import CalendarSource, User
from ..schemas import HEX_COLOR, CalendarOut, CalendarUrlIn
from ..security import SecretBox
from ..services import ics

router = APIRouter(prefix="/calendars", tags=["calendars"])

MAX_SOURCES = 20


def _check_quota(db: DbSession, user: User) -> None:
    count = len(db.scalars(select(CalendarSource.id).where(CalendarSource.user_id == user.id)).all())
    if count >= MAX_SOURCES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You can connect at most {MAX_SOURCES} calendars")


@router.get("", response_model=list[CalendarOut])
def list_calendars(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    return db.scalars(
        select(CalendarSource).where(CalendarSource.user_id == user.id).order_by(CalendarSource.created_at)
    ).all()


@router.post("", response_model=CalendarOut, status_code=status.HTTP_201_CREATED)
def subscribe(
    body: CalendarUrlIn,
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
    box: SecretBox = Depends(get_secret_box),
):
    """Subscribe to an ICS feed. The feed is fetched first so a bad URL fails fast."""
    _check_quota(db, user)
    try:
        parsed = ics.parse_ics(ics.fetch_ics(body.url), tz)
    except ics.IcsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Couldn't load that calendar: {exc}") from exc
    source = CalendarSource(
        user_id=user.id,
        name=body.name.strip(),
        kind="url",
        url_encrypted=box.encrypt(body.url),
        color=body.color,
    )
    db.add(source)
    db.flush()
    ics.replace_source_events(db, source, parsed)
    db.commit()
    return source


@router.post("/upload", response_model=CalendarOut, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    name: str = Form(""),
    color: str = Form("#e8833a"),
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
):
    _check_quota(db, user)
    if not HEX_COLOR.match(color):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "color must look like #RRGGBB")
    data = await file.read(ics.MAX_BYTES + 1)
    if len(data) > ics.MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Calendar file is larger than 5 MB")
    try:
        parsed = ics.parse_ics(data, tz)
    except ics.IcsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    display = (name.strip() or (file.filename or "Imported calendar").rsplit(".", 1)[0])[:80]
    source = CalendarSource(user_id=user.id, name=display or "Imported calendar", kind="file", color=color)
    db.add(source)
    db.flush()
    ics.replace_source_events(db, source, parsed)
    db.commit()
    return source


@router.post("/{source_id}/sync", response_model=CalendarOut)
def sync(
    source_id: int,
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
    box: SecretBox = Depends(get_secret_box),
):
    source = get_owned(db, CalendarSource, source_id, user)
    if source.kind != "url" or not source.url_encrypted:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Uploaded calendars can't be re-synced. Upload the file again instead.",
        )
    try:
        parsed = ics.parse_ics(ics.fetch_ics(box.decrypt(source.url_encrypted)), tz)
    except (ics.IcsError, ValueError) as exc:
        source.last_error = str(exc)[:500]
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Sync failed: {exc}") from exc
    ics.replace_source_events(db, source, parsed)
    db.commit()
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(source_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    db.delete(get_owned(db, CalendarSource, source_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
