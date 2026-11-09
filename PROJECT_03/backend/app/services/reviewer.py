"""End-of-day review: Claude writes it when configured, otherwise transparent rules do.

The deterministic planner always produces the candidate plan; the AI may re-order it but can
only choose tasks that already exist, and the result is re-checked against capacity.
"""

from __future__ import annotations

import json
from datetime import date

import anthropic

from .ai import AIError, call_json
from .day import DaySnapshot
from .planner import PlanItem

QUESTIONS = [
    "What gave you the most energy today, and how can you get more of it tomorrow?",
    "Which task did you avoid, and what is the smallest next step on it?",
    "What would make tomorrow a good day, even if everything else slips?",
    "What did you learn today that you want to remember next week?",
    "Where did your time go that you didn't plan for?",
    "Who helped you today, or who could you help tomorrow?",
    "What is one thing you can stop doing?",
    "If you only finish one thing tomorrow, what should it be?",
]

SYSTEM = """You write a short end-of-day review for a productivity app. You receive a JSON
snapshot of the user's day (finished tasks, work log, wins, learnings, open blockers, energy and
focus) and a list of CANDIDATE tasks for tomorrow with ids, estimates and the reasons they matter.

Write, in second person, warm but direct, no emoji:
- headline: under 80 characters, the shape of the day.
- recap: 2-4 sentences on what actually got done and how the day went. Use only the snapshot.
- wins: up to 3 short wins worth remembering (from done tasks / wins). Empty if none.
- blockers: up to 3 short notes on what is blocking progress and one concrete next step each.
- tomorrow_focus: the tasks to do first tomorrow, in order, chosen ONLY from the candidate ids,
  each with a one-sentence why. Respect the capacity: the estimates of chosen tasks should fit
  within capacity_minutes. Prefer overdue, high-priority and repeatedly carried tasks.
- reflection_question: one question to end the day with.

Never invent tasks, people or events."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "recap": {"type": "string"},
        "wins": {"type": "array", "items": {"type": "string"}},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "tomorrow_focus": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}, "why": {"type": "string"}},
                "required": ["task_id", "why"],
                "additionalProperties": False,
            },
        },
        "reflection_question": {"type": "string"},
    },
    "required": ["headline", "recap", "wins", "blockers", "tomorrow_focus", "reflection_question"],
    "additionalProperties": False,
}


def question_for(day: date) -> str:
    return QUESTIONS[day.toordinal() % len(QUESTIONS)]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def rule_review(snap: DaySnapshot, plan: list[PlanItem], recurring: list[str], carried: int) -> dict:
    done = snap.done
    logged = snap.entries("done")
    wins = [e.text for e in snap.entries("win")][:3] or [t.title for t in done if t.priority == 1][:3]
    if done or logged:
        bits = [t.title for t in done][:3] or [e.text for e in logged][:3]
        recap = f"You finished {_plural(len(done), 'task')}" + (f" and logged {_plural(len(logged), 'piece')} of work" if logged else "")
        recap += f", including {', '.join(f'“{b}”' for b in bits)}."
    else:
        recap = "Nothing was marked as finished today."
    if snap.checkin:
        recap += f" Focus: {snap.checkin.focus_hours:g} h, energy {snap.checkin.energy}/5."
    if carried:
        recap += f" {_plural(carried, 'task')} will carry over to tomorrow."

    def age(b) -> str:
        days = (snap.day - b.opened_on).days
        return "opened today" if days == 0 else f"open for {_plural(days, 'day')}"

    blockers = [f"“{b.text}” ({age(b)}): name one person or action that unblocks it." for b in snap.blockers_open[:3]]
    blockers += recurring[:2]

    headline_bits = [f"{len(done)} done"]
    if carried:
        headline_bits.append(f"{carried} carried over")
    if snap.blockers_open:
        headline_bits.append(_plural(len(snap.blockers_open), "open blocker"))
    headline = " · ".join(headline_bits) if done or carried or snap.blockers_open else "A quiet day"

    return {
        "headline": headline,
        "recap": recap,
        "wins": wins,
        "blockers": blockers[:4],
        "tomorrow_focus": [{"task_id": p.task_id, "title": p.title, "why": "; ".join(p.reasons).capitalize()} for p in plan[:3]],
        "reflection_question": question_for(snap.day),
    }


def snapshot_json(snap: DaySnapshot, candidates: list[PlanItem], recurring: list[str]) -> str:
    return json.dumps(
        {
            "date": snap.day.isoformat(),
            "finished_tasks": [{"title": t.title, "area": t.area, "priority": t.priority} for t in snap.done],
            "work_log": [{"kind": e.kind, "text": e.text, "minutes": e.minutes} for e in snap.log],
            "open_blockers": [{"text": b.text, "open_days": (snap.day - b.opened_on).days} for b in snap.blockers_open],
            "recurring_blockers": recurring,
            "checkin": (
                {"energy": snap.checkin.energy, "mood": snap.checkin.mood, "focus_hours": snap.checkin.focus_hours}
                if snap.checkin
                else None
            ),
            "capacity_minutes": snap.capacity_min,
            "candidates": [
                {"task_id": c.task_id, "title": c.title, "estimate_minutes": c.estimate_min, "reasons": c.reasons} for c in candidates
            ],
        },
        ensure_ascii=False,
    )


def ai_review(snap: DaySnapshot, candidates: list[PlanItem], recurring: list[str], client: anthropic.Anthropic, model: str) -> tuple[dict, list[int]]:
    data = call_json(client, model=model, system=SYSTEM, content=snapshot_json(snap, candidates, recurring), schema=SCHEMA, effort="low")
    missing = [k for k in SCHEMA["required"] if k not in data]
    if missing or not str(data.get("recap", "")).strip():
        raise AIError("the model returned an incomplete review")
    by_id = {c.task_id: c for c in candidates}
    focus, order = [], []
    for f in data.get("tomorrow_focus", []):
        tid = f.get("task_id") if isinstance(f, dict) else None
        if isinstance(tid, int) and tid in by_id and tid not in order:
            order.append(tid)
            focus.append({"task_id": tid, "title": by_id[tid].title, "why": str(f.get("why", ""))[:300]})
    content = {
        "headline": str(data["headline"])[:120],
        "recap": str(data["recap"])[:1200],
        "wins": [str(w)[:200] for w in data.get("wins", [])][:3],
        "blockers": [str(b)[:300] for b in data.get("blockers", [])][:4],
        "tomorrow_focus": focus[:5],
        "reflection_question": str(data.get("reflection_question", ""))[:300] or question_for(snap.day),
    }
    return content, order
