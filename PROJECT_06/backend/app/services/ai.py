"""Optional Claude extraction with strict validation and a guaranteed local fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import httpx

from ..config import Settings
from .extract import ActionDraft, Extraction, extract

SYSTEM = """You extract structured meeting memory from pasted notes or a transcript.
Return JSON only, exactly:
{"summary":"...","decisions":["..."],"actions":[{"title":"...","owner":"...","due_date":"YYYY-MM-DD"}]}
Rules:
- Use only facts present in the notes. Do not invent owners, dates or decisions.
- A decision is something the group agreed or approved, not a topic discussed.
- An action is a concrete follow-up. Use an empty owner or due_date when the notes do not say.
- Keep summary under 600 characters, each decision under 450, each action under 240.
- Prefer 1-8 decisions and 1-12 actions. Empty arrays are allowed.
- No prose outside the JSON."""


@dataclass
class ExtractResult:
    extraction: Extraction
    source: str  # "claude" or "local"
    model: str | None = None
    note: str = ""


def _clean(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit].strip()


def _validate(payload: dict, day: date) -> tuple[str, list[str], list[ActionDraft]]:
    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")
    summary = _clean(payload.get("summary"), 600)
    raw_decisions = payload.get("decisions")
    raw_actions = payload.get("actions")
    if raw_decisions is None:
        raw_decisions = []
    if raw_actions is None:
        raw_actions = []
    if not isinstance(raw_decisions, list) or not isinstance(raw_actions, list):
        raise ValueError("decisions and actions must be lists")

    decisions = []
    for item in raw_decisions[:8]:
        text = _clean(item, 450)
        if len(text) >= 8:
            decisions.append(text)

    actions: list[ActionDraft] = []
    for item in raw_actions[:12]:
        if not isinstance(item, dict):
            continue
        title = _clean(item.get("title"), 240)
        if len(title) < 4:
            continue
        owner = _clean(item.get("owner"), 80)
        due = None
        raw_due = _clean(item.get("due_date"), 10)
        if raw_due:
            try:
                due = date.fromisoformat(raw_due)
            except ValueError:
                due = None
            if due and abs((due - day).days) > 730:
                due = None
        actions.append(ActionDraft(title=title, owner=owner, due_date=due))

    if len(summary) < 4:
        raise ValueError("summary is too short")
    return summary, decisions, actions


def _payload(meeting, notes: str, attendees: str) -> dict:
    return {
        "meeting": {
            "title": meeting.title[:160],
            "date": meeting.occurred_on.isoformat(),
            "attendees": attendees[:600],
        },
        "notes": notes[:12000],
    }


def _local_result(meeting, notes: str, attendees: str, note: str) -> ExtractResult:
    extraction = extract(notes, attendees, meeting.occurred_on)
    extraction.note = note
    return ExtractResult(extraction, "local", note=note)


def suggest(settings: Settings, meeting, notes: str, attendees: str) -> ExtractResult:
    """Return model extraction when configured, otherwise the local extractor."""
    local_note = "Local extractor: rules only, no model call."
    if not settings.ai_enabled:
        return _local_result(meeting, notes, attendees, local_note)

    body = {
        "model": settings.anthropic_model,
        "max_tokens": 1400,
        "system": SYSTEM,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(_payload(meeting, notes, attendees), ensure_ascii=False),
            }
        ],
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
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        summary, decisions, actions = _validate(json.loads(text), meeting.occurred_on)
        if not decisions and not actions and len(summary) < 40:
            raise ValueError("nothing useful extracted")
        extraction = Extraction(summary=summary, decisions=decisions, actions=actions)
        extraction.attendees = extract(notes, attendees, meeting.occurred_on).attendees
        return ExtractResult(extraction, "claude", model=settings.anthropic_model, note="")
    except Exception:
        return _local_result(
            meeting,
            notes,
            attendees,
            "Claude was unavailable or returned an invalid result; the local extractor was used.",
        )
