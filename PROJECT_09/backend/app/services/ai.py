"""Optional Claude rewrite of the strategy memo.

The local memo in services/brief.py is always available and always grounded in stored inputs.
This module only improves the prose when an API key is configured; every failure keeps the local
memo and reports why.
"""

from __future__ import annotations

import json

import httpx

from .brief import prompt as build_prompt

SYSTEM = (
    "You are a strategy editor for a founder's own planning notes. Rewrite only from the facts "
    "supplied. Never invent a number, customer, date or competitor. Keep sentences short and "
    "concrete, and drop any claim the notes do not support. Return a single JSON object and "
    "nothing else."
)

FALLBACK_NOTE = "Claude was unavailable or returned an invalid result; the local memo is shown."

MIN_CHARS = 240
MAX_CHARS = 3600
MAX_PARAGRAPHS = 6


def _call(settings, prompt: str) -> dict:
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.anthropic_model,
            "max_tokens": 900,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=settings.ai_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    text = "".join(block.get("text", "") for block in payload.get("content", [])).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("model response was not a JSON object")
    return data


def narrative_text(value) -> str:
    """Validate and normalise the model's prose: 2-6 plain paragraphs, no headings or fences."""
    if not isinstance(value, str):
        raise ValueError("expected a string")
    text = value.replace("\r\n", "\n").strip()
    if "```" in text or "#" in text:
        raise ValueError("markdown headings or fences are not allowed")
    paragraphs = [" ".join(part.split()) for part in text.split("\n\n") if part.strip()]
    if not 2 <= len(paragraphs) <= MAX_PARAGRAPHS:
        raise ValueError("paragraph count out of range")
    if any(len(part) < 40 for part in paragraphs):
        raise ValueError("a paragraph is too short")
    cleaned = "\n\n".join(paragraphs)
    if not MIN_CHARS <= len(cleaned) <= MAX_CHARS:
        raise ValueError("narrative length out of range")
    return cleaned


def rewrite(settings, venture, memo_text: str, blocks: list[dict]) -> tuple[str | None, str]:
    """Return (narrative, note). A failure returns (None, note) so the caller keeps the local memo."""
    if not settings.ai_enabled:
        return None, "No API key is configured; the local memo is shown."
    try:
        data = _call(settings, build_prompt(venture, memo_text, blocks))
        return narrative_text(data.get("narrative")), ""
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return None, FALLBACK_NOTE
