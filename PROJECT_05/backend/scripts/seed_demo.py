"""Create a DEMO account with eight weeks of habit history (screenshots and first-run tours).

    cd PROJECT_05/backend
    python -m scripts.seed_demo [--tz Asia/Kolkata]

Everything created here is demo data:
  * account  demo@cadence.example / password "cadence-demo" (local use only), shown as "Swayam"
  * habits, logs and weekly reflections are sample data
  * streaks, reports and charts are computed from those logs by the app's own logic
Running it again wipes and recreates the demo account only.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.main import run_migrations
from app.models import Habit, HabitLog, Reflection, Suggestion, User
from app.security import hash_password
from app.services import coach
from app.timeutil import local_today, monday_of, parse_days, zone

DEMO_EMAIL = "demo@cadence.example"
DEMO_PASSWORD = "cadence-demo"


def _at(day: date, hour: int, tz, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=tz).astimezone(timezone.utc)


def _recent_scheduled(habit: Habit, today: date, count: int) -> set[date]:
    """The most recent `count` scheduled days, walking backwards from today."""
    days = {d for d in parse_days(habit.days)}
    found: set[date] = set()
    cursor = today
    while cursor > today - timedelta(days=90) and len(found) < count:
        if cursor.weekday() in days:
            found.add(cursor)
        cursor -= timedelta(days=1)
    return found


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
    this_monday = monday_of(today)

    with Session() as db:
        db.execute(delete(User).where(User.email == DEMO_EMAIL))
        db.commit()
        user = User(email=DEMO_EMAIL, name="Swayam", password_hash=hash_password(DEMO_PASSWORD), timezone=args.tz)
        db.add(user)
        db.flush()

        start = today - timedelta(days=63)
        read = Habit(
            user_id=user.id,
            title="Read 20 minutes",
            intention="I want to think in longer sentences than a feed allows.",
            cue="After I put the kettle on",
            days="0,1,2,3,4,5,6",
            status="active",
            created_at=_at(start, 7, tz),
        )
        walk = Habit(
            user_id=user.id,
            title="Morning walk",
            intention="Daylight before screens changes the whole morning.",
            cue="After brushing my teeth",
            days="0,1,2,3,4",
            status="active",
            created_at=_at(start, 7, tz),
        )
        journal = Habit(
            user_id=user.id,
            title="Evening journal",
            intention="Three lines is enough to stop the day from blurring.",
            cue="Before I charge my phone",
            days="0,1,2,3,4,5,6",
            status="active",
            created_at=_at(start + timedelta(days=10), 7, tz),
        )
        strength = Habit(
            user_id=user.id,
            title="Strength training",
            intention="Stay strong enough for the long run, not for a mirror.",
            cue="After the walk, before the shower",
            days="0,2,4",
            status="active",
            created_at=_at(start, 7, tz),
        )
        paused = Habit(
            user_id=user.id,
            title="No phone with breakfast",
            intention="Breakfast is the one meal that does not need a screen.",
            cue="Phone stays in the hallway until the plate is clear",
            days="0,1,2,3,4",
            status="paused",
            created_at=_at(start - timedelta(days=20), 7, tz),
        )
        archived = Habit(
            user_id=user.id,
            title="Morning pages",
            intention="Too much for this season; reading replaced it.",
            cue="Before coffee",
            days="0,1,2,3,4",
            status="archived",
            created_at=_at(start - timedelta(days=40), 7, tz),
        )
        habits = [read, walk, journal, strength, paused, archived]
        db.add_all(habits)
        db.flush()

        # A real-feeling but deterministic pattern per habit: done, planned rest, or missed.
        reliability = {read.id: 0.90, walk.id: 0.84, journal.id: 0.78, strength.id: 0.55}
        forced_runs = {read.id: 16, walk.id: 7, journal.id: 5}
        planned: dict[tuple[int, date], str] = {}

        for habit in habits:
            created = habit.created_at.date()
            scheduled_days = set(parse_days(habit.days))
            run_days = _recent_scheduled(habit, today, forced_runs.get(habit.id, 0))
            cursor = created
            while cursor <= today:
                if cursor.weekday() not in scheduled_days:
                    cursor += timedelta(days=1)
                    continue
                if habit.status == "archived" and cursor > today - timedelta(days=9):
                    cursor += timedelta(days=1)
                    continue
                if habit.status == "paused" and cursor > today - timedelta(days=24):
                    cursor += timedelta(days=1)
                    continue
                if habit.id in forced_runs and cursor in run_days:
                    status = "done"
                else:
                    roll = (habit.id * 31 + cursor.toordinal() * 17) % 100
                    threshold = int(reliability.get(habit.id, 0.7) * 100)
                    if roll < 5:
                        status = "skipped"
                    elif roll < threshold:
                        status = "done"
                    else:
                        status = "missed"
                if status != "missed":
                    planned[(habit.id, cursor)] = status
                cursor += timedelta(days=1)

        # Today: two done, one still open, so the dashboard has something to act on.
        planned[(read.id, today)] = "done"
        planned.pop((journal.id, today), None)

        for (habit_id, day), status in planned.items():
            db.add(
                HabitLog(
                    user_id=user.id,
                    habit_id=habit_id,
                    day=day,
                    status=status,
                    note="",
                    created_at=_at(day, 20, tz),
                )
            )

        # Local coach notes, so the detail pages are populated on first load.
        db.flush()
        read_logs = list(db.scalars(select(HabitLog).where(HabitLog.habit_id == read.id)))
        strength_logs = list(db.scalars(select(HabitLog).where(HabitLog.habit_id == strength.id)))
        for habit, logs in ((read, read_logs), (strength, strength_logs)):
            for suggestion in coach.rule_suggestions(habit, logs, today, limit=2):
                db.add(
                    Suggestion(
                        user_id=user.id,
                        habit_id=habit.id,
                        title=suggestion.title,
                        rationale=suggestion.rationale,
                        source="local",
                        created_at=_at(today - timedelta(days=1), 21, tz),
                    )
                )

        # Past reflections: seven consecutive weeks, leaving this week open for the demo form.
        reflections = [
            ("Kept the reading cue after the kettle; it is starting to feel automatic.", "Strength keeps losing to meetings on Wednesdays.", "Move strength to Tuesday and Friday for one week."),
            ("The walk is easier when shoes are by the door.", "Journaling slipped on the two late nights.", "Write before dinner on late-work days."),
            ("Reading is the most reliable part of the day now.", "Too many seven-day plans, not enough rest.", "Keep Saturday as a deliberate rest day."),
            ("The shorter walk still counts. That was the useful lesson.", "Phone at breakfast crept back in.", "Leave the phone charging in the hallway overnight."),
            ("Two strength sessions happened because they were on the calendar.", "Sunday planning was rushed.", "Spend ten minutes on Sunday choosing the week's three priorities."),
            ("Journaling helped me notice the good days, not just the misses.", "I tried to make up missed days instead of letting them go.", "Never double up. The next scheduled day is enough."),
            ("The first week where the routine felt boring in a good way.", "I still negotiate with the alarm.", "Put the alarm across the room and keep the cue the same."),
        ]
        for index, (worked, friction, change) in enumerate(reflections, start=1):
            week = this_monday - timedelta(days=7 * index)
            db.add(
                Reflection(
                    user_id=user.id,
                    week_start=week,
                    mood=[4, 3, 5, 3, 4, 2, 4][index - 1],
                    worked=worked,
                    friction=friction,
                    change=change,
                    created_at=_at(week + timedelta(days=6), 18, tz),
                )
            )

        db.commit()
        print(f"Demo account ready: {DEMO_EMAIL} (timezone {args.tz}) with 8 weeks of history")
        print("Sign in with the password documented at the top of scripts/seed_demo.py.")
    engine.dispose()


if __name__ == "__main__":
    main()
