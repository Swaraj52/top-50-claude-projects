"""Seed Foundry with demo data for the Business Operations Hub.

Creates a demo account with one SOP, a run, some people, and ownership data.
Run from the backend venv: python scripts/seed_demo.py

This creates data/foundry.db in the PROJECT_10 directory.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.models import Base, User, Person, Sop, SopStep, Run, RunItem
from app.security import hash_password
from sqlalchemy import select


def main() -> int:
    settings = Settings(database_url="sqlite:///C:/Users/Swayam Naik/TOP-50-CLAUDE-PROJECTS/PROJECT_10/data/foundry.db", run_migrations=False)
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)

    # Ensure tables exist
    Base.metadata.create_all(engine)

    db = sessionmaker()

    # Create a demo user
    user = db.scalar(select(User).where(User.email == "demo@foundry.example"))
    if not user:
        user = User(
            email="demo@foundry.example",
            name="Demo User",
            password_hash=hash_password("demo-password"),
            timezone="Asia/Kolkata",
        )
        db.add(user)
        db.commit()
        print("Created demo user: demo@foundry.example")
    else:
        print("Demo user already exists")

    # Create a demo SOP
    sop = db.scalar(select(Sop).where(Sop.user_id == user.id, Sop.code == "OPS-01"))
    if not sop:
        sop = Sop(
            user_id=user.id,
            code="OPS-01",
            title="Monthly Bank Reconciliation",
            area="finance",
            purpose="Ensure all monthly transactions are recorded and reconciled against the bank statement",
            scope="Finance team reconciles the month-end close process",
            cadence="monthly",
            review_months=6,
            status="draft",
            version=1,
        )
        db.add(sop)
        db.commit()
        print("Created SOP: OPS-01 Monthly Bank Reconciliation")

        # Add steps
        steps_data = [
            ("Match transactions",
             "Compare the company's cash book entries with the bank statement line by line",
             "Operator"),
            ("Identify discrepancies",
             "List any unmatched items and note the reason for the difference",
             "Operator"),
            ("Reconcile items",
             "Resolve unmatched items; write off immaterial differences",
             "Operator"),
            ("Certify and close",
             "Senior officer reviews and signs off the reconciliation",
             "Owner"),
        ]
        for i, (title, detail, role) in enumerate(steps_data, start=1):
            step = SopStep(
                position=i,
                title=title,
                detail=detail,
                role=role,
                minutes=30,
            )
            sop.steps.append(step)
        db.commit()
        print("Added 4 steps to the SOP")
    else:
        print("SOP OPS-01 already exists")

    # Create a person
    person = db.scalar(
        select(Person).where(
            Person.user_id == user.id, Person.name == "Alice"
        )
    )
    if not person:
        person = Person(
            user_id=user.id, name="Alice", role="Finance Manager",
            email="alice@example.com", active=True,
        )
        db.add(person)
        db.commit()
        print("Created person: Alice")
    else:
        print("Person Alice already exists")

    # Create a run from the SOP
    run = db.scalar(select(Run).where(Run.sop_id == sop.id))
    if not run:
        due = date.today() + timedelta(days=28)
        run = Run(
            sop_id=sop.id,
            owner_id=person.id,
            started_on=date.today(),
            due_on=due,
            status="open",
            notes="First run of the monthly reconciliation process",
        )
        db.add(run)
        db.commit()
        print("Created run for SOP OPS-01")

        # Add run items from the SOP steps
        for step in sop.steps:
            item = RunItem(
                position=step.position,
                title=step.title,
                detail=step.detail,
                role=step.role,
            )
            run.items.append(item)
        db.commit()
        print("Added 4 checklist items to the run")
    else:
        print("Run already exists")

    # Print summary
    print("\n--- Demo Summary ---")
    people = db.scalars(select(Person)).all()
    sops = db.scalars(select(Sop)).all()
    runs = db.scalars(select(Run)).all()
    print(f"User: {user.name} ({user.email})")
    print(f"People: {len(people)}")
    for p in people:
        print(f"  - {p.name} ({p.role})")
    print(f"SOPs: {len(sops)}")
    for s in sops:
        print(f"  - {s.code} {s.title} (status={s.status}, area={s.area})")
        print(f"    Steps: {len(s.steps)}")
    print(f"Runs: {len(runs)}")
    for r in runs:
        done = sum(1 for i in r.items if i.done)
        print(f"  - Run {r.id}: {done}/{len(r.items)} done, status={r.status}")

    db.close()
    print("\nSeed complete. Database at: data/foundry.db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())