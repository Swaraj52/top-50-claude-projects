from __future__ import annotations

from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..deps import current_user, get_db, get_owned, get_secret_box, user_zone
from ..models import Email, EmailAccount, Task, User
from ..schemas import EmailAccountIn, EmailAccountOut, EmailOut, EmailSyncOut, TaskOut
from ..security import SecretBox
from ..services import imap
from ..timeutil import local_today

router = APIRouter(prefix="/email", tags=["email"])


def _account(db: DbSession, user: User) -> EmailAccount | None:
    return db.scalar(select(EmailAccount).where(EmailAccount.user_id == user.id))


@router.get("/account", response_model=EmailAccountOut | None)
def get_account(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    return _account(db, user)


@router.put("/account", response_model=EmailAccountOut)
def connect_account(
    body: EmailAccountIn,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
    box: SecretBox = Depends(get_secret_box),
):
    """Verify the credentials against the server, then store them encrypted."""
    try:
        imap.verify_login(body.host, body.port, body.username, body.password, body.mailbox)
    except imap.ImapError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    account = _account(db, user)
    if account is None:
        account = EmailAccount(user_id=user.id)
        db.add(account)
    elif (account.host, account.username, account.mailbox) != (body.host, body.username, body.mailbox):
        db.execute(delete(Email).where(Email.account_id == account.id))
    account.host = body.host
    account.port = body.port
    account.username = body.username
    account.password_encrypted = box.encrypt(body.password)
    account.mailbox = body.mailbox
    account.last_error = None
    db.commit()
    return account


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    account = _account(db, user)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No email account is connected")
    db.delete(account)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sync", response_model=EmailSyncOut)
def sync(
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
    box: SecretBox = Depends(get_secret_box),
):
    account = _account(db, user)
    if account is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect an email account first")
    try:
        headers = imap.fetch_recent_headers(
            account.host,
            account.port,
            account.username,
            box.decrypt(account.password_encrypted),
            account.mailbox,
        )
    except (imap.ImapError, ValueError) as exc:
        account.last_error = str(exc)[:500]
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Email sync failed: {exc}") from exc

    existing = {e.uid: e for e in db.scalars(select(Email).where(Email.account_id == account.id))}
    seen = set()
    for h in headers:
        seen.add(h.uid)
        row = existing.get(h.uid)
        if row is None:
            row = Email(user_id=user.id, account_id=account.id, uid=h.uid)
            db.add(row)
        row.message_id = h.message_id
        row.from_name = h.from_name
        row.from_addr = h.from_addr
        row.subject = h.subject
        row.received_at = h.received_at
        row.is_unread = h.is_unread
        row.is_flagged = h.is_flagged
    # Messages that left the window (or were deleted on the server) are dropped.
    for uid, row in existing.items():
        if uid not in seen:
            db.delete(row)
    account.last_synced_at = utcnow()
    account.last_error = None
    db.commit()
    return EmailSyncOut(
        fetched=len(headers), attention=sum(1 for h in headers if h.is_unread or h.is_flagged)
    )


@router.get("/messages", response_model=list[EmailOut])
def messages(
    filter: Literal["attention", "unread", "all"] = "attention",
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    q = select(Email).where(Email.user_id == user.id)
    if filter == "attention":
        q = q.where(or_(Email.is_unread, Email.is_flagged))
    elif filter == "unread":
        q = q.where(Email.is_unread)
    return db.scalars(q.order_by(Email.received_at.desc()).limit(200)).all()


@router.post("/messages/{email_id}/task", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def make_task(
    email_id: int,
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
):
    email = get_owned(db, Email, email_id, user)
    if email.task_id is not None and db.get(Task, email.task_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A task already exists for this email")
    sender = f"{email.from_name} <{email.from_addr}>" if email.from_name != email.from_addr else email.from_addr
    task = Task(
        user_id=user.id,
        title=f"Reply: {email.subject}"[:200],
        notes=f"From: {sender}\nReceived: {email.received_at.astimezone(tz):%Y-%m-%d %H:%M}",
        priority="high" if email.is_flagged else "medium",
        due_date=local_today(tz),
    )
    db.add(task)
    db.flush()
    email.task_id = task.id
    db.commit()
    return task
