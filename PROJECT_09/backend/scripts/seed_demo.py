"""Seed the demo portfolio.

Demo sign-in: demo@keystone.example / keystone-demo

Every figure below is invented for the demo. Dates are relative to the seed run, so the pace
labels and overdue milestones stay believable. Re-running wipes and recreates only the demo
account. Two ventures on purpose: one with a full desk, one still thin, so every empty state is
reachable from the demo login.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.config import Settings
from app.db import make_engine, make_sessionmaker, utcnow
from app.main import run_migrations
from app.models import (
    CanvasEntry,
    CostLine,
    Kpi,
    KpiReading,
    Milestone,
    RevenueStream,
    SwotItem,
    User,
    Venture,
)
from app.security import hash_password

DEMO_EMAIL = "demo@keystone.example"
DEMO_PASSWORD = "keystone-demo"
DEMO_NAME = "Swayam"

CANVAS_SAHAJ = [
    (
        "problem",
        "Independent installers quote on WhatsApp and lose track of site visits",
        "Two installers we spoke to each juggle 30-50 open jobs in a notebook.",
    ),
    (
        "customers",
        "Owner-run solar installers with two to eight technicians",
        "Based in Tier-2 cities; one person quotes, schedules and follows up.",
    ),
    (
        "value",
        "Every job, quote and payment in one list a technician can read on a phone",
        "No training: the first job is entered in under three minutes.",
    ),
    (
        "solution",
        "A mobile-first job board for quote, site visit and invoice steps",
        "Starts with scheduling; invoicing lands on the same job.",
    ),
    (
        "channels",
        "Installer WhatsApp groups and two distributor partnerships",
        "Distributors already run training days for new equipment.",
    ),
    (
        "revenue",
        "Rs 1,499 per installer per month, plus a paid migration",
        "Priced below the value of one recovered job.",
    ),
    (
        "costs",
        "One support person and hosting",
        "Support is the largest line until sixty accounts.",
    ),
    (
        "metrics",
        "Activated installers, jobs scheduled per week, setup hours",
        "Activation means three jobs entered in the first week.",
    ),
    (
        "advantage",
        "A workflow tuned to solar site visits, not generic field service",
        "The job steps mirror the subsidy paperwork installers already file.",
    ),
]

CANVAS_SECOND = [
    ("problem", "Founder updates read like status reports, not arguments", ""),
    ("customers", "Solo founders writing monthly investor updates", ""),
    ("value", "A second pair of eyes that cuts the update by a third", ""),
    ("solution", "An editing pass with a fixed checklist", ""),
    ("revenue", "Per-update fee, then a monthly retainer", ""),
]


def _venture_sahaj(user_id: int, today: date, now) -> Venture:
    venture = Venture(
        user_id=user_id,
        name="Sahaj",
        one_liner="Scheduling and invoicing for independent solar installers.",
        stage="validating",
        horizon="90 days",
        currency="INR",
        market=(
            "Residential solar is growing in Tier-2 cities, and most installers run the business "
            "from a phone. Subsidy paperwork moved online in September, which makes the job record "
            "more valuable than it was a year ago."
        ),
        segment="Owner-run solar installers with two to eight technicians",
        alternatives="A notebook, a WhatsApp group and a generic spreadsheet shared with the accountant.",
        differentiation="The job steps follow solar site visits and subsidy paperwork, so nobody has to translate.",
        created_at=now - timedelta(days=76),
        updated_at=now - timedelta(hours=5),
    )
    return venture


def _venture_second(user_id: int, today: date, now) -> Venture:
    return Venture(
        user_id=user_id,
        name="Second Draft",
        one_liner="An editing pass for founder updates that reads like an argument.",
        stage="idea",
        horizon="6 months",
        currency="INR",
        market="",
        segment="Solo founders writing monthly investor updates",
        alternatives="A friend reads it, or it ships unedited.",
        differentiation="A fixed checklist rather than generic copy-editing.",
        created_at=now - timedelta(days=9),
        updated_at=now - timedelta(days=2),
    )


def seed() -> dict[str, int]:
    settings = Settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    session = make_sessionmaker(engine)
    now = utcnow()
    today = now.date()
    try:
        db = session()
        existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing is not None:
            db.delete(existing)
            db.commit()

        user = User(
            email=DEMO_EMAIL,
            name=DEMO_NAME,
            password_hash=hash_password(DEMO_PASSWORD),
            timezone="Asia/Kolkata",
            created_at=now - timedelta(days=90),
        )
        db.add(user)
        db.flush()

        sahaj = _venture_sahaj(user.id, today, now)
        second = _venture_second(user.id, today, now)
        db.add_all([sahaj, second])
        db.flush()

        for order, (block, title, detail) in enumerate(CANVAS_SAHAJ, start=1):
            db.add(
                CanvasEntry(
                    venture_id=sahaj.id, block=block, title=title, detail=detail, sort_order=order
                )
            )
        for order, (block, title, detail) in enumerate(CANVAS_SECOND, start=1):
            db.add(
                CanvasEntry(
                    venture_id=second.id, block=block, title=title, detail=detail, sort_order=order
                )
            )

        swot = [
            ("strength", "Two design partners already share their job logs", 5, "Both signed a one-page pilot note."),
            ("strength", "The founder ran installer operations for three years", 4, "Ran scheduling for 40 technicians."),
            ("strength", "Hindi-first interface drafted", 3, "Tested with two installers in Nagpur."),
            ("weakness", "No invoicing yet", 4, "Installers still bill from a separate app."),
            ("weakness", "Support load is unknown above sixty accounts", 3, "One contractor handles all requests today."),
            ("opportunity", "Solar subsidy paperwork is moving online", 4, "State portal pilot announced in September."),
            ("opportunity", "Incumbent tools price per technician", 3, "A flat price per installer is easier to compare."),
            ("opportunity", "Distributor training days reach 200 installers a month", 3, "Two distributors agreed to a slot."),
            ("threat", "An incumbent adds a cheap scheduling tier", 4, "Their pricing page lists a coming soon plan."),
            ("threat", "Installers resist another app", 3, "Three of ten said they would not move off WhatsApp."),
        ]
        for quadrant, text, impact, evidence in swot:
            db.add(
                SwotItem(
                    venture_id=sahaj.id,
                    quadrant=quadrant,
                    text=text,
                    impact=impact,
                    evidence=evidence,
                )
            )
        db.add(
            SwotItem(
                venture_id=second.id,
                quadrant="strength",
                text="Writing and editing is the founder's actual craft",
                impact=4,
                evidence="",
            )
        )
        db.add(
            SwotItem(
                venture_id=second.id,
                quadrant="threat",
                text="Founders may not pay for an editing pass",
                impact=4,
                evidence="",
            )
        )

        db.add_all(
            [
                RevenueStream(
                    venture_id=sahaj.id,
                    name="Installer subscription",
                    model="subscription",
                    price=1499,
                    unit="per installer / month",
                    volume=40,
                    confidence="high",
                    notes="Design partners convert at about sixty percent.",
                ),
                RevenueStream(
                    venture_id=sahaj.id,
                    name="Migration and setup",
                    model="one_off",
                    price=6000,
                    unit="per account",
                    volume=3,
                    confidence="medium",
                    notes="First ten accounts only; the goal is to remove it later.",
                ),
                CostLine(
                    venture_id=sahaj.id,
                    name="Support contractor",
                    amount=18000,
                    kind="fixed",
                    notes="Twenty hours a week at Rs 900.",
                ),
                CostLine(
                    venture_id=sahaj.id,
                    name="Hosting and SMS",
                    amount=5500,
                    kind="variable",
                    notes="Grows with jobs scheduled.",
                ),
                CostLine(
                    venture_id=sahaj.id,
                    name="Payment processing",
                    amount=2400,
                    kind="variable",
                    notes="About two percent of collected subscription.",
                ),
            ]
        )

        milestones = [
            ("Ten installers entering jobs weekly", "Ten accounts each log three jobs in one week.", "Swayam", today + timedelta(days=12), "now", "in_progress", now - timedelta(days=4)),
            ("Pilot pricing call with both design partners", "Both partners agree the same price and term.", "Swayam", today - timedelta(days=4), "now", "planned", None),
            ("Distributor training deck", "One distributor runs the deck without help.", "Priya", today + timedelta(days=30), "next", "done", now - timedelta(days=2)),
            ("Invoicing in the same job view", "One installer sends a real invoice from the app.", "Arjun", today + timedelta(days=45), "next", "planned", None),
            ("Sixty paying installers", "Rs 90k MRR with churn under eight percent.", "Swayam", today + timedelta(days=120), "later", "planned", None),
            ("Support playbook", "A new contractor answers the top ten requests unaided.", "Priya", today + timedelta(days=150), "later", "planned", None),
        ]
        for order, (title, criterion, owner, due, horizon, status, completed) in enumerate(milestones, start=1):
            db.add(
                Milestone(
                    venture_id=sahaj.id,
                    title=title,
                    success_criterion=criterion,
                    owner=owner,
                    due_date=due,
                    horizon=horizon,
                    status=status,
                    completed_at=completed,
                    sort_order=order,
                )
            )
        db.add(
            Milestone(
                venture_id=second.id,
                title="Three paid editing passes",
                success_criterion="Three founders pay for a pass and send a second update.",
                owner="Swayam",
                due_date=today + timedelta(days=21),
                horizon="now",
                status="planned",
                sort_order=1,
            )
        )

        activated = Kpi(
            venture_id=sahaj.id,
            name="Activated installers",
            unit="installers",
            direction="up",
            baseline=0,
            target=40,
            target_date=today + timedelta(days=90),
            cadence="weekly",
            created_at=now - timedelta(days=70),
        )
        jobs = Kpi(
            venture_id=sahaj.id,
            name="Jobs scheduled per week",
            unit="jobs",
            direction="up",
            baseline=0,
            target=400,
            target_date=today + timedelta(days=60),
            cadence="weekly",
            created_at=now - timedelta(days=60),
        )
        setup = Kpi(
            venture_id=sahaj.id,
            name="Setup hours per account",
            unit="hours",
            direction="down",
            baseline=6,
            target=2,
            target_date=today + timedelta(days=45),
            cadence="monthly",
            created_at=now - timedelta(days=30),
        )
        db.add_all([activated, jobs, setup])
        db.flush()

        readings = [
            (activated, [2, 4, 6, 9, 11, 14, 17, 19, 22, 24]),
            (jobs, [40, 70, 95, 120, 150, 175, 190, 210, 235, 250]),
            (setup, [6, 5.5, 5, 4.5, 4, 3.5]),
        ]
        for kpi, values in readings:
            for index, value in enumerate(values):
                days_ago = (len(values) - index) * 7 - 4
                db.add(
                    KpiReading(
                        kpi_id=kpi.id,
                        value=value,
                        recorded_on=today - timedelta(days=max(days_ago, 0)),
                        note="",
                    )
                )

        db.add(
            Kpi(
                venture_id=second.id,
                name="Update turnaround",
                unit="days",
                direction="down",
                baseline=6,
                target=2,
                target_date=today + timedelta(days=60),
                cadence="monthly",
                created_at=now - timedelta(days=8),
            )
        )

        db.commit()
        counts = {
            "ventures": 2,
            "canvas": len(CANVAS_SAHAJ) + len(CANVAS_SECOND),
            "swot": len(swot) + 2,
            "milestones": len(milestones) + 1,
            "kpis": 4,
            "readings": sum(len(values) for _kpi, values in readings),
        }
        return counts
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    print(seed())
