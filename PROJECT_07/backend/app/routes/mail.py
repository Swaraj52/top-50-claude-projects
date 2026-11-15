from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..models import CATEGORIES, Draft, FollowUp, Mailbox, Message, Thread
from ..services import ai
from ..services.mail import (
    CATEGORY_LABELS,
    Classification,
    classify,
    clean_text,
    display_sender,
    draft_local,
    parse_eml,
    priority,
    subject_key,
    summarise_local,
    vip_set,
)
from ..timeutil import parse_local_datetime, parse_people, relative_day, to_utc
from ..web import Ctx, csrf, ctx, get_db, render, safe_next, see_other

router = APIRouter()

MAX_BODY = 60_000
TONES = ("warm", "brief", "formal")


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _mailboxes(db: DbSession, c: Ctx) -> list[Mailbox]:
    return list(db.scalars(select(Mailbox).where(Mailbox.user_id == c.user.id).order_by(Mailbox.id)).all())


def _thread_or_404(db: DbSession, c: Ctx, thread_id: int) -> Thread:
    thread = db.scalar(select(Thread).where(Thread.id == thread_id, Thread.user_id == c.user.id))
    if thread is None:
        raise HTTPException(404, "That thread doesn't exist.")
    return thread


def _draft_or_404(db: DbSession, c: Ctx, draft_id: int) -> Draft:
    draft = db.scalar(select(Draft).where(Draft.id == draft_id, Draft.user_id == c.user.id))
    if draft is None:
        raise HTTPException(404, "That draft doesn't exist.")
    return draft


def _followup_or_404(db: DbSession, c: Ctx, followup_id: int) -> FollowUp:
    followup = db.scalar(select(FollowUp).where(FollowUp.id == followup_id, FollowUp.user_id == c.user.id))
    if followup is None:
        raise HTTPException(404, "That follow-up doesn't exist.")
    return followup


def _participants(messages: list[Message]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for message in messages:
        candidates = [message.sender, *parse_people(message.recipients)]
        for raw in candidates:
            label = display_sender(raw) if ("@" in raw or "<" in raw) else raw.strip()
            label = clean_text(label, 80)
            if not label or label.lower() in seen:
                continue
            seen.add(label.lower())
            out.append(label)
    return ", ".join(out)[:400]


def _latest_inbound(thread: Thread) -> Message | None:
    inbound = [m for m in thread.messages if m.direction == "in"]
    return (inbound or list(thread.messages))[-1] if thread.messages else None


def _refresh_thread(thread: Thread, messages: list[Message], vips: set[str], *, inbound: bool) -> None:
    thread.participants = _participants(messages)
    latest = _latest_inbound(thread)
    if latest is not None:
        result: Classification = classify(latest.sender, thread.subject, latest.body, vips)
        if thread.category_source != "you":
            thread.category = result.category
            thread.category_source = "rules"
        if inbound:
            thread.status = "open"
        elif thread.status != "closed":
            thread.status = "waiting"
        thread.unread = thread.unread or inbound
        thread.summary = summarise_local(thread.messages)
        thread.summary_source = "local"
        thread.summary_note = "Local summary: the first sentences of the latest message; no model call."
        thread.last_activity_at = max(
            [message.received_at for message in thread.messages] or [thread.last_activity_at]
        )
    thread.updated_at = utcnow()


def _ingest(
    db: DbSession,
    c: Ctx,
    mailbox: Mailbox,
    *,
    sender: str,
    recipients: str,
    subject: str,
    body: str,
    received_at: datetime,
    external_id: str | None = None,
) -> tuple[Thread, Message | None]:
    """Create or append to a thread. Returns (thread, new_message_or_None)."""
    sender = clean_text(sender, 254)
    subject = clean_text(subject, 200) or "(no subject)"
    body = (body or "").strip()[:MAX_BODY]
    key = subject_key(subject) or "(no subject)"

    if external_id:
        existing = db.scalar(
            select(Message).where(Message.user_id == c.user.id, Message.external_id == external_id)
        )
        if existing is not None:
            return existing.thread, None

    thread = db.scalar(
        select(Thread)
        .where(
            Thread.user_id == c.user.id,
            Thread.mailbox_id == mailbox.id,
            Thread.subject_key == key,
            Thread.status != "closed",
        )
        .order_by(Thread.last_activity_at.desc())
        .limit(1)
    )
    if thread is None:
        thread = Thread(
            user_id=c.user.id,
            mailbox_id=mailbox.id,
            subject=subject,
            subject_key=key,
            participants="",
            category="fyi",
            category_source="rules",
            status="open",
            unread=True,
            last_activity_at=received_at,
        )
        db.add(thread)
        db.flush()

    message = Message(
        user_id=c.user.id,
        thread_id=thread.id,
        direction="in",
        sender=sender,
        recipients=clean_text(recipients, 400),
        body=body,
        received_at=received_at,
        external_id=external_id,
    )
    db.add(message)
    db.flush()
    db.refresh(thread)
    _refresh_thread(thread, thread.messages, vip_set(c.user.vips), inbound=True)
    db.commit()
    return thread, message


def _rows(threads: list[Thread], c: Ctx) -> list[dict]:
    vips = vip_set(c.user.vips)
    rows = []
    for thread in threads:
        score, reasons = priority(thread, vips, c.now, thread.unread, thread.starred)
        rows.append(
            {
                "thread": thread,
                "score": score,
                "reasons": reasons,
                "latest": thread.messages[-1] if thread.messages else None,
            }
        )
    return rows


def _greeting(now: datetime, tz) -> str:
    hour = now.astimezone(tz).hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def _category_counts(db: DbSession, c: Ctx) -> dict[str, int]:
    counts = {category: 0 for category in CATEGORIES}
    rows = db.execute(
        select(Thread.category, func.count(Thread.id))
        .where(Thread.user_id == c.user.id, Thread.status != "closed")
        .group_by(Thread.category)
    ).all()
    for category, total in rows:
        counts[category] = total
    return counts


def _followup_groups(followups: list[FollowUp], today) -> list[dict]:
    groups = [
        {"key": "overdue", "label": "Overdue", "rows": []},
        {"key": "today", "label": "Today", "rows": []},
        {"key": "week", "label": "Next seven days", "rows": []},
        {"key": "later", "label": "Later", "rows": []},
        {"key": "none", "label": "No date", "rows": []},
    ]
    index = {group["key"]: group for group in groups}
    for followup in followups:
        if followup.due_date is None:
            index["none"]["rows"].append(followup)
        elif followup.due_date < today:
            index["overdue"]["rows"].append(followup)
        elif followup.due_date == today:
            index["today"]["rows"].append(followup)
        elif followup.due_date <= today + timedelta(days=7):
            index["week"]["rows"].append(followup)
        else:
            index["later"]["rows"].append(followup)
    return [group for group in groups if group["rows"]]


@router.get("/")
def dashboard(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    threads = list(
        db.scalars(select(Thread).where(Thread.user_id == c.user.id).order_by(Thread.last_activity_at.desc())).all()
    )
    open_threads = [t for t in threads if t.status != "closed"]
    rows = _rows(open_threads, c)
    rows.sort(key=lambda row: (row["score"], row["thread"].last_activity_at), reverse=True)
    followups = list(
        db.scalars(
            select(FollowUp)
            .where(FollowUp.user_id == c.user.id, FollowUp.status == "open")
            .order_by(FollowUp.due_date.is_(None), FollowUp.due_date, FollowUp.id)
            .limit(6)
        ).all()
    )
    drafts = list(
        db.scalars(
            select(Draft)
            .where(Draft.user_id == c.user.id, Draft.status == "draft")
            .order_by(Draft.updated_at.desc())
            .limit(4)
        ).all()
    )
    stats = {
        "unread": sum(1 for t in open_threads if t.unread),
        "reply": sum(1 for t in open_threads if t.category == "reply"),
        "waiting": sum(1 for t in open_threads if t.category == "waiting"),
        "drafts": len(
            list(db.scalars(select(Draft.id).where(Draft.user_id == c.user.id, Draft.status == "draft")))
        ),
        "followups": len(
            list(db.scalars(select(FollowUp.id).where(FollowUp.user_id == c.user.id, FollowUp.status == "open")))
        ),
        "overdue": sum(1 for f in followups if f.due_date and f.due_date < c.today and f.status == "open"),
    }
    return render(
        request,
        "dashboard.html",
        c,
        rows=rows[:6],
        stats=stats,
        followups=followups,
        drafts=drafts,
        categories=_category_counts(db, c),
        labels=CATEGORY_LABELS,
        threads_total=len(open_threads),
        greeting=_greeting(c.now, c.tz),
    )


@router.get("/inbox")
def inbox(
    request: Request,
    view: str = "priority",
    q: str = "",
    mailbox: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    query = select(Thread).where(Thread.user_id == c.user.id)
    if view == "closed":
        query = query.where(Thread.status == "closed")
    elif view == "starred":
        query = query.where(Thread.starred.is_(True), Thread.status != "closed")
    elif view in CATEGORIES:
        query = query.where(Thread.category == view, Thread.status != "closed")
    elif view in ("all", "priority"):
        query = query.where(Thread.status != "closed")
    else:
        view = "priority"
        query = query.where(Thread.status != "closed")

    if mailbox:
        query = query.where(Thread.mailbox_id == mailbox)
    term = q.strip()
    if term:
        pattern = _like(term)
        query = query.where(
            or_(
                Thread.subject.ilike(pattern, escape="\\"),
                Thread.participants.ilike(pattern, escape="\\"),
                Thread.messages.any(Message.body.ilike(pattern, escape="\\")),
            )
        )
    threads = list(db.scalars(query.order_by(Thread.last_activity_at.desc()).limit(120)).all())
    rows = _rows(threads, c)
    if view in ("priority", "all"):
        rows.sort(key=lambda row: (row["score"], row["thread"].last_activity_at), reverse=True)
    return render(
        request,
        "inbox.html",
        c,
        rows=rows,
        view=view,
        q=term,
        mailbox=mailbox,
        mailboxes=_mailboxes(db, c),
        categories=_category_counts(db, c),
        labels=CATEGORY_LABELS,
        total=len(rows),
    )


@router.get("/threads/{thread_id}")
def thread_detail(
    request: Request,
    thread_id: int,
    imported: int = 0,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    thread = _thread_or_404(db, c, thread_id)
    if thread.unread:
        thread.unread = False
        db.commit()
    score, reasons = priority(thread, vip_set(c.user.vips), c.now, thread.unread, thread.starred)
    return render(
        request,
        "thread_detail.html",
        c,
        thread=thread,
        messages=thread.messages,
        drafts=[d for d in thread.drafts if d.status == "draft"],
        sent=[d for d in thread.drafts if d.status == "sent"],
        followups=thread.followups,
        labels=CATEGORY_LABELS,
        score=score,
        reasons=reasons,
        imported=imported,
        tones=(("warm", "Warm"), ("brief", "Brief"), ("formal", "Formal")),
    )


@router.get("/compose")
def compose_page(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    return render(
        request,
        "compose.html",
        c,
        mailboxes=_mailboxes(db, c),
        values={},
        error=None,
        now_local=c.now.astimezone(c.tz).strftime("%Y-%m-%dT%H:%M"),
    )


@router.post("/compose")
async def compose(
    request: Request,
    mailbox_id: int = Form(0),
    sender: str = Form(""),
    recipients: str = Form(""),
    subject: str = Form(""),
    received_at: str = Form(""),
    body: str = Form(""),
    file: UploadFile | None = File(None),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    mailbox = db.scalar(select(Mailbox).where(Mailbox.id == mailbox_id, Mailbox.user_id == c.user.id))
    mailboxes = _mailboxes(db, c)
    if mailbox is None and mailboxes:
        mailbox = mailboxes[0]
    if mailbox is None:
        mailbox = Mailbox(user_id=c.user.id, name="Personal", address=c.user.email)
        db.add(mailbox)
        db.flush()

    parsed = None
    if file is not None and file.filename:
        raw = await file.read()
        if len(raw) > 2_000_000:
            return render(
                request,
                "compose.html",
                c,
                mailboxes=mailboxes,
                values={},
                error="That .eml file is too large (2 MB maximum).",
                now_local=c.now.astimezone(c.tz).strftime("%Y-%m-%dT%H:%M"),
            )
        parsed = parse_eml(raw)
        sender = parsed.sender or sender
        recipients = parsed.recipients or recipients
        subject = parsed.subject or subject
        body = parsed.body or body
        received_at = ""

    values = {
        "sender": sender,
        "recipients": recipients,
        "subject": subject,
        "received_at": received_at,
        "body": body,
    }
    if not sender.strip() or "@" not in sender:
        return render(
            request,
            "compose.html",
            c,
            mailboxes=mailboxes,
            values=values,
            error="Add the sender's email address.",
            now_local=c.now.astimezone(c.tz).strftime("%Y-%m-%dT%H:%M"),
        )
    if len(body.strip()) < 1:
        return render(
            request,
            "compose.html",
            c,
            mailboxes=mailboxes,
            values=values,
            error="Paste the message body.",
            now_local=c.now.astimezone(c.tz).strftime("%Y-%m-%dT%H:%M"),
        )
    if len(body) > MAX_BODY:
        return render(
            request,
            "compose.html",
            c,
            mailboxes=mailboxes,
            values=values,
            error="That message is too long (60,000 characters maximum).",
            now_local=c.now.astimezone(c.tz).strftime("%Y-%m-%dT%H:%M"),
        )

    received = parse_local_datetime(received_at, c.tz) if received_at else None
    if received is None:
        if parsed and parsed.received_at:
            received = parsed.received_at
        else:
            received = c.now
    if received.tzinfo is None:
        received = to_utc(received, c.tz)

    thread, _message = _ingest(
        db,
        c,
        mailbox,
        sender=sender,
        recipients=recipients,
        subject=subject,
        body=body,
        received_at=received,
        external_id=parsed.external_id if parsed else None,
    )
    return see_other(f"/threads/{thread.id}?imported=1")


@router.post("/threads/{thread_id}/category")
def set_category(
    thread_id: int,
    category: str = Form("fyi"),
    next: str = Form("/inbox"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    thread = _thread_or_404(db, c, thread_id)
    if category not in CATEGORIES:
        raise HTTPException(422, "Unknown category.")
    thread.category = category
    thread.category_source = "you"
    thread.updated_at = utcnow()
    db.commit()
    return see_other(safe_next(next, f"/threads/{thread.id}"))


@router.post("/threads/{thread_id}/star")
def toggle_star(
    thread_id: int,
    next: str = Form("/inbox"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    thread = _thread_or_404(db, c, thread_id)
    thread.starred = not thread.starred
    db.commit()
    return see_other(safe_next(next, f"/threads/{thread.id}"))


@router.post("/threads/{thread_id}/unread")
def mark_unread(
    thread_id: int,
    next: str = Form("/inbox"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    thread = _thread_or_404(db, c, thread_id)
    thread.unread = True
    db.commit()
    return see_other(safe_next(next, "/inbox"))


@router.post("/threads/{thread_id}/status")
def set_status(
    thread_id: int,
    status: str = Form("open"),
    next: str = Form("/inbox"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if status not in ("open", "waiting", "closed"):
        raise HTTPException(422, "Unknown status.")
    thread = _thread_or_404(db, c, thread_id)
    thread.status = status
    thread.updated_at = utcnow()
    db.commit()
    return see_other(safe_next(next, f"/threads/{thread.id}"))


@router.post("/threads/{thread_id}/delete")
def delete_thread(
    thread_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    thread = _thread_or_404(db, c, thread_id)
    db.delete(thread)
    db.commit()
    return see_other("/inbox")


@router.post("/threads/{thread_id}/summarize")
def summarize_thread(
    request: Request,
    thread_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    thread = _thread_or_404(db, c, thread_id)
    limiter = request.app.state.ai_limiter
    key = str(c.user.id)
    if limiter.blocked(key):
        raise HTTPException(429, "Give the summariser a minute before trying again.")
    limiter.hit(key)
    text, source, note = ai.summarise(request.app.state.settings, thread, thread.messages)
    thread.summary = text
    thread.summary_source = source
    thread.summary_note = note
    thread.updated_at = utcnow()
    db.commit()
    return see_other(f"/threads/{thread.id}#summary")


@router.post("/threads/{thread_id}/draft")
def create_draft(
    request: Request,
    thread_id: int,
    tone: str = Form("warm"),
    engine: str = Form("local"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    thread = _thread_or_404(db, c, thread_id)
    if tone not in TONES:
        tone = "warm"
    settings = request.app.state.settings
    source = "claude" if engine == "claude" and settings.ai_enabled else "local"
    if source == "claude":
        limiter = request.app.state.ai_limiter
        key = str(c.user.id)
        if limiter.blocked(key):
            raise HTTPException(429, "Give the drafter a minute before trying again.")
        limiter.hit(key)
        text, source, note = ai.draft(settings, thread, thread.messages, c.user, tone)
    else:
        text = draft_local(thread, thread.messages, c.user, tone)
        note = ai.DRAFT_NOTE_LOCAL
    draft = Draft(
        user_id=c.user.id,
        thread_id=thread.id,
        subject=text.subject[:200],
        body=text.body[:4000],
        tone=tone,
        source=source,
        status="draft",
        note=note,
    )
    db.add(draft)
    db.commit()
    return see_other(f"/threads/{thread.id}#drafts")


@router.post("/drafts/{draft_id}")
def update_draft(
    draft_id: int,
    subject: str = Form(""),
    body: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    draft = _draft_or_404(db, c, draft_id)
    if draft.status != "draft":
        raise HTTPException(409, "That draft has already been marked sent.")
    if not 3 <= len(subject.strip()) <= 200:
        raise HTTPException(422, "Keep the subject between 3 and 200 characters.")
    if not 1 <= len(body.strip()) <= 4000:
        raise HTTPException(422, "Keep the draft between 1 and 4,000 characters.")
    draft.subject = subject.strip()
    draft.body = body.strip()
    draft.updated_at = utcnow()
    db.commit()
    return see_other(f"/threads/{draft.thread_id}#drafts")


@router.post("/drafts/{draft_id}/send")
def send_draft(
    draft_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    draft = _draft_or_404(db, c, draft_id)
    if draft.status != "draft":
        raise HTTPException(409, "That draft has already been marked sent.")
    thread = draft.thread
    latest = _latest_inbound(thread)
    message = Message(
        user_id=c.user.id,
        thread_id=thread.id,
        direction="out",
        sender=thread.mailbox.address,
        recipients=clean_text(latest.sender if latest else "", 400),
        body=draft.body,
        received_at=utcnow(),
    )
    db.add(message)
    draft.status = "sent"
    draft.note = "Marked sent locally. Switchboard does not send email."
    db.flush()
    db.refresh(thread)
    _refresh_thread(thread, thread.messages, vip_set(c.user.vips), inbound=False)
    # After a reply the ball is in their court, so the thread is explicitly waiting on them.
    thread.status = "waiting"
    if thread.category_source != "you":
        thread.category = "waiting"
        thread.category_source = "rules"
    thread.unread = False
    db.commit()
    return see_other(f"/threads/{thread.id}#drafts")


@router.post("/drafts/{draft_id}/delete")
def delete_draft(
    draft_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    draft = _draft_or_404(db, c, draft_id)
    thread_id = draft.thread_id
    db.delete(draft)
    db.commit()
    return see_other(f"/threads/{thread_id}#drafts")


@router.get("/drafts")
def drafts_page(
    request: Request,
    status: str = "draft",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    if status not in ("draft", "sent", "all"):
        status = "draft"
    query = select(Draft).where(Draft.user_id == c.user.id)
    if status != "all":
        query = query.where(Draft.status == status)
    drafts = list(db.scalars(query.order_by(Draft.updated_at.desc()).limit(120)).all())
    counts = {
        "draft": len(list(db.scalars(select(Draft.id).where(Draft.user_id == c.user.id, Draft.status == "draft")))),
        "sent": len(list(db.scalars(select(Draft.id).where(Draft.user_id == c.user.id, Draft.status == "sent")))),
    }
    return render(request, "drafts.html", c, drafts=drafts, status=status, counts=counts)


@router.get("/followups")
def followups_page(
    request: Request,
    status: str = "open",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    if status not in ("open", "done", "all"):
        status = "open"
    query = select(FollowUp).where(FollowUp.user_id == c.user.id)
    if status != "all":
        query = query.where(FollowUp.status == status)
    followups = list(
        db.scalars(
            query.order_by(FollowUp.due_date.is_(None), FollowUp.due_date, FollowUp.id).limit(200)
        ).all()
    )
    groups = _followup_groups(followups, c.today)
    counts = {
        "open": len(list(db.scalars(select(FollowUp.id).where(FollowUp.user_id == c.user.id, FollowUp.status == "open")))),
        "done": len(list(db.scalars(select(FollowUp.id).where(FollowUp.user_id == c.user.id, FollowUp.status == "done")))),
    }
    return render(
        request,
        "followups.html",
        c,
        groups=groups,
        status=status,
        counts=counts,
        today=c.today,
        followup_total=len(followups),
    )


@router.post("/threads/{thread_id}/followups")
def add_followup(
    thread_id: int,
    title: str = Form(""),
    due_date: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    thread = _thread_or_404(db, c, thread_id)
    title = clean_text(title, 240)
    if len(title) < 3:
        raise HTTPException(422, "Give the follow-up a title of at least 3 characters.")
    due = relative_day(due_date, c.today) if due_date else None
    db.add(
        FollowUp(
            user_id=c.user.id,
            thread_id=thread.id,
            title=title,
            due_date=due,
            status="open",
        )
    )
    db.commit()
    return see_other(f"/threads/{thread.id}#followups")


@router.post("/followups/{followup_id}/toggle")
def toggle_followup(
    followup_id: int,
    next: str = Form("/followups"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    followup = _followup_or_404(db, c, followup_id)
    followup.status = "done" if followup.status == "open" else "open"
    followup.completed_at = utcnow() if followup.status == "done" else None
    db.commit()
    return see_other(safe_next(next, "/followups"))


@router.post("/followups/{followup_id}/update")
def update_followup(
    followup_id: int,
    title: str = Form(""),
    due_date: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    followup = _followup_or_404(db, c, followup_id)
    title = clean_text(title, 240)
    if len(title) < 3:
        raise HTTPException(422, "Give the follow-up a title of at least 3 characters.")
    followup.title = title
    followup.due_date = relative_day(due_date, c.today) if due_date else None
    db.commit()
    return see_other("/followups")


@router.post("/followups/{followup_id}/delete")
def delete_followup(
    followup_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    followup = _followup_or_404(db, c, followup_id)
    db.delete(followup)
    db.commit()
    return see_other("/followups")
