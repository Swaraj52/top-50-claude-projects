"""Optional Claude integration with a deterministic, labelled fallback.

The app is fully usable without an API key. When ANTHROPIC_API_KEY is set, the coach asks
Claude for a JSON action plan; every field is validated and any failure falls back to the
local planner. No output is ever presented as AI-written unless the API call succeeded.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date

import httpx

from ..config import Settings
from ..models import Checkin, Goal, Milestone
from . import goalmath
from .coach import Suggestion, rule_plan

log = logging.getLogger("summit.ai")

SYSTEM = """You are a pragmatic goal coach. Turn the supplied goal, milestones, recent actions
and check-ins into 3 to 5 concrete actions for one week. Rules:
- Each action must be completable in one sitting (10-120 minutes).
- Prefer advancing an existing open milestone; use its id as milestone_id.
- Do not invent facts, deadlines or resources that are not in the input.
- If progress is behind, recommend cutting scope rather than working more hours.
- Return JSON only, exactly: {"actions":[{"title":"...","rationale":"...","estimate_min":45,"milestone_id":1}]}
- milestone_id may be null. Titles max 120 characters; rationales max 240 characters."""


@dataclass
class CoachResult:
    suggestions: list[Suggestion]
    source: str  # "claude" or "local"
    model: str | None = None
    note: str = ""


def _validate(payload: dict, allowed_ids: set[int]) -> list[Suggestion]:
    raw = payload.get("actions")
    if not isinstance(raw, list):
        raise ValueError("actions is not a list")
    out: list[Suggestion] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        if not 4 <= len(title) <= 120 or not rationale:
            continue
        try:
            estimate = int(item.get("estimate_min", 45))
        except (TypeError, ValueError):
            estimate = 45
        estimate = max(10, min(120, estimate))
        mid = item.get("milestone_id")
        try:
            mid = int(mid) if mid is not None else None
        except (TypeError, ValueError):
            mid = None
        if mid not in allowed_ids:
            mid = None
        out.append(Suggestion(title=title[:120], rationale=rationale[:240], estimate_min=estimate, milestone_id=mid))
    if len(out) < 2:
        raise ValueError("too few valid actions")
    return out


def _payload(goal: Goal, milestones: list[Milestone], checkins: list[Checkin], today: date, week_start: date) -> dict:
    return {
        "today": today.isoformat(),
        "week_start": week_start.isoformat(),
        "goal": {
            "title": goal.title,
            "description": goal.description[:1200],
            "why": goal.why[:600],
            "category": goal.category,
            "target_date": goal.target_date.isoformat() if goal.target_date else None,
            "progress_percent": goalmath.progress(goal),
            "pace": goalmath.pace(goal, today),
        },
        "milestones": [
            {
                "id": m.id,
                "title": m.title,
                "weight": m.weight,
                "status": m.status,
                "due_date": m.due_date.isoformat() if m.due_date else None,
            }
            for m in milestones
        ],
        "recent_checkins": [
            {"day": c.day.isoformat(), "confidence": c.confidence, "note": c.note[:300]}
            for c in sorted(checkins, key=lambda c: c.day)[-6:]
        ],
    }


def plan(settings: Settings, goal: Goal, milestones: list[Milestone], checkins: list[Checkin], today: date, week_start: date) -> CoachResult:
    local = rule_plan(goal, milestones, checkins, today, week_start)
    if not settings.ai_enabled:
        return CoachResult(local, "local", note="Local planner: no API key configured.")

    body = {
        "model": settings.anthropic_model,
        "max_tokens": 1200,
        "temperature": 0,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": json.dumps(_payload(goal, milestones, checkins, today, week_start))}],
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
        suggestions = _validate(json.loads(text), {m.id for m in milestones})
        return CoachResult(suggestions, "claude", model=settings.anthropic_model, note="Plan written by Claude; validated against this goal.")
    except Exception as exc:  # network, HTTP, JSON, validation
        log.warning("Claude coach failed, using local planner: %s", type(exc).__name__)
        return CoachResult(local, "local", note=f"Claude was unavailable ({type(exc).__name__}); the local planner wrote this plan.")
