"""Create a DEMO account filled with sample data (for screenshots and trying the app).

    cd PROJECT_01/backend
    python -m scripts.seed_demo            # uses DATABASE_URL / the default database
    python -m scripts.seed_demo --tz Europe/London

Everything created here is demo data:
  * account  demo@daybook.example / password "daybook-demo" (local use only)
  * the "Team calendar (demo)" source is generated ICS, parsed by the real ICS service
  * the mailbox "demo-inbox@example.invalid" cannot be synced; its messages are samples
Running it again wipes and recreates the demo account only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import delete, select

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.main import run_migrations
from app.models import CalendarSource, Email, EmailAccount, Event, Reminder, Task, User
from app.security import SecretBox, hash_password
from app.services import ics
from app.timeutil import local_today, zone

DEMO_EMAIL = "demo@daybook.example"
DEMO_PASSWORD = "daybook-demo"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tz", default="Asia/Kolkata", help="IANA timezone of the demo user")
    args = parser.parse_args()

    settings = Settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    box = SecretBox(settings.secret_key)
    tz = zone(args.tz)
    today = local_today(tz)
    now = datetime.now(timezone.utc)

    def at(day_offset: int, hh: int, mm: int = 0) -> datetime:
        local = datetime.combine(today + timedelta(days=day_offset), time(hh, mm), tzinfo=tz)
        return local.astimezone(timezone.utc)

    with Session() as db:
        db.execute(delete(User).where(User.email == DEMO_EMAIL))
        db.commit()

        user = User(email=DEMO_EMAIL, name="Swayam", password_hash=hash_password(DEMO_PASSWORD), timezone=args.tz)
        db.add(user)
        db.flush()
        uid = user.id

        tasks = [
            ("Send Q4 proposal to Acme", "high", -2, "Pricing tab still needs Finance sign-off."),
            ("Book flights for the offsite", "high", 0, ""),
            ("Review Sam's pull request #42", "medium", 0, "Focus on the migration script."),
            ("Expense report for October", "low", 0, ""),
            ("Prepare board update slides", "medium", 2, ""),
            ("Renew the daybook.example domain", "low", 5, ""),
            ("Read notes from 'Deep Work'", "low", None, ""),
        ]
        for title, prio, offset, notes in tasks:
            db.add(Task(user_id=uid, title=title, priority=prio, notes=notes,
                        due_date=None if offset is None else today + timedelta(days=offset)))
        db.add(Task(user_id=uid, title="Reply to the landlord", priority="medium", due_date=today,
                    status="done", completed_at=now - timedelta(hours=1)))

        db.add_all([
            Reminder(user_id=uid, text="Call the bank about the new card", remind_at=now - timedelta(minutes=3)),
            Reminder(user_id=uid, text="Stretch and refill water", remind_at=now + timedelta(hours=2)),
            Reminder(user_id=uid, text="Pick up dry cleaning", remind_at=at(0, 18, 30)),
        ])

        for title, start, minutes, location in [
            ("Standup", at(0, 9, 30), 15, "Zoom"),
            ("Lunch with Priya", at(0, 13, 0), 60, "Café Mondegar"),
            ("Client call: Acme", at(1, 10, 0), 45, ""),
            ("Dentist", at(2, 15, 0), 30, "Dr. Rao, Bandra"),
        ]:
            db.add(Event(user_id=uid, title=title, start_at=start, end_at=start + timedelta(minutes=minutes), location=location))

        # A generated feed, parsed by the same code that handles real subscriptions.
        fmt = "%Y%m%dT%H%M%SZ"
        team_events = [
            ("design", "Design review", at(0, 11, 0), at(0, 12, 0)),
            ("one-on-one", "1:1 with Sam", at(0, 16, 0), at(0, 16, 30)),
            ("workshop", "Roadmap workshop", at(-1, 14, 0), at(-1, 16, 0)),
            ("retro", "Sprint retro", at(3, 12, 0), at(3, 13, 0)),
        ]
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Daybook demo//EN"]
        for key, title, start, end in team_events:
            lines += ["BEGIN:VEVENT", f"UID:{key}@demo", f"SUMMARY:{title}",
                      f"DTSTART:{start.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}", "END:VEVENT"]
        offsite = today + timedelta(days=4)
        lines += ["BEGIN:VEVENT", "UID:planning@demo", "SUMMARY:Quarterly planning week",
                  f"DTSTART;VALUE=DATE:{today:%Y%m%d}", f"DTEND;VALUE=DATE:{offsite:%Y%m%d}", "END:VEVENT",
                  "END:VCALENDAR"]
        source = CalendarSource(user_id=uid, name="Team calendar (demo)", kind="file", color="#5b6cf0")
        db.add(source)
        db.flush()
        ics.replace_source_events(db, source, ics.parse_ics("\r\n".join(lines).encode(), tz))

        account = EmailAccount(user_id=uid, host="imap.example.invalid", port=993,
                               username="demo-inbox@example.invalid",
                               password_encrypted=box.encrypt("not-a-real-password"),
                               last_synced_at=now - timedelta(minutes=12))
        db.add(account)
        db.flush()
        for i, (name, addr, subject, hours_ago, unread, flagged) in enumerate([
            ("Priya Shah", "priya@acme.example", "Contract redlines: need your OK today", 1, True, True),
            ("Acme Procurement", "procurement@acme.example", "Re: Q4 proposal timeline", 3, True, False),
            ("GitHub", "notifications@github.example", "[daybook] PR #42 is ready for review", 5, True, False),
            ("Sam Lee", "sam@team.example", "Notes from yesterday's workshop", 20, False, True),
            ("Travel Desk", "travel@team.example", "Offsite flight options", 26, False, False),
        ], start=1):
            db.add(Email(user_id=uid, account_id=account.id, uid=str(100 + i), message_id=f"<demo-{i}@example>",
                         from_name=name, from_addr=addr, subject=subject,
                         received_at=now - timedelta(hours=hours_ago), is_unread=unread, is_flagged=flagged))
        db.commit()
        counts = {m.__name__: len(db.scalars(select(m.id).where(m.user_id == uid)).all())
                  for m in (Task, Reminder, Event, Email)}
    engine.dispose()
    print(f"Demo account ready: {DEMO_EMAIL} (timezone {args.tz}) -> {counts}")
    print("Sign in with the password documented at the top of scripts/seed_demo.py.")


if __name__ == "__main__":
    main()
