"""Create a DEMO account with eight weeks of history (screenshots and first-run tours).

    cd PROJECT_04/backend
    python -m scripts.seed_demo [--tz Asia/Kolkata]

Everything created here is demo data:
  * account  demo@summit.example / password "summit-demo" (local use only), shown as "Swayam"
  * goals, milestones, weekly actions and check-ins are sample data
  * insights are computed from those actions by the app's own logic, so the charts are real
Running it again wipes and recreates the demo account only.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.main import run_migrations
from app.models import Checkin, Goal, Milestone, User, WeeklyAction
from app.security import hash_password
from app.timeutil import local_today, monday_of, zone

DEMO_EMAIL = "demo@summit.example"
DEMO_PASSWORD = "summit-demo"


def _at(day: date, hour: int, tz, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=tz).astimezone(timezone.utc)


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
        user = User(email=DEMO_EMAIL, name="Swayam", password_hash=hash_password(DEMO_PASSWORD), timezone=args.tz, weekly_capacity_min=360)
        db.add(user)
        db.flush()

        def goal(title, category, why, description, target_in, created_back, milestones, status="active"):
            g = Goal(
                user_id=user.id,
                title=title,
                category=category,
                why=why,
                description=description,
                target_date=today + timedelta(days=target_in) if target_in is not None else None,
                created_at=_at(today - timedelta(days=created_back), 9, tz),
                status=status,
                achieved_at=_at(today - timedelta(days=6), 18, tz) if status == "achieved" else None,
            )
            db.add(g)
            db.flush()
            for position, (mtitle, weight, done, due_in, detail) in enumerate(milestones, start=1):
                db.add(
                    Milestone(
                        goal_id=g.id,
                        title=mtitle,
                        weight=weight,
                        position=position,
                        detail=detail,
                        due_date=today + timedelta(days=due_in) if due_in is not None else None,
                        status="done" if done else "open",
                        completed_at=_at(today - timedelta(days=max(1, due_in or 1) + 2), 17, tz) if done else None,
                        created_at=_at(today - timedelta(days=created_back), 9, tz),
                    )
                )
            db.flush()
            return g

        run = goal(
            "Run a half marathon",
            "health",
            "I want to still be running when I am sixty.",
            "Build to 21.1 km with three runs a week, no heroics.",
            75,
            120,
            [
                ("Run 5 km without stopping", 2, True, -80, "The first real threshold."),
                ("Run 10 km without stopping", 3, True, -35, "Slow and steady."),
                ("Complete a 15 km long run", 3, False, 18, "Long run on a Sunday morning."),
                ("Race-day dress rehearsal", 2, False, 55, "Full kit, race pace for 5 km."),
            ],
        )
        site = goal(
            "Ship the portfolio site",
            "career",
            "A recruiter should understand what I do in ninety seconds.",
            "Five case studies, a working contact form and fast pages.",
            24,
            65,
            [
                ("Choose three case studies", 2, True, -20, "Depth over volume."),
                ("Write the case study drafts", 3, False, 7, "Problem, decisions, result."),
                ("Build and deploy the site", 3, False, 16, "Static, accessible, quick."),
                ("Ask two peers for a critique", 1, False, 20, "Fresh eyes before launch."),
            ],
        )
        books = goal(
            "Read 12 books this year",
            "learning",
            "Reading is how I keep my thinking from shrinking.",
            "Non-fiction and fiction in equal measure.",
            None,
            280,
            [
                ("Four books", 1, True, -200, ""),
                ("Six books", 1, True, -160, ""),
                ("Eight books", 1, True, -90, ""),
                ("Ten books", 1, False, None, ""),
                ("Twelve books", 1, False, None, ""),
            ],
        )
        goal(
            "Complete a 30-day writing sprint",
            "creative",
            "Publishing daily broke the perfectionism loop.",
            "Thirty short essays, published whether or not they were good.",
            None,
            90,
            [("Fifteen essays", 2, True, -60, ""), ("Thirty essays", 2, True, -12, "")],
            status="achieved",
        )

        # Eight weeks of actions. Counts vary so the trend charts are honest-looking but real.
        done_counts = [3, 4, 2, 5, 4, 5, 4]
        titles = [
            ("Easy 5 km", 30), ("Long run", 75), ("Strength session", 30),
            ("Draft a case study", 60), ("Fix the contact form", 45), ("Outline the homepage", 30),
            ("Read 40 pages", 30), ("Write a book note", 20),
        ]
        for back in range(7, 0, -1):
            monday = this_monday - timedelta(days=7 * back)
            count = done_counts[7 - back] if back <= 7 else 3
            goals = [run, site, books]
            for i in range(count + 1):
                g = goals[i % 3]
                title, estimate = titles[i % len(titles)]
                done = i < count
                db.add(
                    WeeklyAction(
                        user_id=user.id,
                        goal_id=g.id,
                        title=title,
                        estimate_min=estimate,
                        week_start=monday,
                        status="done" if done else "open",
                        source="manual",
                        done_at=_at(monday + timedelta(days=min(5, i)), 18, tz) if done else None,
                        created_at=_at(monday, 9, tz),
                    )
                )

        current = [
            (run, "15 km long run on Sunday", 90, "open"),
            (run, "Two easy 5 km runs", 60, "done"),
            (site, "Finish the case study drafts", 90, "open"),
            (site, "Book a critique with Priya", 20, "done"),
            (books, "Read 40 pages of the current book", 30, "done"),
            (books, "Write one book note", 20, "open"),
        ]
        for g, title, estimate, status in current:
            db.add(
                WeeklyAction(
                    user_id=user.id,
                    goal_id=g.id,
                    title=title,
                    estimate_min=estimate,
                    week_start=this_monday,
                    status=status,
                    source="manual",
                    done_at=_at(today, 12, tz) if status == "done" else None,
                    created_at=_at(this_monday, 9, tz),
                )
            )
        db.add(
            WeeklyAction(
                user_id=user.id,
                goal_id=run.id,
                title="Choose scope over speed: protect the long run",
                estimate_min=30,
                week_start=this_monday,
                status="open",
                source="coach",
                created_at=_at(today, 8, tz),
            )
        )

        # Check-ins: a four-day streak with one honest dip.
        notes = {
            run: ["Legs felt heavy but the long run held together.", "Missed Tuesday; the plan still fits.", "Confidence is rising."],
            site: ["The drafts are slower than expected.", "Priya's critique will help; booked it.", "Scope keeps growing. Cut it."],
            books: ["Reading before bed instead of scrolling.", "A good week for fiction."],
        }
        for back in range(0, 5):
            day = today - timedelta(days=back)
            if back == 4:
                continue
            for idx, g in enumerate([run, site, books]):
                note = notes[g][back % len(notes[g])]
                confidence = 4 if back in (0, 1, 3) else (2 if back == 2 and idx == 1 else 3)
                db.add(Checkin(user_id=user.id, goal_id=g.id, day=day, confidence=confidence, note=note, created_at=_at(day, 19, tz)))

        # Earlier weeks: two check-ins per goal per week so the confidence chart
        # has eight real weekly averages instead of a single point.
        history = {
            run: [3, 3, 4, 3, 4, 4, 3],
            site: [2, 3, 3, 2, 3, 3, 3],
            books: [4, 3, 4, 4, 3, 4, 4],
        }
        for back in range(7, 0, -1):
            monday = this_monday - timedelta(days=7 * back)
            for g, values in history.items():
                confidence = values[7 - back]
                for offset in (1, 4):
                    day = monday + timedelta(days=offset)
                    db.add(
                        Checkin(
                            user_id=user.id,
                            goal_id=g.id,
                            day=day,
                            confidence=confidence,
                            note=notes[g][(back + offset) % len(notes[g])],
                            created_at=_at(day, 19, tz),
                        )
                    )
        db.commit()
        print(f"Demo account ready: {DEMO_EMAIL} (timezone {args.tz}) with 8 weeks of history")
        print("Sign in with the password documented at the top of scripts/seed_demo.py.")
    engine.dispose()


if __name__ == "__main__":
    main()
