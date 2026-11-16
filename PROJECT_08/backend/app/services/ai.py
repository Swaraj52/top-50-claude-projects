"""Optional Claude answers over the local search results.

The local answer in services/ask.py is always available and always cites items. This module
only upgrades the prose when an API key is present, and every failure falls back with a note.
"""

from __future__ import annotations

import json

import httpx

from .ask import Answer, passages_for_model

SYSTEM = (
    "You answer questions using only the passages supplied from one person's own library. "
    "Quote or paraphrase those passages and never add facts that are not there. "
    "If the passages do not answer the question, say so plainly. "
    "Return a single JSON object and nothing else."
)

FALLBACK_NOTE = "Claude was unavailable or returned an invalid result; the local extractive answer was used."


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


def _answer_text(value) -> str:
    if not isinstance(value, str):
        raise ValueError("expected a string")
    cleaned = " ".join(value.split())
    if not 20 <= len(cleaned) <= 1600:
        raise ValueError("answer length out of range")
    return cleaned


def upgrade(settings, question: str, local: Answer, hits) -> tuple[Answer, str]:
    """Return the answer to show and a note. Claude failure returns the local answer unchanged."""
    if not settings.ai_enabled or not local.citations:
        return local, local.note
    passages = passages_for_model(hits)
    prompt = (
        f"Question: {question.strip()[:500]}\n\n"
        "Passages from the library:\n"
        + "\n\n".join(
            f"[{index + 1}] {passage['title']} ({passage['kind']})\n{passage['text']}"
            for index, passage in enumerate(passages)
        )
        + "\n\nAnswer in two to five sentences and cite passages by number. "
        'Return JSON: {"answer": "..."}.'
    )
    try:
        data = _call(settings, prompt)
        text = _answer_text(data.get("answer"))
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return local, FALLBACK_NOTE
    return Answer(
        text=text,
        citations=local.citations,
        source="claude",
        note="Claude wrote this answer from the quoted passages only. Check the citations.",
        read=local.read,
    ), ""
