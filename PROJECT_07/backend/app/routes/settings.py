from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from ..models import Draft, FollowUp, Mailbox, Session, Thread, User
from ..security import hash_password, verify_password
from ..services.mail import email_of
from ..timeutil import is_valid_timezone
from ..web import SESSION_COOKIE, Ctx, csrf, ctx, get_db, render, see_other

router = APIRouter()
_EMAIL = TypeAdapter(EmailStr)


def _counts(db: DbSession, user_id: int) -> dict[str, int]:
    return {
        "threads": len(list(db.scalars(select(Thread.id).where(Thread.user_id == user_id)))),
        "drafts": len(list(db.scalars(select(Draft.id).where(Draft.user_id == user_id)))),
        "followups": len(list(db.scalars(select(FollowUp.id).where(FollowUp.user_id == user_id)))),
        "mailboxes": len(list(db.scalars(select(Mailbox.id).where(Mailbox.user_id == user_id)))),
    }


@router.get("/settings")
def settings_page(
    request: Request,
    saved: int = 0,
    error: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    return render(
        request,
        "settings.html",
        c,
        saved=saved,
        error=error or None,
        counts=_counts(db, c.user.id),
        mailboxes=list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()),
    )


@router.post("/settings")
def save_settings(
    request: Request,
    name: str = Form(""),
    timezone: str = Form("UTC"),
    signature: str = Form(""),
    vips: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    name = name.strip()
    if not name or len(name) > 80:
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Name must be between 1 and 80 characters.",
            counts=_counts(db, c.user.id),
            mailboxes=list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()),
        )
    if not is_valid_timezone(timezone):
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Unknown timezone. Pick a value like Asia/Kolkata.",
            counts=_counts(db, c.user.id),
            mailboxes=list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()),
        )
    if len(signature) > 240 or len(vips) > 2000:
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Keep the signature under 240 characters and the VIP list under 2,000.",
            counts=_counts(db, c.user.id),
            mailboxes=list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()),
        )
    user = db.get(User, c.user.id)
    user.name = name
    user.timezone = timezone
    user.signature = signature.strip()
    user.vips = vips.strip()
    db.commit()
    return see_other("/settings?saved=1")


@router.post("/settings/password")
def change_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if not verify_password(current_password, c.user.password_hash):
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Your current password is incorrect.",
            counts=_counts(db, c.user.id),
            mailboxes=list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()),
        )
    if not 8 <= len(new_password) <= 128:
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Use a new password of at least 8 characters.",
            counts=_counts(db, c.user.id),
            mailboxes=list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()),
        )
    user = db.get(User, c.user.id)
    user.password_hash = hash_password(new_password)
    db.execute(delete(Session).where(Session.user_id == user.id, Session.id != c.session.id))
    db.commit()
    return see_other("/settings?saved=1")


@router.post("/settings/mailboxes")
def add_mailbox(
    request: Request,
    name: str = Form(""),
    address: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    name = name.strip()
    address = email_of(address)
    mailboxes = list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all())
    if not name or len(name) > 40:
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Give the mailbox a short name (up to 40 characters).",
            counts=_counts(db, c.user.id),
            mailboxes=mailboxes,
        )
    try:
        _EMAIL.validate_python(address)
    except ValidationError:
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Enter a valid mailbox address.",
            counts=_counts(db, c.user.id),
            mailboxes=mailboxes,
        )
    if db.scalar(select(Mailbox.id).where(Mailbox.user_id == c.user.id, Mailbox.address == address)):
        return render(
            request,
            "settings.html",
            c,
            http_status=409,
            error="That address is already listed.",
            counts=_counts(db, c.user.id),
            mailboxes=mailboxes,
        )
    db.add(Mailbox(user_id=c.user.id, name=name, address=address))
    db.commit()
    return see_other("/settings?saved=1")


@router.post("/settings/mailboxes/{mailbox_id}/delete")
def delete_mailbox(
    mailbox_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    mailbox = db.scalar(select(Mailbox).where(Mailbox.id == mailbox_id, Mailbox.user_id == c.user.id))
    if mailbox is None:
        raise HTTPException(404, "That mailbox doesn't exist.")
    threads = db.scalar(select(func.count(Thread.id)).where(Thread.mailbox_id == mailbox.id)) or 0
    if threads:
        raise HTTPException(409, "Delete or move that mailbox's threads before removing it.")
    db.delete(mailbox)
    db.commit()
    return see_other("/settings?saved=1")


@router.get("/settings/export")
def export_data(c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    mailboxes = list(
        db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()
    )
    threads = list(
        db.scalars(
            select(Thread)
            .where(Thread.user_id == c.user.id)
            .order_by(Thread.last_activity_at, Thread.id)
        ).all()
    )
    payload = {
        "format": "switchboard-export-v1",
        "exported_for": c.user.email,
        "mailboxes": [{"name": m.name, "address": m.address} for m in mailboxes],
        "threads": [
            {
                "mailbox": thread.mailbox.address,
                "subject": thread.subject,
                "participants": thread.participants,
                "category": thread.category,
                "status": thread.status,
                "starred": thread.starred,
                "unread": thread.unread,
                "summary": thread.summary,
                "summary_source": thread.summary_source,
                "last_activity_at": thread.last_activity_at.isoformat(),
                "messages": [
                    {
                        "direction": message.direction,
                        "sender": message.sender,
                        "recipients": message.recipients,
                        "body": message.body,
                        "received_at": message.received_at.isoformat(),
                    }
                    for message in sorted(thread.messages, key=lambda m: (m.received_at, m.id))
                ],
                "drafts": [
                    {
                        "subject": draft.subject,
                        "body": draft.body,
                        "tone": draft.tone,
                        "status": draft.status,
                        "source": draft.source,
                        "note": draft.note,
                    }
                    for draft in sorted(thread.drafts, key=lambda d: d.id)
                ],
                "followups": [
                    {
                        "title": followup.title,
                        "due_date": followup.due_date.isoformat() if followup.due_date else None,
                        "status": followup.status,
                    }
                    for followup in sorted(thread.followups, key=lambda f: f.id)
                ],
            }
            for thread in threads
        ],
    }
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="switchboard-export.json"'},
    )


@router.post("/settings/delete")
def delete_account(
    request: Request,
    password: str = Form(""),
    confirm: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if confirm != "DELETE":
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Type DELETE to confirm.",
            counts=_counts(db, c.user.id),
            mailboxes=list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()),
        )
    if not verify_password(password, c.user.password_hash):
        return render(
            request,
            "settings.html",
            c,
            http_status=422,
            error="Your password is incorrect.",
            counts=_counts(db, c.user.id),
            mailboxes=list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all()),
        )
    db.execute(delete(User).where(User.id == c.user.id))
    db.commit()
    resp = see_other("/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp
