"""Import goals from a Summit JSON export (or the same shape, hand-written).

    cd PROJECT_04/backend
    python -m scripts.import_data --email you@example.com mydata.json [--dry-run]

Only non-secret data is imported: goals, milestones, actions and check-ins. Milestones and
actions are attached to goals by title. Existing goals with the same title are skipped, so the
script can be run twice safely. Check-ins are skipped if a check-in already exists that day.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.config import Settings
from app.db import make_engine, make_sessionmaker, utcnow
from app.models import Checkin, Goal, Milestone, User, WeeklyAction
from app.timeutil import monday_of


def _date(value):
    return date.fromisoformat(value) if value else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a Summit JSON export")
    parser.add_argument("file", type=Path)
    parser.add_argument("--email", required=True, help="account that receives the data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("goals"), list):
        raise SystemExit("Not a Summit export: expected a 'goals' list.")

    # Export format: actions and check-ins are top-level lists keyed by goal title.
    # Hand-written format: both may be nested inside each goal instead.
    actions_by_goal: dict[str, list] = {}
    for item in payload.get("actions") or []:
        if isinstance(item, dict):
            actions_by_goal.setdefault(str(item.get("goal", "")).strip(), []).append(item)
    checkins_by_goal: dict[str, list] = {}
    for item in payload.get("checkins") or []:
        if isinstance(item, dict):
            checkins_by_goal.setdefault(str(item.get("goal", "")).strip(), []).append(item)

    settings = Settings()
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    counts = {"goals": 0, "milestones": 0, "actions": 0, "checkins": 0, "skipped": 0}
    with Session() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            raise SystemExit(f"No account with email {args.email!r}.")
        for raw in payload["goals"]:
            title = str(raw.get("title", "")).strip()
            if not title:
                counts["skipped"] += 1
                continue
            if db.scalar(select(Goal.id).where(Goal.user_id == user.id, Goal.title == title)):
                counts["skipped"] += 1
                continue
            goal = Goal(
                user_id=user.id,
                title=title[:160],
                description=str(raw.get("description", ""))[:4000],
                why=str(raw.get("why", ""))[:1200],
                category=raw.get("category") if raw.get("category") in ("career", "health", "learning", "finance", "personal", "creative") else "personal",
                status=raw.get("status") if raw.get("status") in ("active", "achieved", "paused", "archived") else "active",
                target_date=_date(raw.get("target_date")),
                created_at=utcnow(),
            )
            db.add(goal)
            db.flush()
            counts["goals"] += 1
            for position, m in enumerate(raw.get("milestones") or [], start=1):
                mtitle = str(m.get("title", "")).strip()
                if not mtitle:
                    continue
                db.add(
                    Milestone(
                        goal_id=goal.id,
                        title=mtitle[:160],
                        detail=str(m.get("detail", ""))[:1000],
                        due_date=_date(m.get("due_date")),
                        weight=max(1, min(5, int(m.get("weight", 1) or 1))),
                        position=position,
                        status="done" if m.get("status") == "done" else "open",
                        completed_at=utcnow() if m.get("status") == "done" else None,
                    )
                )
                counts["milestones"] += 1
            db.flush()
            for a in (raw.get("actions") or actions_by_goal.get(title, [])):
                atitle = str(a.get("title", "")).strip()
                if not atitle:
                    continue
                week = _date(a.get("week_start"))
                db.add(
                    WeeklyAction(
                        user_id=user.id,
                        goal_id=goal.id,
                        title=atitle[:200],
                        estimate_min=max(5, min(600, int(a.get("estimate_min", 45) or 45))),
                        week_start=monday_of(week) if week else monday_of(date.today()),
                        status=a.get("status") if a.get("status") in ("open", "done", "skipped") else "open",
                        source="manual",
                    )
                )
                counts["actions"] += 1
            for k in (raw.get("checkins") or checkins_by_goal.get(title, [])):
                day = _date(k.get("day"))
                if not day:
                    continue
                if db.scalar(select(Checkin.id).where(Checkin.goal_id == goal.id, Checkin.day == day)):
                    continue
                db.add(
                    Checkin(
                        user_id=user.id,
                        goal_id=goal.id,
                        day=day,
                        confidence=max(1, min(5, int(k.get("confidence", 3) or 3))),
                        note=str(k.get("note", ""))[:500],
                    )
                )
                counts["checkins"] += 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    engine.dispose()
    print(("Would import" if args.dry_run else "Imported") + ": " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
