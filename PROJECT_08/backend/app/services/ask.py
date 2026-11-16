"""Extractive answers built from the best matching passages.

This is not a model. It quotes the library, names the item each sentence came from and
says how many passages it read. When Claude is enabled the route may replace the prose,
but the citations always come from the same local results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .search import Hit, Query


@dataclass
class Citation:
    item_id: int
    title: str
    sentence: str
    kind: str


@dataclass
class Answer:
    text: str
    citations: list[Citation] = field(default_factory=list)
    source: str = "local"
    note: str = ""
    read: int = 0


def _sentences(body: str) -> list[str]:
    text = re.sub(r"\s+", " ", (body or "").replace("\n", " ")).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if len(part.strip()) >= 20][:40]


def best_sentence(body: str, terms: list[str], fallback: int = 260) -> str:
    sentences = _sentences(body)
    if not sentences:
        return re.sub(r"\s+", " ", (body or "")).strip()[:fallback]
    wanted = [term.lower() for term in terms if len(term) > 1]
    scored: list[tuple[int, int, str]] = []
    for position, sentence in enumerate(sentences):
        lowered = sentence.lower()
        score = sum(lowered.count(term) for term in wanted)
        scored.append((score, -position, sentence))
    scored.sort(reverse=True)
    best = scored[0]
    chosen = best[2] if best[0] > 0 else sentences[0]
    return chosen[:fallback] + ("…" if len(chosen) > fallback else "")


def compose(question: str, query: Query, hits: list[Hit]) -> Answer:
    if not hits:
        subject = ", ".join(query.terms_display) or "that question"
        return Answer(
            text=(
                f"Nothing in this library matches {subject}. Try fewer words, drop a filter, "
                "or add an item that covers it."
            ),
            source="local",
            note="No passage was read, so there is nothing to quote.",
            read=0,
        )

    citations: list[Citation] = []
    seen: set[int] = set()
    for hit in hits:
        if hit.item.id in seen:
            continue
        seen.add(hit.item.id)
        citations.append(
            Citation(
                item_id=hit.item.id,
                title=hit.item.title,
                sentence=best_sentence(hit.item.body, [*query.terms, *query.expansions]),
                kind=hit.item.kind,
            )
        )
        if len(citations) >= 3:
            break

    subject = ", ".join(query.terms_display) if query.terms_display else "this question"
    lead = (
        f"Read {len(citations)} of the closest passages. "
        f"Matched words: {subject}. The library's own words, in order of relevance:"
    )
    body = " ".join(f"“{citation.sentence}” — {citation.title}." for citation in citations)
    note = (
        "Local extractive answer: sentences are quoted from your items, not generated. "
        "Follow the citations to read each source in full."
    )
    return Answer(text=f"{lead} {body}", citations=citations, source="local", note=note, read=len(citations))


def passages_for_model(hits: list[Hit], limit: int = 4, width: int = 700) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for hit in hits[:limit]:
        text = re.sub(r"\s+", " ", hit.item.body or "").strip()
        out.append(
            {
                "title": hit.item.title,
                "kind": hit.item.kind,
                "text": text[:width] + ("…" if len(text) > width else ""),
            }
        )
    return out
