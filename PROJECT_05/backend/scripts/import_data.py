"""Import habits from a Cadence JSON export (or the same shape, hand-written).

    cd PROJECT_05/backend
    python -m scripts.import_data --email you@example.com mydata.json [--dry-run]

Only non-secret data is imported: habits, their logs and weekly reflections. Habits are matched
by title; an existing habit with the same title is skipped, so the script can be run twice safely.
A log is skipped if that habit already has a log for the day. A reflection is skipped if the
account already has a reflection for that week.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.config import Settings
from app.db import make_engine, make_sessionmaker, utcnow
from app.models import Habit, HabitLog, Reflection, User
from app.timeutil import days_to_string, monday_of, parse_days


def _date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a Cadence JSON export")
    parser.add_argument("file", type=Path)
    parser.add_argument("--email", required=True, help="account that receives the data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("habits"), list):
        raise SystemExit("Not a Cadence export: expected a 'habits' list.")

    settings = Settings()
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    counts = {"habits": 0, "logs": 0, "reflections": 0, "skipped": 0}
    today = date.today()

    with Session() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            raise SystemExit(f"No account with email {args.email!r}.")

        for raw in payload["habits"]:
            if not isinstance(raw, dict):
                counts["skipped"] += 1
                continue
            title = str(raw.get("title", "")).strip()
            if not title:
                counts["skipped"] += 1
                continue
            if db.scalar(select(Habit.id).where(Habit.user_id == user.id, Habit.title == title)):
                counts["skipped"] += 1
                continue

            status = raw.get("status") if raw.get("status") in ("active", "paused", "archived") else "active"
            habit = Habit(
                user_id=user.id,
                title=title[:120],
                intention=str(raw.get("intention", ""))[:1000],
                cue=str(raw.get("cue", ""))[:160],
                days=days_to_string(parse_days(str(raw.get("days", "")))),
                status=status,
                created_at=utcnow(),
                archived_at=utcnow() if status == "archived" else None,
            )
            db.add(habit)
            db.flush()
            counts["habits"] += 1

            for item in raw.get("logs") or []:
                if not isinstance(item, dict):
                    continue
                day = _date(item.get("day"))
                if day is None or day > today:
                    continue
                if db.scalar(select(HabitLog.id).where(HabitLog.habit_id == habit.id, HabitLog.day == day)):
                    continue
                log_status = "skipped" if item.get("status") == "skipped" else "done"
                db.add(
                    HabitLog(
                        user_id=user.id,
                        habit_id=habit.id,
                        day=day,
                        status=log_status,
                        note=str(item.get("note", ""))[:300],
                        created_at=utcnow(),
                    )
                )
                counts["logs"] += 1

        for raw in payload.get("reflections") or []:
            if not isinstance(raw, dict):
                continue
            week = _date(raw.get("week_start"))
            if week is None:
                continue
            week = monday_of(week)
            if week > today:
                continue
            if db.scalar(select(Reflection.id).where(Reflection.user_id == user.id, Reflection.week_start == week)):
                continue
            db.add(
                Reflection(
                    user_id=user.id,
                    week_start=week,
                    mood=max(1, min(5, int(raw.get("mood", 3) or 3))),
                    worked=str(raw.get("worked", ""))[:2000],
                    friction=str(raw.get("friction", ""))[:2000],
                    change=str(raw.get("change", ""))[:2000],
                    created_at=utcnow(),
                )
            )
            counts["reflections"] += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    engine.dispose()
    print(("Would import" if args.dry_run else "Imported") + ": " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
