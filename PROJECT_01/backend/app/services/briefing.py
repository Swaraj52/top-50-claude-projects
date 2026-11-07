"""Daily briefing: a context snapshot of the day, summarised by Claude or by rules.

The AI path is optional. When it is unavailable or fails, the rule-based summary is
used and labelled as such; it is never presented as AI output.
"""

from __future__ import annotations

import json
import logging
import time as clock
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import anthropic
from pydantic import ValidationError

from ..schemas import BriefingContent, FocusItem

log = logging.getLogger(__name__)

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
WORKDAY = (time(8, 0), time(18, 0))

SYSTEM_PROMPT = """You write the morning briefing inside a personal dashboard app.
You receive a JSON snapshot of the user's day: calendar events, tasks (overdue, due today,
coming up), reminders, emails that need attention and the priorities they already chose.

Write a briefing that helps them decide what to do first:
- headline: one short line (under 90 characters) capturing the shape of the day.
- summary: two to four plain sentences. Mention the busiest stretch, anything overdue, and
  how much free time there is. Use the times exactly as given (they are already local).
- schedule_notes: up to five short notes about the schedule (conflicts, back-to-back meetings,
  the best block for focused work, all-day events). Empty if there is nothing useful to say.
- focus: up to three suggested priorities. Prefer overdue and due-today tasks with higher
  priority. When a suggestion is an existing task, set task_id to that task's id; otherwise
  null. Give a brief reason for each.
- heads_up: up to four short warnings (reminders with times, emails from people waiting on a
  reply, deadlines tomorrow). Empty if none.

Only use facts from the snapshot. Do not invent meetings, people or tasks. If the day is
empty, say so plainly and suggest using the time for planning. Write in a calm, direct tone,
second person, no emoji."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "schedule_notes": {"type": "array", "items": {"type": "string"}},
        "focus": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "task_id": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                },
                "required": ["title", "reason", "task_id"],
                "additionalProperties": False,
            },
        },
        "heads_up": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "summary", "schedule_notes", "focus", "heads_up"],
    "additionalProperties": False,
}


class AIBriefingError(Exception):
    """The AI briefing could not be produced; message is safe to show the user."""


@dataclass
class DayContext:
    day: date
    tz: ZoneInfo
    now_local: datetime
    events: list[dict]  # {title, start, end, all_day, location}
    overdue: list[dict]  # {id, title, priority, due_date}
    due_today: list[dict]
    upcoming: list[dict]  # next 3 days
    reminders: list[dict]  # {text, time}
    emails: list[dict]  # {from, subject, flagged, unread}
    priorities: list[dict]  # {text, done}

    def to_prompt_json(self) -> str:
        return json.dumps(
            {
                "date": self.day.isoformat(),
                "weekday": self.day.strftime("%A"),
                "local_time_now": self.now_local.strftime("%H:%M"),
                "timezone": str(self.tz),
                "events_today": self.events,
                "tasks_overdue": self.overdue,
                "tasks_due_today": self.due_today,
                "tasks_next_3_days": self.upcoming,
                "reminders_today": self.reminders,
                "emails_needing_attention": self.emails,
                "priorities_already_chosen": self.priorities,
            },
            ensure_ascii=False,
            indent=1,
        )

    @property
    def task_ids(self) -> set[int]:
        return {t["id"] for t in self.overdue + self.due_today + self.upcoming}


# --- AI path ------------------------------------------------------------------------


def generate_ai(ctx: DayContext, client: anthropic.Anthropic, model: str) -> BriefingContent:
    started = clock.monotonic()
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": ctx.to_prompt_json()}],
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as exc:
        raise AIBriefingError("the Anthropic API key was rejected") from exc
    except anthropic.PermissionDeniedError as exc:
        raise AIBriefingError("the Anthropic API key lacks permission for this model") from exc
    except anthropic.NotFoundError as exc:
        raise AIBriefingError(f"model '{model}' is not available to this API key") from exc
    except anthropic.RateLimitError as exc:
        raise AIBriefingError("the Anthropic API rate limit was reached") from exc
    except anthropic.APIStatusError as exc:
        raise AIBriefingError(f"the Anthropic API returned an error ({exc.status_code})") from exc
    except anthropic.APIConnectionError as exc:  # includes timeouts
        raise AIBriefingError("the Anthropic API could not be reached") from exc

    log.info(
        "AI briefing: model=%s stop=%s request_id=%s in %.1fs",
        getattr(response, "model", model),
        response.stop_reason,
        getattr(response, "_request_id", None),
        clock.monotonic() - started,
    )
    if response.stop_reason == "refusal":
        raise AIBriefingError("the model declined to write this briefing")
    if response.stop_reason == "max_tokens":
        raise AIBriefingError("the model's answer was cut off")
    text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
    try:
        content = BriefingContent.model_validate(_clamp(json.loads(text)))
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise AIBriefingError("the model returned an answer in an unexpected format") from exc

    valid_ids = ctx.task_ids
    for item in content.focus:
        if item.task_id is not None and item.task_id not in valid_ids:
            item.task_id = None
    return content


def _clamp(data: dict) -> dict:
    """Trim over-long fields so a verbose but well-formed answer still validates."""
    if not isinstance(data, dict):
        raise TypeError("expected an object")
    missing = [k for k in OUTPUT_SCHEMA["required"] if k not in data]
    if missing:
        raise TypeError(f"missing fields: {missing}")
    if not str(data["headline"]).strip() or not str(data["summary"]).strip():
        raise TypeError("empty headline or summary")
    data["headline"] = str(data.get("headline", ""))[:200]
    data["summary"] = str(data.get("summary", ""))[:1200]
    data["schedule_notes"] = [str(s)[:300] for s in data.get("schedule_notes", [])][:6]
    data["heads_up"] = [str(s)[:300] for s in data.get("heads_up", [])][:5]
    focus = []
    for item in list(data.get("focus", []))[:3]:
        if isinstance(item, dict):
            focus.append(
                {
                    "title": str(item.get("title", ""))[:200],
                    "reason": str(item.get("reason", ""))[:300],
                    "task_id": item.get("task_id"),
                }
            )
    data["focus"] = focus
    return data


# --- rule-based path ----------------------------------------------------------------


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _free_blocks(events: list[dict]) -> list[tuple[int, int]]:
    """Free gaps of 30+ minutes inside the 08:00-18:00 workday."""
    day_start = WORKDAY[0].hour * 60
    day_end = WORKDAY[1].hour * 60
    busy = sorted(
        (max(_minutes(e["start"]), day_start), min(_minutes(e["end"]), day_end))
        for e in events
        if not e["all_day"]
    )
    gaps, cursor = [], day_start
    for start, end in busy:
        if start - cursor >= 30:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if day_end - cursor >= 30:
        gaps.append((cursor, day_end))
    return gaps


def generate_rule_based(ctx: DayContext) -> BriefingContent:
    timed = [e for e in ctx.events if not e["all_day"]]
    all_day = [e for e in ctx.events if e["all_day"]]
    n_over, n_today = len(ctx.overdue), len(ctx.due_today)

    parts = []
    if timed:
        first = timed[0]
        parts.append(
            f"You have {_plural(len(timed), 'event')} today, starting with "
            f"\"{first['title']}\" at {first['start']}."
        )
    else:
        parts.append("Your calendar has no timed events today.")
    if n_today or n_over:
        parts.append(
            f"{_plural(n_today, 'task')} {'is' if n_today == 1 else 'are'} due today"
            + (f" and {n_over} {'is' if n_over == 1 else 'are'} overdue." if n_over else ".")
        )
    else:
        parts.append("No tasks are due today.")
    if ctx.reminders:
        parts.append(f"{_plural(len(ctx.reminders), 'reminder')} will go off today.")
    if ctx.emails:
        n = len(ctx.emails)
        parts.append(f"{_plural(n, 'email')} {'needs' if n == 1 else 'need'} attention.")

    if not ctx.events and not n_over and not n_today:
        headline = "A clear day: nothing scheduled and nothing due"
    else:
        bits = []
        if timed:
            bits.append(_plural(len(timed), "meeting"))
        if n_today:
            bits.append(f"{n_today} due")
        if n_over:
            bits.append(f"{n_over} overdue")
        headline = ", ".join(bits) if bits else "A light day ahead"

    notes = [f"All day: {e['title']}" for e in all_day[:2]]
    for prev, nxt in zip(timed, timed[1:]):
        if _minutes(nxt["start"]) < _minutes(prev["end"]):
            notes.append(f"\"{prev['title']}\" overlaps \"{nxt['title']}\" at {nxt['start']}.")
        elif _minutes(nxt["start"]) - _minutes(prev["end"]) < 10:
            notes.append(f"Back-to-back: \"{prev['title']}\" then \"{nxt['title']}\" at {nxt['start']}.")
    gaps = _free_blocks(ctx.events)
    if gaps:
        start, end = max(gaps, key=lambda g: g[1] - g[0])
        notes.append(f"Longest free block: {_fmt(start)}-{_fmt(end)} ({(end - start) // 60}h {(end - start) % 60}m).")
    elif timed:
        notes.append("No free block of 30 minutes or more between 08:00 and 18:00.")

    candidates = sorted(
        [(0, t) for t in ctx.overdue] + [(1, t) for t in ctx.due_today],
        key=lambda pair: (PRIORITY_ORDER.get(pair[1]["priority"], 3), pair[0]),
    )
    focus = []
    for kind, task in candidates[:3]:
        when = f"overdue since {task['due_date']}" if kind == 0 else "due today"
        focus.append(FocusItem(title=task["title"], reason=f"{task['priority'].capitalize()} priority, {when}", task_id=task["id"]))
    if not focus and ctx.upcoming:
        task = ctx.upcoming[0]
        focus.append(FocusItem(title=task["title"], reason=f"Next deadline: {task['due_date']}", task_id=task["id"]))

    heads_up = [f"Reminder at {r['time']}: {r['text']}" for r in ctx.reminders[:3]]
    flagged = [e for e in ctx.emails if e.get("flagged")]
    if flagged:
        heads_up.append(f"Flagged email from {flagged[0]['from']}: \"{flagged[0]['subject']}\"")
    if n_over > 3:
        heads_up.append(f"{n_over} overdue tasks: consider rescheduling the ones that can wait.")

    return BriefingContent(
        headline=headline[:200],
        summary=" ".join(parts)[:1200],
        schedule_notes=notes[:6],
        focus=focus[:3],
        heads_up=heads_up[:5],
    )
