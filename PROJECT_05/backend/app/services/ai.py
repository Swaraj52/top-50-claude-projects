"""Optional Claude habit coach with a deterministic, labelled fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date

import httpx

from ..config import Settings
from ..models import Habit, HabitLog
from ..timeutil import parse_days
from . import habitmath
from .coach import Suggestion, rule_suggestions

log = logging.getLogger("cadence.ai")

SYSTEM = """You are a practical habit coach. Using only the supplied habit, schedule, logs and
computed stats, suggest 2 to 4 realistic changes for the next two weeks. Rules:
- Prefer changing the environment, cue, schedule or size of the habit over adding willpower.
- Do not invent facts, events or resources that are not in the input.
- If the habit is being missed, shrink it or reduce the schedule; never prescribe more effort.
- Keep advice concrete enough to do tomorrow.
- Return JSON only, exactly: {"suggestions":[{"title":"...","rationale":"..."}]}
- Titles max 120 characters; rationales max 380 characters."""


@dataclass
class CoachResult:
    suggestions: list[Suggestion]
    source: str  # "claude" or "local"
    model: str | None = None
    note: str = ""


def _validate(payload: dict) -> list[Suggestion]:
    raw = payload.get("suggestions")
    if not isinstance(raw, list):
        raise ValueError("suggestions is not a list")
    out: list[Suggestion] = []
    for item in raw[:4]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        if not 4 <= len(title) <= 120 or not 10 <= len(rationale) <= 380:
            continue
        out.append(Suggestion(title=title, rationale=rationale))
    if len(out) < 2:
        raise ValueError("too few valid suggestions")
    return out


def _payload(habit: Habit, logs: list[HabitLog], today: date) -> dict:
    stats = habitmath.habit_stats(habit, logs, today)
    recent = sorted(logs, key=lambda l: l.day)[-21:]
    return {
        "today": today.isoformat(),
        "habit": {
            "title": habit.title,
            "intention": habit.intention[:500],
            "cue": habit.cue[:200],
            "schedule": parse_days(habit.days),
            "created_on": habit.created_at.date().isoformat(),
            "status": habit.status,
        },
        "stats": stats,
        "recent_logs": [{"day": log.day.isoformat(), "status": log.status, "note": log.note[:200]} for log in recent],
    }


def suggest(settings: Settings, habit: Habit, logs: list[HabitLog], today: date) -> CoachResult:
    local = rule_suggestions(habit, logs, today, limit=3)
    if not settings.ai_enabled:
        return CoachResult(local, "local", note="Local coach: no API key configured.")

    body = {
        "model": settings.anthropic_model,
        "max_tokens": 1000,
        "temperature": 0,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": json.dumps(_payload(habit, logs, today))}],
    }
    try:
        with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
        suggestions = _validate(json.loads(text))
        return CoachResult(suggestions, "claude", model=settings.anthropic_model, note="Suggestions written by Claude and checked for length and shape.")
    except Exception as exc:
        log.warning("Claude coach failed, using local coach: %s", type(exc).__name__)
        return CoachResult(local, "local", note=f"Claude was unavailable ({type(exc).__name__}); the local coach wrote this.")
