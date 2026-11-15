"""Optional Claude summaries and reply drafts, with a labelled local fallback.

The local writer in services/mail.py is always available. This module only upgrades the text when
the owner supplies an API key, and every failure falls back with an honest note.
"""

from __future__ import annotations

import json

import httpx

from .mail import DraftText, draft_local, summarise_local

SUMMARY_NOTE_LOCAL = "Local summary: the first sentences of the latest message; no model call."
DRAFT_NOTE_LOCAL = "Local draft scaffold: a template, not a model. Edit it before sending."
FALLBACK_NOTE = "Claude was unavailable or returned an invalid result; the local writer was used."

_SYSTEM = (
    "You help one person triage their own email. Be concise and factual. "
    "Never invent names, dates, amounts or commitments that are not in the thread. "
    "Return a single JSON object and nothing else."
)


def _transcript(thread, messages) -> str:
    parts = [f"Subject: {thread.subject}", f"Participants: {thread.participants}"]
    total = 0
    for message in list(messages)[-6:]:
        who = message.sender if message.direction == "in" else "me"
        body = " ".join((message.body or "").split())[:1600]
        block = f"[{message.received_at:%Y-%m-%d %H:%M} UTC] {who}: {body}"
        if total + len(block) > 6000:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts)


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
            "max_tokens": 700,
            "system": _SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=settings.ai_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    text = "".join(block.get("text", "") for block in payload.get("content", []))
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("model response was not a JSON object")
    return data


def _text(value, low: int, high: int) -> str:
    if not isinstance(value, str):
        raise ValueError("expected a string")
    cleaned = " ".join(value.split())
    if not low <= len(cleaned) <= high:
        raise ValueError("string length out of range")
    return cleaned


def _block(value, low: int, high: int) -> str:
    if not isinstance(value, str):
        raise ValueError("expected a string")
    cleaned = value.replace("\r\n", "\n").strip()
    if not low <= len(cleaned) <= high:
        raise ValueError("string length out of range")
    return cleaned


def summarise(settings, thread, messages) -> tuple[str, str, str]:
    """Return (summary, source, note)."""
    local = summarise_local(messages)
    if not settings.ai_enabled:
        return local, "local", SUMMARY_NOTE_LOCAL
    prompt = (
        "Summarise this email thread for its owner in two sentences. Keep the ask, any deadline "
        "and any decision. Do not add advice. Return JSON: {\"summary\": \"...\"}.\n\n"
        + _transcript(thread, messages)
    )
    try:
        data = _call(settings, prompt)
        return _text(data.get("summary"), 10, 800), "claude", ""
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return local, "local", FALLBACK_NOTE


def draft(settings, thread, messages, user, tone: str = "warm") -> tuple[DraftText, str, str]:
    """Return (draft, source, note)."""
    local = draft_local(thread, messages, user, tone)
    if not settings.ai_enabled:
        return local, "local", DRAFT_NOTE_LOCAL
    prompt = (
        f"Write a short reply in a {tone} tone from {user.name} to the latest message. "
        "Acknowledge the ask, do not promise anything not already agreed, and leave a clear place "
        "for any detail the owner must fill in. Use the signature supplied. "
        "Return JSON: {\"subject\": \"...\", \"body\": \"...\"}.\n"
        f"Signature: {user.name}" + (f", {user.signature}" if user.signature else "") + "\n\n"
        + _transcript(thread, messages)
    )
    try:
        data = _call(settings, prompt)
        subject = _text(data.get("subject"), 3, 200)
        body = _block(data.get("body"), 20, 4000)
        return DraftText(subject=subject, body=body), "claude", ""
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return local, "local", FALLBACK_NOTE
