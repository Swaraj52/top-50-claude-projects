"""Create the demo desk for screenshots and first-run exploration.

    cd PROJECT_07/backend
    python -m scripts.seed_demo

Sign in with **demo@switchboard.example / switchboard-demo**.

Every thread is built by the app's own rules: the same classifier, priority scoring and local
summary writer that a real paste goes through. Nothing here is hard-coded output pretending to be a
computation, and the account contains only invented mail.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db import make_engine, make_sessionmaker, utcnow  # noqa: E402
from app.models import Draft, FollowUp, Mailbox, Thread, User  # noqa: E402
from app.routes.mail import _ingest, _refresh_thread  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.ai import DRAFT_NOTE_LOCAL  # noqa: E402
from app.services.mail import draft_local, vip_set  # noqa: E402
from app.timeutil import local_today, zone  # noqa: E402

DEMO_EMAIL = "demo@switchboard.example"
DEMO_PASSWORD = "switchboard-demo"
DEMO_NAME = "Swayam"
DEMO_TZ = "Asia/Kolkata"
DEMO_SIGNATURE = "Product lead, Lumen Labs"
DEMO_VIPS = "priya@lumen.example, meera@northwind.example, kavya@lumen.example"

# Each thread: subject, messages (direction, hours ago, sender override, body), optional extras.
THREADS = [
    {
        "subject": "Q4 launch checklist",
        "sender": "Priya Raman <priya@lumen.example>",
        "messages": [
            (
                "in",
                4.5,
                None,
                "Hi Swayam,\n\nI put the launch checklist in the shared doc. Could you review the pricing "
                "section and confirm the numbers by Friday? The board pack goes out Monday, so I need "
                "your sign-off before then.\n\nThanks,\nPriya",
            )
        ],
        "star": True,
        "draft": "warm",
        "followup": ("Priya's sign-off on the launch checklist", 2),
    },
    {
        "subject": "Coffee next week?",
        "sender": "Meera Iyer <meera@northwind.example>",
        "messages": [
            (
                "in",
                7,
                None,
                "Hey Swayam,\n\nIt has been too long. Are you free for coffee on Tuesday or Wednesday "
                "afternoon? I am near your office both days and would love to hear how the launch is going.\n\nMeera",
            )
        ],
        "star": True,
        "draft": "brief",
    },
    {
        "subject": "Contract redlines",
        "sender": "Arjun Mehta <arjun@acme.example>",
        "messages": [
            (
                "in",
                52,
                None,
                "Swayam,\n\nLegal sent back the redlines on the vendor agreement. Two clauses changed: the "
                "termination window and the payment terms. Can you take a look and tell me whether we can "
                "accept them this week?\n\nArjun",
            ),
            (
                "out",
                30,
                None,
                "Hi Arjun,\n\nI went through both changes. The termination window is fine. The payment terms "
                "need to stay at net 30; I have asked our finance lead to confirm in writing. I will send "
                "the countersigned copy once that lands.\n\nSwayam",
            ),
        ],
        "sent_draft": True,
        "followup": ("Countersigned contract from Arjun", -2),
    },
    {
        "subject": "Your November invoice",
        "sender": "Billing <billing@stripe.example>",
        "messages": [
            (
                "in",
                26,
                None,
                "Your invoice for November is ready. Amount charged: 24.00 USD. This is a receipt for your "
                "records. No action is required.\n\nInvoice number INV-2026-1142.",
            )
        ],
    },
    {
        "subject": "How the best PMs run a launch",
        "sender": "Lenny's Newsletter <news@lennys.example>",
        "messages": [
            (
                "in",
                5,
                None,
                "This week: the launch checklist used by three heads of product, a teardown of onboarding "
                "emails, and why your pricing page is doing too much. You are receiving this because you "
                "subscribed. Unsubscribe or manage your preferences at any time.",
            )
        ],
    },
    {
        "subject": "The measure of our aliveness",
        "sender": "The Marginalian <newsletter@themarginalian.example>",
        "messages": [
            (
                "in",
                50,
                None,
                "A letter about attention, trees, and the courage to stay curious. View this in your browser "
                "if the images do not load. You are receiving this newsletter because you asked for it.",
            )
        ],
    },
    {
        "subject": "[lumen/switchboard] Security alert resolved",
        "sender": "GitHub <noreply@github.example>",
        "messages": [
            (
                "in",
                9,
                None,
                "The Dependabot alert on a transitive dependency has been resolved by a merge to main. "
                "No action is needed from you. You can review the alert in the security tab.",
            )
        ],
    },
    {
        "subject": "Design system week 44 notes",
        "sender": "Nadia Khan <nadia@lumen.example>",
        "messages": [
            (
                "in",
                24,
                None,
                "Notes from the design system review are in the doc. We renamed two tokens and deprecated "
                "the old spacing scale. The migration is already done in the app shell. Nothing is needed "
                "from you this week.",
            )
        ],
    },
    {
        "subject": "Re: onboarding deck",
        "sender": "Ravi Shah <ravi@vendor.example>",
        "messages": [
            (
                "in",
                70,
                None,
                "Swayam,\n\nThanks for the deck. I have shared it with our onboarding team. Could you send the "
                "two sample screenshots at higher resolution so we can drop them into the customer guide?\n\nRavi",
            ),
            (
                "out",
                46,
                None,
                "Hi Ravi,\n\nGlad it landed well. I have exported both screenshots at 2x and put them in the "
                "shared folder. Let me know if the guide needs a short caption for each.\n\nSwayam",
            ),
        ],
        "followup": ("Ravi's feedback on the deck", 5),
    },
    {
        "subject": "Board deck numbers due tomorrow",
        "sender": "Kavya Rao <kavya@lumen.example>",
        "messages": [
            (
                "in",
                30,
                None,
                "Swayam,\n\nI still need the ARR and net-retention numbers for the board deck. The deadline is "
                "tomorrow at noon. Can you send them to me today so I can build the chart?\n\nKavya",
            )
        ],
        "followup": ("Send Kavya the ARR numbers", 0),
    },
    {
        "subject": "Receipt for your November payment",
        "sender": "Figma <receipts@figma.example>",
        "messages": [
            (
                "in",
                96,
                None,
                "Thanks for your payment. Your receipt for November is attached. Total charged: 45.00 USD. "
                "Your next billing date is 14 December 2026. This is an automated receipt.",
            )
        ],
    },
    {
        "subject": "API sandbox access",
        "sender": "Tomas Berg <tomas@partner.example>",
        "messages": [
            (
                "in",
                48,
                None,
                "Hello Swayam,\n\nWe would like to test the partner API before the integration review. Could "
                "you create a sandbox key for our staging account?\n\nTomas",
            ),
            (
                "in",
                6,
                None,
                "Hi Swayam,\n\nAny update on the sandbox access? Our integration review is next Wednesday and "
                "we would like a day or two with the API first. Thanks!\n\nTomas",
            ),
        ],
        "draft": "formal",
        "followup": ("Sandbox credentials for Tomas", 7),
    },
]


def _email_text(value: str) -> str:
    return value.strip()


def seed(settings: Settings | None = None) -> dict[str, int]:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    now = utcnow()

    with Session() as db:
        existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing is not None:
            db.execute(delete(User).where(User.id == existing.id))
            db.commit()

        user = User(
            email=DEMO_EMAIL,
            name=DEMO_NAME,
            password_hash=hash_password(DEMO_PASSWORD),
            timezone=DEMO_TZ,
            signature=DEMO_SIGNATURE,
            vips=DEMO_VIPS,
        )
        db.add(user)
        db.flush()
        mailbox = Mailbox(user_id=user.id, name="Personal", address=DEMO_EMAIL)
        db.add(mailbox)
        db.commit()

        c = SimpleNamespace(user=user)
        vips = vip_set(user.vips)
        today = local_today(zone(user.timezone))
        counts = {"threads": 0, "messages": 0, "drafts": 0, "followups": 0}

        for spec in THREADS:
            thread = None
            inbound_count = 0
            for direction, hours_ago, sender, body in spec["messages"]:
                at = now - timedelta(hours=hours_ago)
                if direction == "in":
                    thread, _message = _ingest(
                        db,
                        c,
                        mailbox,
                        sender=sender or spec["sender"],
                        recipients=DEMO_EMAIL,
                        subject=spec["subject"],
                        body=_email_text(body),
                        received_at=at,
                    )
                    inbound_count += 1
                    counts["messages"] += 1
                else:
                    assert thread is not None, "an outbound message needs a thread first"
                    from app.models import Message

                    db.add(
                        Message(
                            user_id=user.id,
                            thread_id=thread.id,
                            direction="out",
                            sender=mailbox.address,
                            recipients=spec["sender"],
                            body=_email_text(body),
                            received_at=at,
                        )
                    )
                    db.commit()
                    db.refresh(thread)
                    counts["messages"] += 1

            if thread is None:
                continue
            db.refresh(thread)
            has_outbound = any(message.direction == "out" for message in thread.messages)
            _refresh_thread(thread, thread.messages, vips, inbound=not has_outbound)
            if has_outbound:
                thread.status = "waiting"
                thread.category = "waiting"
                thread.category_source = "rules"
            thread.starred = bool(spec.get("star"))
            thread.unread = bool(spec.get("star")) and not has_outbound
            if inbound_count > 1:
                thread.unread = True
            thread.updated_at = now
            db.commit()
            counts["threads"] += 1

            if spec.get("draft"):
                text = draft_local(thread, thread.messages, user, spec["draft"])
                db.add(
                    Draft(
                        user_id=user.id,
                        thread_id=thread.id,
                        subject=text.subject,
                        body=text.body,
                        tone=spec["draft"],
                        source="local",
                        status="draft",
                        note=DRAFT_NOTE_LOCAL,
                    )
                )
                counts["drafts"] += 1

            if spec.get("sent_draft"):
                text = draft_local(thread, thread.messages, user, "warm")
                db.add(
                    Draft(
                        user_id=user.id,
                        thread_id=thread.id,
                        subject=text.subject,
                        body=text.body,
                        tone="warm",
                        source="local",
                        status="sent",
                        note="Marked sent locally. Switchboard does not send email.",
                    )
                )
                counts["drafts"] += 1

            if spec.get("followup"):
                title, offset = spec["followup"]
                db.add(
                    FollowUp(
                        user_id=user.id,
                        thread_id=thread.id,
                        title=title,
                        due_date=today + timedelta(days=offset),
                        status="open",
                    )
                )
                counts["followups"] += 1

        # One finished follow-up, so the Done tab is not empty.
        own = db.scalar(select(Thread).where(Thread.user_id == user.id, Thread.subject == "Design system week 44 notes"))
        if own is not None:
            db.add(
                FollowUp(
                    user_id=user.id,
                    thread_id=own.id,
                    title="Confirm the token rename landed in the app shell",
                    due_date=today - timedelta(days=1),
                    status="done",
                    completed_at=now - timedelta(days=1, hours=3),
                )
            )
            counts["followups"] += 1

        db.add(
            FollowUp(
                user_id=user.id,
                thread_id=thread.id,
                title="Renew the analytics sandbox",
                due_date=today + timedelta(days=19),
                status="open",
            )
        )
        counts["followups"] += 1
        db.commit()

    engine.dispose()
    return counts


def main() -> int:
    settings = Settings()
    counts = seed(settings)
    print(f"Seeded {counts['threads']} threads, {counts['messages']} messages, "
          f"{counts['drafts']} drafts and {counts['followups']} follow-ups.")
    print(f"Sign in: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"Database: {settings.database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
