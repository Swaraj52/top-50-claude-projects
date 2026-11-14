"""Create a DEMO account with a realistic meeting archive (screenshots and first-run tours).

    cd PROJECT_06/backend
    python -m scripts.seed_demo

Everything created here is demo data:
  * account  demo@quorum.example / password "quorum-demo" (local use only), shown as "Swayam"
  * meetings, decisions and follow-ups are invented but internally consistent
  * the summary, decisions and actions in each meeting are produced by the app's own local
    extractor from the notes below, not typed in by hand
Running it again wipes and recreates the demo account only.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from sqlalchemy import delete

from app.config import Settings
from app.db import make_engine, make_sessionmaker, utcnow
from app.main import run_migrations
from app.models import ActionItem, Decision, Meeting, User
from app.security import hash_password
from app.services.extract import extract
from app.timeutil import local_today, zone

DEMO_EMAIL = "demo@quorum.example"
DEMO_PASSWORD = "quorum-demo"


def _notes(summary: str, decisions: list[str], attendees: list[str], actions: list[str]) -> str:
    lines = ["", "Attendees: " + ", ".join(attendees), "", f"Summary: {summary}", "", "Decisions:"]
    lines += [f"- {item}" for item in decisions]
    lines += ["", "Action items:"]
    lines += [f"- {item}" for item in actions]
    return "\n".join(lines).strip() + "\n"


def _archive(today: date) -> list[dict]:
    iso = date.isoformat

    def days_ago(n: int) -> str:
        return iso(today - timedelta(days=n))

    def days_ahead(n: int) -> str:
        return iso(today + timedelta(days=n))

    return [
        {
            "title": "Weekly product review",
            "day": today - timedelta(days=14),
            "attendees": ["Priya", "Arjun", "Meera"],
            "summary": "We reviewed the beta scope and agreed the onboarding flow is the critical path. "
            "The December date holds as long as the pricing page does not expand again.",
            "decisions": [
                "Ship the beta on 1 December",
                "Keep pricing on a single page",
            ],
            "actions": [
                f"@Priya send the onboarding deck by {days_ago(11)}",
                f"Arjun will draft the migration note by {days_ago(8)}",
                f"@Meera audit the empty states by {days_ago(6)}",
            ],
            "done": [0, 2],
        },
        {
            "title": "Pricing and packaging",
            "day": today - timedelta(days=11),
            "attendees": ["Priya", "Meera", "Dev"],
            "summary": "We compared seat-based and usage-based pricing. Seat-based is easier to explain "
            "at launch; usage-based is worth revisiting after the first cohort.",
            "decisions": [
                "Launch with seat-based pricing",
                "Revisit usage-based pricing next quarter",
                "Do not add an enterprise tier before January",
            ],
            "actions": [
                f"@Meera build the pricing comparison by {days_ago(7)}",
                f"Dev will update the billing copy by {days_ago(4)}",
            ],
            "done": [0, 1],
            "revisit": "Revisit usage-based pricing next quarter",
        },
        {
            "title": "Design critique: onboarding",
            "day": today - timedelta(days=7),
            "attendees": ["Meera", "Priya", "Sana"],
            "summary": "The first-run flow is close. We cut one step, moved the workspace name later, and "
            "agreed the empty state needs a real example instead of an illustration.",
            "decisions": [
                "Cut the invite step from first-run onboarding",
                "Use a filled example workspace in the empty state",
            ],
            "actions": [
                f"@Meera ship the reduced flow by {days_ago(4)}",
                f"Sana will record the new onboarding walkthrough by {days_ahead(2)}",
            ],
            "done": [0],
        },
        {
            "title": "Customer call: Northwind",
            "day": today - timedelta(days=4),
            "attendees": ["Arjun", "Priya"],
            "summary": "Northwind runs three weekly planning meetings and loses the decisions in chat. "
            "They want a searchable archive more than another task tracker.",
            "decisions": [
                "Offer Northwind a beta seat for their operations team",
                "Prioritise search over integrations this quarter",
            ],
            "actions": [
                f"@Arjun send the beta invite by {days_ahead(1)}",
                f"@Priya write up the Northwind notes by {days_ago(2)}",
                "Follow up with their security questionnaire",
            ],
            "done": [1],
        },
        {
            "title": "Beta launch readiness",
            "day": today - timedelta(days=1),
            "attendees": ["Priya", "Arjun", "Dev", "Meera"],
            "summary": "Final readiness pass before the beta. Analytics, status page and the support inbox "
            "are the only open items. No blockers on the application itself.",
            "decisions": [
                "Run the launch checklist on Friday",
                "Invite the first twenty design partners",
            ],
            "actions": [
                f"@Priya update the status page by {iso(today)}",
                f"Dev will wire the analytics events by {days_ahead(2)}",
                f"@Arjun book the launch review by {days_ahead(4)}",
                f"@Meera prepare the support macros by {days_ahead(3)}",
            ],
            "done": [],
        },
        {
            "title": "Weekly product review",
            "day": today,
            "attendees": ["Priya", "Arjun", "Meera", "Dev"],
            "summary": "Short check-in. The beta is ready except for analytics. We agreed to freeze scope "
            "until the first partner cohort has used it for a week.",
            "decisions": [
                "Freeze scope until the first cohort has used the beta for a week",
                "Keep the weekly review on Thursday",
            ],
            "actions": [
                f"@Dev finish the analytics events by {days_ahead(2)}",
                f"@Priya share the partner list by {days_ahead(1)}",
                "Draft the beta welcome email",
            ],
            "done": [],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tz", default="Asia/Kolkata")
    args = parser.parse_args()

    settings = Settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    today = local_today(zone(args.tz))

    with Session() as db:
        db.execute(delete(User).where(User.email == DEMO_EMAIL))
        db.commit()
        user = User(
            email=DEMO_EMAIL,
            name="Swayam",
            password_hash=hash_password(DEMO_PASSWORD),
            timezone=args.tz,
        )
        db.add(user)
        db.flush()

        for entry in _archive(today):
            attendees = ", ".join(entry["attendees"])
            notes = _notes(entry["summary"], entry["decisions"], entry["attendees"], entry["actions"])
            result = extract(notes, attendees, entry["day"])
            meeting = Meeting(
                user_id=user.id,
                title=entry["title"],
                occurred_on=entry["day"],
                attendees=attendees,
                notes=notes,
                summary=result.summary,
                source="local",
                model=None,
                extract_note=result.note,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(meeting)
            db.flush()

            for text in result.decisions:
                status = "revisit" if entry.get("revisit") == text else "agreed"
                db.add(
                    Decision(
                        user_id=user.id,
                        meeting_id=meeting.id,
                        text=text,
                        status=status,
                        decided_on=meeting.occurred_on,
                    )
                )

            for index, draft in enumerate(result.actions):
                done = index in entry.get("done", [])
                db.add(
                    ActionItem(
                        user_id=user.id,
                        meeting_id=meeting.id,
                        title=draft.title,
                        owner=draft.owner,
                        due_date=draft.due_date,
                        status="done" if done else "open",
                        completed_at=utcnow() if done else None,
                    )
                )

        db.commit()
        print(f"Demo account ready: {DEMO_EMAIL} with {len(_archive(today))} meetings")
        print("Sign in with the password documented at the top of scripts/seed_demo.py.")
    engine.dispose()


if __name__ == "__main__":
    main()
