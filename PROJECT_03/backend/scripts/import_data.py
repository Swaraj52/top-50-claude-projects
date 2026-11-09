"""Load the owner's own data (given in chat or prepared as JSON) into their account.

    cd PROJECT_03/backend
    python -m scripts.import_data --email you@example.com mydata.json

The account must already exist (register in the app first; the password never leaves you).
JSON shape (every section optional):

{
  "settings": {"name": "Swayam", "timezone": "Asia/Kolkata", "capacity_hours": 6},
  "tasks": [{"title": "Prepare slides", "area": "work", "priority": 1, "estimate_min": 60,
             "when": "today" | "tomorrow" | "backlog" | "YYYY-MM-DD", "due_date": "YYYY-MM-DD"}],
  "blockers": [{"text": "Waiting for lab access"}]
}
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.main import run_migrations
from app.models import Blocker, Task, User
from app.timeutil import is_valid_timezone, local_today, zone


class ImportError_(ValueError):
    pass


def apply(db: DbSession, email: str, payload: dict) -> dict:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise ImportError_(f"No account for {email}. Register in the app first.")
    counts = {"tasks": 0, "blockers": 0, "settings": 0}

    s = payload.get("settings") or {}
    if "name" in s:
        name = " ".join(str(s["name"]).split())
        if not 1 <= len(name) <= 80:
            raise ImportError_("settings.name must be 1-80 characters")
        user.name = name
        counts["settings"] += 1
    if "timezone" in s:
        if not is_valid_timezone(str(s["timezone"])):
            raise ImportError_(f"Unknown timezone {s['timezone']!r}")
        user.timezone = str(s["timezone"])
        counts["settings"] += 1
    if "capacity_hours" in s:
        hours = float(s["capacity_hours"])
        if not 0.5 <= hours <= 16:
            raise ImportError_("settings.capacity_hours must be 0.5-16")
        user.capacity_hours = hours
        counts["settings"] += 1

    today = local_today(zone(user.timezone))
    for i, t in enumerate(payload.get("tasks") or []):
        title = " ".join(str(t.get("title", "")).split())[:200]
        if not title:
            raise ImportError_(f"tasks[{i}] needs a title")
        when = str(t.get("when", "today"))
        planned = {"today": today, "tomorrow": today + timedelta(days=1), "backlog": None}.get(when)
        if when not in ("today", "tomorrow", "backlog"):
            planned = date.fromisoformat(when)
        db.add(Task(
            user_id=user.id, title=title, area=" ".join(str(t.get("area", "")).split()).lower()[:40],
            priority=min(max(int(t.get("priority", 2)), 1), 3), estimate_min=min(max(int(t.get("estimate_min", 30)), 5), 480),
            planned_for=planned, due_date=date.fromisoformat(t["due_date"]) if t.get("due_date") else None,
        ))
        counts["tasks"] += 1
    for i, b in enumerate(payload.get("blockers") or []):
        text = " ".join(str(b.get("text", "")).split())[:300]
        if not text:
            raise ImportError_(f"blockers[{i}] needs text")
        db.add(Blocker(user_id=user.id, text=text, opened_on=today))
        counts["blockers"] += 1
    db.commit()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import your tasks, blockers and settings")
    parser.add_argument("--email", required=True)
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    settings = Settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    try:
        with make_sessionmaker(engine)() as db:
            counts = apply(db, args.email, json.loads(args.file.read_text(encoding="utf-8")))
    except (ImportError_, ValueError, KeyError) as exc:
        print(f"Import failed, nothing was saved: {exc}")
        return 1
    finally:
        engine.dispose()
    print(f"Imported {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
