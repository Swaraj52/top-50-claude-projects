"""Keep chunks and the FTS5 indexes in step with items."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DbSession

from ..models import Chunk, Item
from .text import chunk_text, word_count


def _drop_fts(db: DbSession, item_id: int) -> None:
    old_chunks = db.scalars(select(Chunk.id).where(Chunk.item_id == item_id)).all()
    for cid in old_chunks:
        db.execute(text("DELETE FROM chunks_fts WHERE rowid = :id"), {"id": cid})
    db.execute(text("DELETE FROM items_fts WHERE rowid = :id"), {"id": item_id})


def reindex(db: DbSession, item: Item) -> None:
    """Rebuild an item's passages and full-text rows. Call after any text/title/tag change."""
    db.flush()
    _drop_fts(db, item.id)
    db.query(Chunk).filter(Chunk.item_id == item.id).delete(synchronize_session=False)

    body = "\n\n".join(p for p in (item.description, item.content) if p)
    item.word_count = word_count(item.content)
    passages = chunk_text(item.content) or ([body] if body else [item.title])
    chunks = [Chunk(item_id=item.id, user_id=item.user_id, position=i, text=p) for i, p in enumerate(passages)]
    db.add_all(chunks)
    db.flush()

    tags = " ".join(t.name for t in item.tags)
    db.execute(
        text("INSERT INTO items_fts(rowid, title, tags, body) VALUES (:id, :title, :tags, :body)"),
        {"id": item.id, "title": item.title, "tags": tags, "body": body},
    )
    for c in chunks:
        # Prefixing the title lets a passage match questions phrased around the item's topic.
        db.execute(
            text("INSERT INTO chunks_fts(rowid, text) VALUES (:id, :text)"),
            {"id": c.id, "text": f"{item.title}\n{c.text}"},
        )


def unindex(db: DbSession, item: Item) -> None:
    _drop_fts(db, item.id)
