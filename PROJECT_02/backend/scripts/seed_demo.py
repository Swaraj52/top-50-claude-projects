"""Create a DEMO library with sample content (for screenshots and trying the app).

    cd PROJECT_02/backend
    python -m scripts.seed_demo

Everything created here is demo data:
  * account  demo@stacks.example / password "stacks-demo" (local use only)
  * all items are short sample texts written for this demo, on fictional *.example sites
  * the "video" item has no real YouTube link; its transcript is sample text
Summaries are produced by the real extractive summariser; the index by the real indexer.
Running it again wipes and recreates the demo account only.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete

from app.config import Settings
from app.db import make_engine, make_sessionmaker, utcnow
from app.main import run_migrations
from app.models import Item, Question, Tag, User
from app.security import hash_password
from app.services import indexer, summarize
from app.services.ask import retrieve

DEMO_EMAIL = "demo@stacks.example"
DEMO_PASSWORD = "stacks-demo"

ITEMS = [
    dict(kind="article", status="library", fav=True, tags=["sleep", "memory"], days=12,
         title="Why sleep matters for memory", source="Brain Weekly (demo)", author="Maya Rao",
         url="https://brainweekly.example/sleep-and-memory",
         content="""During deep sleep the hippocampus replays the day's experiences and hands them to the neocortex for long-term storage. This consolidation is why students who sleep after studying remember more than those who pull an all-nighter.

A short afternoon nap of about twenty minutes improves alertness without grogginess. Naps longer than an hour often end in slow-wave sleep, which is why you can wake up feeling worse.

Caffeine blocks adenosine receptors. A coffee after 2pm can delay sleep onset by around an hour and reduce deep sleep, which weakens memory consolidation the following night.

Consistency matters more than catching up: going to bed and waking at the same time keeps your circadian rhythm stable, and a stable rhythm improves both sleep quality and next-day focus."""),
    dict(kind="article", status="library", fav=False, tags=["habits", "productivity"], days=9,
         title="Tiny habits that actually stick", source="Field Notes (demo)", author="Jon Ellis",
         url="https://fieldnotes.example/tiny-habits",
         content="""Habit formation depends on three things: a clear cue, a routine small enough to feel trivial, and an immediate reward. Start with one page of reading or two push-ups.

Stack the new habit onto an existing one: after I pour my morning coffee, I write one sentence in my journal. The existing routine becomes the cue.

In the first month consistency beats intensity. Missing once is an accident; missing twice is the start of a new habit, so never skip twice in a row.

Track the habit somewhere visible. A paper calendar with a cross for each day creates a chain you will not want to break."""),
    dict(kind="video", status="library", fav=False, tags=["learning", "memory"], days=7,
         title="Spaced repetition, explained (demo transcript)", source="YouTube", author="Learning Lab (demo)", url=None,
         content="""[0:00] Welcome back. Today we look at spaced repetition, the most reliable way to move facts into long-term memory.

[1:02] The forgetting curve shows that we lose most of what we learn within days unless we review it. Each review flattens the curve.

[2:05] The trick is timing: review just before you would forget. Start with a day, then three days, a week, two weeks, a month.

[3:10] Combine spacing with active recall. Testing yourself beats rereading, because retrieving a memory strengthens it."""),
    dict(kind="newsletter", status="library", fav=False, tags=["finance"], days=5,
         title="Markets: inflation cools for a third month", source="The Morning Ledger (demo)", author="The Morning Ledger", url=None,
         content="""Stocks rallied as inflation cooled for the third straight month, lifting rate-sensitive technology shares and small caps.

Bond yields slipped as traders priced in an interest rate cut early next year. Mortgage rates followed, giving housing stocks their best week since spring.

Oil fell on weaker demand forecasts from Asia, while gold held near its record high as investors hedged against a slowdown."""),
    dict(kind="note", status="library", fav=True, tags=["ideas", "learning"], days=4,
         title="Study plan for the ML exam", source="", author="", url=None,
         content="""Goal: finish the machine learning revision in three weeks.

Week 1: linear models and gradient descent, with two practice papers. Use spaced repetition for formulas.

Week 2: trees, ensembles and evaluation metrics. Sleep before every long session; no coffee after 2pm.

Week 3: neural networks and a full mock exam under timed conditions."""),
    dict(kind="pdf", status="library", fav=False, tags=["productivity"], days=3,
         title="Deep work: a field guide (demo PDF)", source="", author="Ana Ortiz", url=None,
         content="""Deep work is focused, uninterrupted effort on a cognitively demanding task. Shallow work is logistical and easy to interrupt.

Schedule deep work in blocks of 90 minutes, ideally in the morning when willpower is highest, and protect them like meetings.

Batch shallow work such as email into two or three fixed windows a day so it does not fragment your attention."""),
    dict(kind="article", status="inbox", fav=False, tags=["sleep"], days=1,
         title="The truth about blue light and sleep", source="Night Owl Journal (demo)", author="Priya Shah",
         url="https://nightowl.example/blue-light",
         content="""Evening light delays the release of melatonin, the hormone that signals night to the body. Bright overhead lighting matters more than phone screens.

Dim the lights an hour before bed and keep the bedroom cool and dark. Night-mode filters help a little, but the content you engage with keeps you awake more than the light does."""),
    dict(kind="newsletter", status="inbox", fav=False, tags=["habits"], days=0,
         title="Weekly reset: the two-minute rule", source="Better Weeks (demo)", author="Better Weeks", url=None,
         content="""If a task takes less than two minutes, do it now. If a new habit feels hard, scale it down until it takes two minutes.

This week's challenge: pick one habit, shrink it to two minutes, and attach it to something you already do every day."""),
    dict(kind="article", status="inbox", fav=False, tags=[], days=0,
         title="How to take smart notes", source="Paper Trail (demo)", author="Lee Park",
         url="https://papertrail.example/smart-notes",
         content="""Write notes in your own words and link each new note to the ones it relates to. Over time the links matter more than the notes.

Keep each note to one idea so it can be reused in many contexts. Review your notes when starting a project, not just when you take them."""),
    dict(kind="article", status="archived", fav=False, tags=["finance"], days=30,
         title="Budgeting with the 50/30/20 rule", source="Money Basics (demo)", author="Sam Lee",
         url="https://moneybasics.example/50-30-20",
         content="""Spend 50 percent of take-home pay on needs, 30 percent on wants and save 20 percent. Adjust the split when rent is high, but keep saving something every month."""),
]


def main() -> None:
    settings = Settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    now = utcnow()
    with Session() as db:
        old = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if old is not None:
            for item in db.query(Item).filter(Item.user_id == old.id):
                indexer.unindex(db, item)
            db.execute(delete(User).where(User.id == old.id))
            db.commit()

        user = User(email=DEMO_EMAIL, name="Swayam", password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()
        tags: dict[str, Tag] = {}
        for spec in ITEMS:
            item = Item(
                user_id=user.id, kind=spec["kind"], status=spec["status"], favorite=spec["fav"],
                title=spec["title"], url=spec["url"], source_name=spec["source"], author=spec["author"],
                content=spec["content"], has_transcript=spec["kind"] == "video",
                created_at=now - timedelta(days=spec["days"], hours=len(spec["title"]) % 7),
            )
            item.tags = [tags.setdefault(n, Tag(user_id=user.id, name=n)) for n in spec["tags"]]
            db.add(item)
            db.flush()
            indexer.reindex(db, item)
            if spec["status"] == "library":
                item.summary = summarize.summarize_extractive(item)
        db.flush()

        question = "What helps memory consolidation?"
        passages = retrieve(db, user.id, question)
        db.add(Question(
            user_id=user.id, question=question, source="passages",
            answer="No AI answer (Claude is not configured). These are the passages from your library that best match your question.",
            citations=[p.citation() for p in passages], created_at=now - timedelta(hours=3),
        ))
        db.commit()
        print(f"Demo library ready: {DEMO_EMAIL} -> {len(ITEMS)} items, {len(tags)} tags")
        print("Sign in with the password documented at the top of scripts/seed_demo.py.")
    engine.dispose()


if __name__ == "__main__":
    main()
