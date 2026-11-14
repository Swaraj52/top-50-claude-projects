"""Import meetings from a Quorum JSON export (or the same shape, hand-written).

    cd PROJECT_06/backend
    python -m scripts.import_data --email you@example.com mydata.json [--dry-run]

Only non-secret data is imported: meetings, decisions and follow-ups. A meeting is matched by
title and date; an identical meeting is skipped, so the script can be run twice safely. When a
meeting has notes but no summary, the app's own extractor fills in the summary, decisions and
actions that the export is missing.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.config import Settings
from app.db import make_engine, make_sessionmaker, utcnow
from app.models import ActionItem, Decision, Meeting, User
from app.services.extract import extract


def _date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a Quorum JSON export")
    parser.add_argument("file", type=Path)
    parser.add_argument("--email", required=True, help="account that receives the data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("meetings"), list):
        raise SystemExit("Not a Quorum export: expected a 'meetings' list.")

    settings = Settings()
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    counts = {"meetings": 0, "decisions": 0, "actions": 0, "skipped": 0}

    with Session() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            raise SystemExit(f"No account with email {args.email!r}.")

        for raw in payload["meetings"]:
            if not isinstance(raw, dict):
                counts["skipped"] += 1
                continue
            title = _text(raw.get("title"), 160)
            occurred_on = _date(raw.get("occurred_on"))
            if len(title) < 3 or occurred_on is None:
                counts["skipped"] += 1
                continue
            if db.scalar(
                select(Meeting.id).where(
                    Meeting.user_id == user.id,
                    Meeting.title == title,
                    Meeting.occurred_on == occurred_on,
                )
            ):
                counts["skipped"] += 1
                continue

            notes = str(raw.get("notes", ""))[:60_000]
            attendees = _text(raw.get("attendees"), 600)
            summary = _text(raw.get("summary"), 800)
            source = raw.get("source") if raw.get("source") in ("local", "claude") else "local"
            result = extract(notes, attendees, occurred_on)
            summary = summary or result.summary

            meeting = Meeting(
                user_id=user.id,
                title=title,
                occurred_on=occurred_on,
                attendees=attendees,
                notes=notes,
                summary=summary,
                source=source,
                model=_text(raw.get("model"), 80) if source == "claude" else None,
                extract_note=_text(raw.get("extract_note"), 300),
            )
            db.add(meeting)
            db.flush()
            counts["meetings"] += 1

            decisions = raw.get("decisions") or []
            if not decisions:
                decisions = [{"text": text, "status": "agreed"} for text in result.decisions]
            for item in decisions:
                if isinstance(item, str):
                    text, status = item, "agreed"
                elif isinstance(item, dict):
                    text = _text(item.get("text"), 450)
                    status = item.get("status") if item.get("status") in ("agreed", "revisit") else "agreed"
                else:
                    continue
                text = _text(text, 450)
                if len(text) < 3:
                    continue
                db.add(
                    Decision(
                        user_id=user.id,
                        meeting_id=meeting.id,
                        text=text,
                        status=status,
                        decided_on=occurred_on,
                    )
                )
                counts["decisions"] += 1

            actions = raw.get("actions") or []
            if not actions:
                actions = [
                    {"title": draft.title, "owner": draft.owner, "due_date": draft.due_date}
                    for draft in result.actions
                ]
            for item in actions:
                if not isinstance(item, dict):
                    continue
                action_title = _text(item.get("title"), 280)
                if len(action_title) < 3:
                    continue
                status = item.get("status") if item.get("status") in ("open", "done") else "open"
                db.add(
                    ActionItem(
                        user_id=user.id,
                        meeting_id=meeting.id,
                        title=action_title,
                        owner=_text(item.get("owner"), 80),
                        due_date=_date(item.get("due_date")),
                        status=status,
                        completed_at=utcnow() if status == "done" else None,
                    )
                )
                counts["actions"] += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    engine.dispose()
    print(("Would import" if args.dry_run else "Imported") + ": " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
