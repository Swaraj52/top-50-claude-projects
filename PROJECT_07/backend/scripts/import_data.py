"""Import a Switchboard JSON export into an existing account.

    cd PROJECT_07/backend
    python -m scripts.import_data --email you@example.com switchboard-export.json [--dry-run]

The file comes from **Settings -> Download JSON** (``switchboard-export-v1``). Only the archive is
read: threads, messages, drafts and follow-ups. There are no passwords, session tokens or API keys
in that format, and the importer never asks for any.

A thread is skipped when the same mailbox, cleaned subject and first-message time are already on the
desk, so the same file can be imported twice without duplicating anything. Missing mailboxes are
created. Invalid or out-of-range values are clamped to what the app accepts; when a summary or route
is missing, the app's own local rules fill it in.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.models import (
    CATEGORIES,
    DRAFT_SOURCES,
    DRAFT_STATUSES,
    DIRECTIONS,
    FOLLOWUP_STATUSES,
    THREAD_STATUSES,
    Draft,
    FollowUp,
    Mailbox,
    Message,
    Thread,
    User,
)
from app.services.mail import classify, clean_text, email_of, summarise_local, subject_key, vip_set

MAX_BODY = 60_000
FORMAT = "switchboard-export-v1"


def _text(value: Any, limit: int) -> str:
    return clean_text(str(value or ""), limit)


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp (``Z`` or an offset) into an aware UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _second(value: datetime) -> datetime:
    return value.replace(microsecond=0)


def _mailbox(db, user: User, address: str, name: str) -> Mailbox:
    address = email_of(address) or address.strip().lower()
    box = db.scalar(select(Mailbox).where(Mailbox.user_id == user.id, Mailbox.address == address))
    if box is not None:
        return box
    box = Mailbox(user_id=user.id, name=_text(name, 40) or "Imported", address=address)
    db.add(box)
    db.flush()
    return box


def _already_imported(db, user: User, box: Mailbox, key: str, earliest: datetime) -> bool:
    """True when the same mailbox/subject/first-message second is already stored."""
    candidates = db.scalars(
        select(Thread).where(
            Thread.user_id == user.id,
            Thread.mailbox_id == box.id,
            Thread.subject_key == key,
        )
    ).all()
    wanted = _second(earliest)
    for thread in candidates:
        stamps = [_second(message.received_at) for message in thread.messages]
        if stamps and min(stamps) == wanted:
            return True
    return False


def _read(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("threads"), list):
        raise SystemExit("Not a Switchboard export: expected a 'threads' list.")
    if payload.get("format") not in (None, FORMAT):
        raise SystemExit(f"Unsupported export format {payload.get('format')!r}; expected {FORMAT!r}.")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a Switchboard JSON export")
    parser.add_argument("file", type=Path)
    parser.add_argument("--email", required=True, help="account that receives the archive")
    parser.add_argument("--dry-run", action="store_true", help="validate and count without saving")
    args = parser.parse_args()

    payload = _read(args.file)
    settings = Settings()
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)

    counts = {
        "threads": 0,
        "messages": 0,
        "drafts": 0,
        "followups": 0,
        "mailboxes": 0,
        "skipped": 0,
        "invalid_messages": 0,
    }

    with Session() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            raise SystemExit(f"No account with email {args.email!r}.")
        vips = vip_set(user.vips)

        mailbox_names = {}
        for item in payload.get("mailboxes") or []:
            if not isinstance(item, dict):
                continue
            address = email_of(str(item.get("address") or ""))
            if address:
                mailbox_names[address] = _text(item.get("name"), 40)

        existing_boxes = set(
            db.scalars(select(Mailbox.address).where(Mailbox.user_id == user.id)).all()
        )

        for raw in payload["threads"]:
            if not isinstance(raw, dict):
                counts["skipped"] += 1
                continue

            subject = _text(raw.get("subject"), 200) or "(no subject)"
            key = subject_key(subject) or "(no subject)"

            messages: list[dict] = []
            for item in raw.get("messages") or []:
                if not isinstance(item, dict):
                    counts["invalid_messages"] += 1
                    continue
                received_at = _datetime(item.get("received_at"))
                body = str(item.get("body") or "").strip()
                if received_at is None or not body:
                    counts["invalid_messages"] += 1
                    continue
                direction = item.get("direction") if item.get("direction") in DIRECTIONS else "in"
                messages.append(
                    {
                        "direction": direction,
                        "sender": _text(item.get("sender"), 254) or "(unknown sender)",
                        "recipients": _text(item.get("recipients"), 400),
                        "body": body[:MAX_BODY],
                        "received_at": received_at,
                    }
                )

            if not messages:
                counts["skipped"] += 1
                continue

            messages.sort(key=lambda m: m["received_at"])
            earliest = messages[0]["received_at"]
            box = _mailbox(
                db,
                user,
                str(raw.get("mailbox") or user.email),
                mailbox_names.get(email_of(str(raw.get("mailbox") or user.email)), "Imported"),
            )
            if box.address not in existing_boxes:
                existing_boxes.add(box.address)
                counts["mailboxes"] += 1

            if _already_imported(db, user, box, key, earliest):
                counts["skipped"] += 1
                continue

            latest_inbound = next((m for m in reversed(messages) if m["direction"] == "in"), messages[-1])
            category = raw.get("category") if raw.get("category") in CATEGORIES else None
            if category is None:
                category = classify(latest_inbound["sender"], subject, latest_inbound["body"], vips).category
            status = raw.get("status") if raw.get("status") in THREAD_STATUSES else "open"
            summary = _text(raw.get("summary"), 800)
            summary_source = "claude" if raw.get("summary_source") == "claude" else "local"
            if not summary:
                summary = summarise_local(messages)
                summary_source = "local"

            thread = Thread(
                user_id=user.id,
                mailbox_id=box.id,
                subject=subject,
                subject_key=key,
                participants=_text(raw.get("participants"), 400),
                category=category,
                category_source="rules",
                status=status,
                unread=_flag(raw.get("unread")),
                starred=_flag(raw.get("starred")),
                summary=summary,
                summary_source=summary_source,
                summary_note="Imported from a Switchboard export."
                if summary_source == "local"
                else "Imported Claude summary from a Switchboard export.",
                last_activity_at=messages[-1]["received_at"],
            )
            db.add(thread)
            db.flush()
            counts["threads"] += 1

            for item in messages:
                db.add(
                    Message(
                        user_id=user.id,
                        thread_id=thread.id,
                        direction=item["direction"],
                        sender=item["sender"],
                        recipients=item["recipients"],
                        body=item["body"],
                        received_at=item["received_at"],
                    )
                )
                counts["messages"] += 1

            for item in raw.get("drafts") or []:
                if not isinstance(item, dict):
                    continue
                draft_subject = _text(item.get("subject"), 200)
                draft_body = str(item.get("body") or "").strip()[:MAX_BODY]
                if len(draft_subject) < 2 or len(draft_body) < 2:
                    continue
                db.add(
                    Draft(
                        user_id=user.id,
                        thread_id=thread.id,
                        subject=draft_subject,
                        body=draft_body,
                        tone=_text(item.get("tone"), 10) or "warm",
                        source=item.get("source") if item.get("source") in DRAFT_SOURCES else "local",
                        status=item.get("status") if item.get("status") in DRAFT_STATUSES else "draft",
                        note=_text(item.get("note"), 300),
                    )
                )
                counts["drafts"] += 1

            for item in raw.get("followups") or []:
                if not isinstance(item, dict):
                    continue
                title = _text(item.get("title"), 240)
                if len(title) < 3:
                    continue
                due = None
                if isinstance(item.get("due_date"), str) and item["due_date"].strip():
                    try:
                        due = date.fromisoformat(item["due_date"].strip()[:10])
                    except ValueError:
                        due = None
                db.add(
                    FollowUp(
                        user_id=user.id,
                        thread_id=thread.id,
                        title=title,
                        due_date=due,
                        status=item.get("status") if item.get("status") in FOLLOWUP_STATUSES else "open",
                        completed_at=datetime.now(timezone.utc)
                        if item.get("status") == "done"
                        else None,
                    )
                )
                counts["followups"] += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    engine.dispose()
    prefix = "Would import" if args.dry_run else "Imported"
    print(prefix + ": " + ", ".join(f"{value} {name}" for name, value in counts.items() if value))
    if args.dry_run:
        print("Dry run: nothing was written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
