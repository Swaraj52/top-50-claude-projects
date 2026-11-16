"""Seed the demo library.

Demo sign-in: demo@loom.example / loom-demo

Every body below is invented for the demo. Timestamps are relative to the moment the seed runs,
so the dashboard and "updated …" labels stay believable. Re-running wipes and recreates only the
demo account.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.config import Settings
from app.db import make_engine, make_sessionmaker, utcnow
from app.main import run_migrations
from app.models import Collection, Item, User
from app.security import hash_password

DEMO_EMAIL = "demo@loom.example"
DEMO_PASSWORD = "loom-demo"
DEMO_NAME = "Swayam"


def _seed_items(collections: dict[str, Collection]) -> list[Item]:
    now = utcnow()

    def at(days: int, hours: int = 0) -> object:
        return now - timedelta(days=days, hours=hours)

    rows = [
        # --- Client work: pricing thread -------------------------------------
        {
            "title": "Q4 pricing review — decisions and open questions",
            "kind": "note",
            "collection": "Client work",
            "tags": "pricing, q4, decisions, lumen",
            "body": (
                "Attendees: Priya, Arjun, Meera, Swayam.\n\n"
                "Decision: the Starter plan stays at the current price until the January renewal "
                "cycle, so existing customers see no change this quarter. The Growth plan moves to "
                "a usage-based pricing model, reviewed monthly.\n\n"
                "Open question: does the pricing page need a separate calculator, or can the "
                "estimate live inside the trial signup? Priya will test both with five customers.\n\n"
                "Open question: the annual discount is still 15 percent. Arjun asked whether a "
                "two-year commitment should get 20 percent. No decision; revisit after the January "
                "renewal numbers arrive.\n\n"
                "Next step: Meera updates the pricing page copy, and Swayam confirms the contract "
                "language with the finance team before the board pack goes out."
            ),
            "starred": True,
            "days": 1,
        },
        {
            "title": "Lumen onboarding checklist",
            "kind": "note",
            "collection": "Client work",
            "tags": "onboarding, checklist, lumen",
            "body": (
                "Kickoff happened. The checklist below is the shared source of truth for the first "
                "two weeks.\n\n"
                "1. Workspace created and the admin invited. Done.\n"
                "2. Import the customer list from the old tool; check two sample accounts by hand.\n"
                "3. Set the default permission group; Priya signs off on the policy.\n"
                "4. Walk through the weekly report with the operations team on Thursday.\n"
                "5. Agree the support channel and response expectations in writing.\n\n"
                "Notes from the kickoff: the team is small, so the weekly report matters more than "
                "the live dashboard. They asked for a single export of everything at the end of the "
                "pilot. Keep the export boring and complete."
            ),
            "days": 4,
        },
        {
            "title": "Lumen contract: renewal terms to confirm",
            "kind": "reference",
            "collection": "Client work",
            "tags": "contract, pricing, legal, lumen",
            "body": (
                "Renewal is due 15 January. The current agreement renews automatically for twelve "
                "months unless either side gives thirty days notice.\n\n"
                "Terms to confirm before signing:\n"
                "- Pricing: the Growth plan moves to usage-based billing, capped for the first two "
                "months while the team learns its volume.\n"
                "- Support: business-hours response, one named contact on each side.\n"
                "- Data: export available on request, deleted thirty days after termination.\n"
                "- Notice: thirty days, in writing, to the address in schedule two.\n\n"
                "Open question for finance: does the capped month count as a discount, and does it "
                "need to appear in the contract or only the order form?"
            ),
            "days": 6,
        },
        {
            "title": "Competitor pricing teardown",
            "kind": "article",
            "collection": "Client work",
            "tags": "pricing, research, competitors",
            "author": "Meera",
            "source_url": "https://research.example/pricing-teardown",
            "body": (
                "A read of six competitors, focused on how each presents pricing rather than the "
                "absolute number.\n\n"
                "Four of the six lead with a free tier and hide the usage limits until the second "
                "screen. The two enterprise vendors anchor on a single number and add a contact "
                "form. Nobody shows a calculator on the pricing page; two show one inside the "
                "trial.\n\n"
                "The clearest pattern: the price is not the argument. Each page argues about what "
                "counts as a seat, what counts as usage, and what happens when a team grows. That is "
                "where the confusion lives.\n\n"
                "Takeaway for our own page: show the two plans side by side, name the unit of "
                "pricing in the heading, and put the estimate in the signup flow where the customer "
                "already has context. Revisit after the January renewal numbers."
            ),
            "days": 8,
        },
        # --- Product notes: database and search ------------------------------
        {
            "title": "Postgres index notes: when a composite index helps",
            "kind": "snippet",
            "collection": "Product notes",
            "tags": "database, postgres, performance",
            "body": (
                "A composite index on (user_id, updated_at) answers two shapes at once: filter by "
                "user, then order by recency. A separate index on updated_at would not help a "
                "per-user list.\n\n"
                "Column order matters. Equality columns first, then the range or sort column. An "
                "index on (updated_at, user_id) is much weaker for this query.\n\n"
                "Watch the planner before adding more. On small tables a sequential scan is "
                "cheaper than the index, and a redundant index only costs writes."
            ),
            "days": 10,
        },
        {
            "title": "SQLite WAL mode and one writer",
            "kind": "snippet",
            "collection": "Product notes",
            "tags": "database, sqlite, performance",
            "body": (
                "Write-ahead logging lets readers continue while one writer works. It does not give "
                "you two writers. A second process that writes will wait, then fail on the busy "
                "timeout if the first holds the lock too long.\n\n"
                "For a single-user desk that is fine: keep writes short, commit in one place, and "
                "let the import script run beside the app. For a multi-worker service, move to a "
                "real server database.\n\n"
                "Foreign keys are off by default in SQLite. Turn them on per connection, otherwise "
                "cascade deletes are quietly skipped."
            ),
            "days": 12,
        },
        {
            "title": "Search ranking: BM25 in plain words",
            "kind": "note",
            "collection": "Product notes",
            "tags": "search, ranking, bm25",
            "body": (
                "BM25 rewards a term that appears often in a document, but the reward flattens so a "
                "page cannot win by repeating a word. It also penalises a term that appears in "
                "almost every document: if every note mentions the project name, that name says "
                "little about relevance.\n\n"
                "The practical version: weight the title and tags above the body, count term "
                "frequency with saturation, multiply by an inverse document frequency, then add a "
                "small bonus when every query term is present and a larger one for an exact "
                "phrase.\n\n"
                "Explain the score in the interface. A ranked list without reasons cannot be "
                "corrected, and a correction is the most useful signal a personal search engine "
                "gets."
            ),
            "starred": True,
            "days": 14,
        },
        {
            "title": "Why snippets need escaping before highlighting",
            "kind": "snippet",
            "collection": "Product notes",
            "tags": "security, search, html",
            "body": (
                "The safe order is: escape the text, then insert markup around the matched words. "
                "If you highlight first and escape afterwards, the mark tags are escaped too and "
                "the user sees the markup.\n\n"
                "If you escape first and then search for the raw term, a term containing an "
                "ampersand or an angle bracket will not be found, because the escaped text no "
                "longer contains it. Match on the raw text, escape each slice, and join with mark "
                "tags that your own code produced.\n\n"
                "This is also why a snippet builder should never accept HTML from a document. It "
                "takes plain text and returns a small, known set of tags."
            ),
            "days": 17,
        },
        # --- Reading list ----------------------------------------------------
        {
            "title": "Reading: The Design of Everyday Things",
            "kind": "article",
            "collection": "Reading list",
            "tags": "design, books, usability",
            "author": "Don Norman",
            "source_url": "https://books.example/design-everyday-things",
            "body": (
                "The core argument: when a person fails to use a thing, the design failed first. "
                "Affordances suggest what an object can do; signifiers show where to act; feedback "
                "says what happened; a good conceptual model explains why.\n\n"
                "The examples that stayed with me are doors and stoves, because they are ordinary. "
                "A door with a handle that must be pushed is a small argument between the handle "
                "and the hinge. People blame themselves, then the next person does the same thing.\n\n"
                "Applied to software: a control that looks pressable should be pressable; a status "
                "should describe the state, not the effort; an error should say what to do next. "
                "Design is not decoration on top of the model, it is the model made visible."
            ),
            "days": 20,
        },
        {
            "title": "Reading: Thinking in Systems",
            "kind": "article",
            "collection": "Reading list",
            "tags": "systems, books, mental-models",
            "author": "Donella Meadows",
            "source_url": "https://books.example/thinking-in-systems",
            "body": (
                "A system is a set of things connected in a way that produces a pattern over time. "
                "Stocks, flows and feedback loops are enough to describe more than they should.\n\n"
                "The leverage points I keep returning to: change the information people receive, "
                "change the rules, change the goal. Prices and parameters are weak leverage; a "
                "delay in feedback is often the reason a sensible policy oscillates.\n\n"
                "The warning is useful for product work: if the metric improves while the goal gets "
                "worse, you have optimised the measure. Look for the loop, not the number."
            ),
            "days": 24,
        },
        {
            "title": "Notes on typography for reading screens",
            "kind": "note",
            "collection": "Reading list",
            "tags": "design, typography, reading",
            "body": (
                "Measure first. Around 60 to 75 characters per line is comfortable for body text; "
                "long lines lose the return sweep and short lines break the rhythm.\n\n"
                "Line height near 1.5 for sans and a little more for serif. Headings need less, "
                "because the eye is not reading a paragraph.\n\n"
                "Contrast is not the same as comfort. Pure black on pure white is harsh for long "
                "reading; a warm off-white with near-black ink is easier for hours. Keep the "
                "contrast ratio above 7:1 anyway.\n\n"
                "Use one serif for display and one sans for interface text, then stop. A third face "
                "is usually a decision made twice."
            ),
            "days": 27,
        },
        # --- Personal systems -------------------------------------------------
        {
            "title": "Weekly review ritual",
            "kind": "note",
            "collection": "Personal systems",
            "tags": "habits, review, planning",
            "body": (
                "Thirty minutes on Friday afternoon, in this order:\n\n"
                "1. Empty the capture inbox; every item gets a home or is deleted.\n"
                "2. Look at the week's calendar and write one sentence about what actually "
                "happened.\n"
                "3. Choose the three outcomes for next week, not ten tasks.\n"
                "4. Check the waiting-on list and send the one message that unblocks someone.\n"
                "5. Close the laptop.\n\n"
                "The point is not the review itself. It is arriving on Monday without rebuilding "
                "the context from memory."
            ),
            "days": 29,
        },
        {
            "title": "Sleep and deep work",
            "kind": "note",
            "collection": "Personal systems",
            "tags": "health, sleep, focus",
            "body": (
                "Two weeks of notes, no grand conclusion. On nights with seven and a half hours or "
                "more, the first ninety minutes of work produced something I kept. On shorter "
                "nights I answered messages and called it work.\n\n"
                "What helped: a fixed lights-out time, no laptop after it, and a paper list for "
                "anything still open. What did not: catching up on sleep at the weekend.\n\n"
                "The honest reading is that focus is downstream of sleep, not a separate discipline "
                "to optimise."
            ),
            "days": 31,
        },
        {
            "title": "Tax documents for 2025-26",
            "kind": "reference",
            "collection": "Personal systems",
            "tags": "tax, finance, documents",
            "body": (
                "Keep the following together before the filing window:\n\n"
                "- Salary statements and the annual tax summary.\n"
                "- Bank interest certificates for every account.\n"
                "- Investment statements for the year, including dividends.\n"
                "- Receipts for deductible professional expenses, scanned and named by month.\n"
                "- The previous year's filed return, for reference.\n\n"
                "Filename convention: year-type-month.pdf. The folder lives outside the repository "
                "and is backed up separately."
            ),
            "days": 33,
        },
    ]

    items: list[Item] = []
    for row in rows:
        moment = at(row.pop("days"))
        items.append(
            Item(
                collection=collections[row.pop("collection")],
                created_at=moment,
                updated_at=moment,
                origin="written",
                **row,
            )
        )
    return items


def seed() -> dict[str, int]:
    settings = Settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    db = sessionmaker()
    try:
        existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing is not None:
            db.delete(existing)
            db.commit()

        user = User(
            email=DEMO_EMAIL,
            name=DEMO_NAME,
            password_hash=hash_password(DEMO_PASSWORD),
            timezone="Asia/Kolkata",
        )
        db.add(user)
        db.flush()

        collections: dict[str, Collection] = {}
        for name, description in (
            ("Client work", "Lumen pilot, pricing and the January renewal"),
            ("Product notes", "Ranking, storage and the search interface"),
            ("Reading list", "Books and design notes worth keeping"),
            ("Personal systems", "Routines, health and paperwork"),
        ):
            collections[name] = Collection(user_id=user.id, name=name, description=description)
            db.add(collections[name])
        db.flush()

        for item in _seed_items(collections):
            item.user_id = user.id
            db.add(item)
        db.commit()
        return {
            "items": len(db.scalars(select(Item.id).where(Item.user_id == user.id)).all()),
            "collections": len(collections),
        }
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    print(seed())
