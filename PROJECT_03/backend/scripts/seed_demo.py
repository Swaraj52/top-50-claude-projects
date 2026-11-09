"""Create a DEMO account with two weeks of history (for screenshots and trying the app).

    cd PROJECT_03/backend
    python -m scripts.seed_demo [--tz Asia/Kolkata]

Everything created here is demo data:
  * account  demo@shutdown.example / password "shutdown-demo" (local use only), shown as "Swayam"
  * past days' tasks, log entries, check-ins and blockers are sample data; each past day's review
    is produced by the real planner and rule-based reviewer, so the History and Trends pages show
    genuine output of the app's own logic
  * today has unfinished work and no review yet, so the shutdown flow can be tried end to end
Running it again wipes and recreates the demo account only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import delete

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.main import run_migrations
from app.models import Blocker, Checkin, LogEntry, Review, Task, User
from app.security import hash_password
from app.services import planner, reviewer
from app.services.day import recurring_blockers, snapshot
from app.timeutil import local_today, zone

DEMO_EMAIL = "demo@shutdown.example"
DEMO_PASSWORD = "shutdown-demo"

PAST_WORK = [
    ("Fix login redirect bug", "code", 60), ("Review Priya's pull request", "code", 30), ("Draft Q4 roadmap", "writing", 90),
    ("Weekly 1:1 notes", "meetings", 30), ("Expense report", "admin", 20), ("Write API docs for /tasks", "writing", 60),
    ("Pair on caching layer", "code", 90), ("Interview: backend candidate", "meetings", 60), ("Refactor settings page", "code", 45),
    ("Customer call follow-up", "admin", 30), ("Blog post outline", "writing", 45), ("Upgrade dependencies", "code", 60),
]
WINS = ["Demo went smoothly", "Closed three bugs before lunch", "Got approval for the roadmap", "Mentored a new teammate"]
LEARNINGS = ["Batching email twice a day saves an hour", "Tests first made the refactor painless", "Morning blocks beat afternoon ones"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tz", default="Asia/Kolkata")
    args = parser.parse_args()

    settings = Settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    tz = zone(args.tz)
    today = local_today(tz)

    def at(day, hour, minute=0):
        return datetime.combine(day, time(hour, minute), tzinfo=tz).astimezone(timezone.utc)

    with Session() as db:
        db.execute(delete(User).where(User.email == DEMO_EMAIL))
        db.commit()
        user = User(email=DEMO_EMAIL, name="Swayam", password_hash=hash_password(DEMO_PASSWORD), timezone=args.tz, capacity_hours=6)
        db.add(user)
        db.flush()

        # Two weeks of history, simulated day by day: some work is left unfinished each evening,
        # the app's own planner + reviewer write that evening's review, and the leftovers are
        # finished the next working morning.
        leftovers: list[Task] = []
        for back in range(13, 0, -1):
            day = today - timedelta(days=back)
            weekend = day.weekday() >= 5
            if not weekend:
                for t in leftovers:
                    t.status, t.completed_at = "done", at(day, 9, 40)
                leftovers = []
            n_done = 0 if weekend else 2 + (back * 7) % 4
            for i in range(n_done):
                title, area, est = PAST_WORK[(back * 3 + i) % len(PAST_WORK)]
                db.add(Task(user_id=user.id, title=title, area=area, estimate_min=est, priority=1 + (i % 3), status="done",
                            planned_for=day, completed_at=at(day, 10 + i, 15), created_at=at(day, 9)))
            if not weekend:
                db.add(LogEntry(user_id=user.id, day=day, kind="win", text=WINS[back % len(WINS)], created_at=at(day, 17)))
                if back % 3 == 0:
                    db.add(LogEntry(user_id=user.id, day=day, kind="learning", text=LEARNINGS[back % len(LEARNINGS)], created_at=at(day, 17, 30)))
                db.add(Checkin(user_id=user.id, day=day, energy=2 + (back * 5) % 4, mood=2 + (back * 2) % 4 if back % 4 else 4, focus_hours=1.5 + (back * 7 % 5) * 0.75))
            if not weekend:
                for j in range(1 + back % 2):
                    title, area, est = PAST_WORK[(back * 5 + j + 7) % len(PAST_WORK)]
                    t = Task(user_id=user.id, title=title, area=area, estimate_min=est, priority=1 + j, status="todo",
                             planned_for=day, created_at=at(day, 9))
                    db.add(t)
                    leftovers.append(t)
            db.flush()
            if not weekend:
                snap = snapshot(db, user, day, tz)
                tomorrow = day + timedelta(days=1)
                plan, load, over = planner.build_plan(planner.candidates(db, user, tomorrow, {}), snap.capacity_min, tomorrow)
                carried = [t.id for t in snap.open_today]
                for t in snap.open_today:
                    t.carry_count += 1
                    t.planned_for = tomorrow
                content = reviewer.rule_review(snap, plan, recurring_blockers(db, user, day), len(carried))
                db.add(Review(user_id=user.id, day=day, source="rule", content=content, committed=True, created_at=at(day, 18, 30),
                              notes="Protect the morning block." if back % 4 == 0 else "",
                              plan={"decisions": {}, "items": [p.as_dict() for p in plan], "load_min": load, "capacity_min": snap.capacity_min,
                                    "over_capacity": over, "carried_ids": carried, "applied_carry_ids": carried}))

        db.add(Blocker(user_id=user.id, text="Waiting for API access from the platform team", opened_on=today - timedelta(days=11), resolved_on=today - timedelta(days=9)))
        db.add(Blocker(user_id=user.id, text="Waiting for API access for the staging env", opened_on=today - timedelta(days=5)))
        db.add(Blocker(user_id=user.id, text="Design sign-off for the settings page", opened_on=today))

        # Today: some done, some open (a few carried over), plus backlog and tomorrow.
        for title, area, prio, est, carry, status in [
            ("Write migration for reviews table", "code", 1, 90, 2, "doing"),
            ("Reply to the hiring manager", "admin", 2, 20, 0, "todo"),
            ("Prepare demo for Friday", "writing", 1, 60, 1, "todo"),
            ("Clean up old feature flags", "code", 3, 45, 3, "todo"),
        ]:
            db.add(Task(user_id=user.id, title=title, area=area, priority=prio, estimate_min=est, carry_count=carry, status=status,
                        planned_for=today, created_at=at(today, 9) - timedelta(days=carry), due_date=today + timedelta(days=2) if "demo" in title else None))
        for title, area, est, hour in [("Fix flaky checkout test", "code", 45, 11), ("Standup notes", "meetings", 15, 10)]:
            db.add(Task(user_id=user.id, title=title, area=area, estimate_min=est, status="done", planned_for=today, completed_at=at(today, hour), created_at=at(today, 9)))
        db.add(Task(user_id=user.id, title="Read the observability RFC", area="learning", priority=3, estimate_min=30, planned_for=None))
        db.add(Task(user_id=user.id, title="Quarterly self-review", area="writing", priority=2, estimate_min=60, planned_for=today + timedelta(days=1)))
        db.add(LogEntry(user_id=user.id, day=today, kind="done", text="Paired with Arjun on the payment webhook", minutes=50, created_at=at(today, 12)))
        db.add(LogEntry(user_id=user.id, day=today, kind="win", text="Checkout test finally green on CI", created_at=at(today, 13)))
        db.add(LogEntry(user_id=user.id, day=today, kind="learning", text="Retries hide timing bugs; fix the race instead", created_at=at(today, 15)))
        db.commit()
        print(f"Demo account ready: {DEMO_EMAIL} (timezone {args.tz}) with 13 days of history")
        print("Sign in with the password documented at the top of scripts/seed_demo.py.")
    engine.dispose()


if __name__ == "__main__":
    main()
