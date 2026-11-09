"""Item summaries: Claude when configured, otherwise a labelled extractive summary."""

from __future__ import annotations

from datetime import datetime, timezone

import anthropic

from ..models import Item
from .ai import AIError, call_json
from .text import extractive_summary, keywords, normalize_tag

MAX_INPUT_CHARS = 120_000

SYSTEM = """You summarise items saved in a personal reading library (articles, newsletters,
video transcripts, PDFs and notes). Write for the person who saved it and will come back later.

- tldr: one or two plain sentences capturing the main point.
- key_points: three to six short, concrete takeaways (facts, arguments, numbers, advice).
- suggested_tags: up to five short lowercase topic tags (one or two words, use hyphens).

Use only what the text says; do not add outside facts. If the text is a transcript, ignore
filler and timestamps."""

SCHEMA = {
    "type": "object",
    "properties": {
        "tldr": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "suggested_tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tldr", "key_points", "suggested_tags"],
    "additionalProperties": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_text(item: Item) -> str:
    return item.content or item.description or ""


def summarize_ai(item: Item, client: anthropic.Anthropic, model: str) -> dict:
    text = _source_text(item)
    if not text.strip():
        raise AIError("this item has no text to summarise")
    truncated = len(text) > MAX_INPUT_CHARS
    header = f"Title: {item.title}\nType: {item.kind}\nSource: {item.source_name or item.url or 'unknown'}\n"
    content = f"{header}\n<text>\n{text[:MAX_INPUT_CHARS]}\n</text>"
    data = call_json(client, model=model, system=SYSTEM, content=content, schema=SCHEMA, effort="low")

    tldr = str(data.get("tldr", "")).strip()
    points = [str(p).strip()[:400] for p in data.get("key_points", []) if str(p).strip()][:6]
    if not tldr:
        raise AIError("the model returned an empty summary")
    tags = []
    for t in data.get("suggested_tags", []):
        name = normalize_tag(str(t))
        if name and name not in tags:
            tags.append(name)
    return {
        "source": "ai",
        "model": model,
        "tldr": tldr[:800],
        "key_points": points,
        "suggested_tags": tags[:5],
        "truncated": truncated,
        "note": "Summary based on the first 120,000 characters." if truncated else None,
        "created_at": _now(),
    }


def summarize_extractive(item: Item, note: str | None = None) -> dict:
    text = _source_text(item)
    tldr, points = extractive_summary(text) if text.strip() else (item.title, [])
    return {
        "source": "extractive",
        "model": None,
        "tldr": tldr[:800],
        "key_points": [p[:400] for p in points],
        "suggested_tags": [t for t in (normalize_tag(k) for k in keywords(text)) if t][:5],
        "truncated": False,
        "note": note,
        "created_at": _now(),
    }
