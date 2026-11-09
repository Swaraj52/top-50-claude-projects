"""Ask Your Library: BM25 retrieval over passages, then a grounded, cited answer."""

from __future__ import annotations

import re
from dataclasses import dataclass

import anthropic
from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from .ai import AIError, call_json
from .text import fts_query

MAX_PASSAGES = 8
PER_ITEM = 3

SYSTEM = """You answer questions using ONLY the numbered sources from the user's personal
library that are provided with the question. Each source is a passage from something they saved.

Rules:
- Base every statement on the sources. If they don't contain the answer, say so plainly
  and suggest what to search for instead; do not use outside knowledge.
- Cite sources inline as [S1], [S2] right after the statements they support.
- cited_sources: the numbers of the sources you actually used.
- confidence: "high" if the sources answer directly, "medium" if partially, "low" if barely.
- Be concise: a short paragraph or a few bullet points. Plain text, no headings."""

SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "cited_sources": {"type": "array", "items": {"type": "integer"}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["answer", "cited_sources", "confidence"],
    "additionalProperties": False,
}


@dataclass
class Passage:
    n: int
    chunk_id: int
    item_id: int
    title: str
    url: str | None
    text: str

    def citation(self) -> dict:
        excerpt = self.text if len(self.text) <= 500 else self.text[:500].rsplit(" ", 1)[0] + "…"
        return {"n": self.n, "item_id": self.item_id, "title": self.title, "url": self.url, "excerpt": excerpt}


def retrieve(db: DbSession, user_id: int, question: str, tag_id: int | None = None) -> list[Passage]:
    query = fts_query(question, mode="or")
    if not query:
        return []
    sql = """
        SELECT c.id, c.item_id, c.text, i.title, i.url
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        JOIN items i ON i.id = c.item_id
        WHERE chunks_fts MATCH :q AND c.user_id = :uid
    """
    params: dict = {"q": query, "uid": user_id}
    if tag_id is not None:
        sql += " AND c.item_id IN (SELECT item_id FROM item_tags WHERE tag_id = :tid)"
        params["tid"] = tag_id
    sql += " ORDER BY bm25(chunks_fts) LIMIT 40"
    rows = db.execute(text(sql), params).all()

    per_item: dict[int, int] = {}
    passages: list[Passage] = []
    for cid, item_id, body, title, url in rows:
        if per_item.get(item_id, 0) >= PER_ITEM:
            continue
        per_item[item_id] = per_item.get(item_id, 0) + 1
        passages.append(Passage(len(passages) + 1, cid, item_id, title, url, body))
        if len(passages) == MAX_PASSAGES:
            break
    return passages


def answer_ai(question: str, passages: list[Passage], client: anthropic.Anthropic, model: str) -> tuple[str, list[int], str]:
    sources = "\n\n".join(
        f"[S{p.n}] {p.title}{f' ({p.url})' if p.url else ''}\n{p.text}" for p in passages
    )
    content = f"Question: {question}\n\nSources:\n\n{sources}"
    data = call_json(client, model=model, system=SYSTEM, content=content, schema=SCHEMA, effort="medium")

    answer = str(data.get("answer", "")).strip()
    if not answer:
        raise AIError("the model returned an empty answer")
    valid = {p.n for p in passages}
    # Remove markers that point at sources we never sent.
    answer = re.sub(r"\[S(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in valid else "", answer)
    cited = [n for n in data.get("cited_sources", []) if isinstance(n, int) and n in valid]
    for m in re.finditer(r"\[S(\d+)\]", answer):
        n = int(m.group(1))
        if n not in cited:
            cited.append(n)
    confidence = data.get("confidence") if data.get("confidence") in ("high", "medium", "low") else "low"
    return answer[:6000], sorted(set(cited)), confidence
