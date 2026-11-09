from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DbSession, selectinload

from ..deps import current_user, get_db
from ..models import Item, User
from ..schemas import ItemCard, SearchHit, SearchOut
from ..services.text import HIGHLIGHT_END, HIGHLIGHT_START, fts_query

router = APIRouter(tags=["search"])

SQL = f"""
    SELECT i.id, snippet(items_fts, 2, '{HIGHLIGHT_START}', '{HIGHLIGHT_END}', '…', 24)
    FROM items_fts JOIN items i ON i.id = items_fts.rowid
    WHERE items_fts MATCH :q AND i.user_id = :uid {{status}}
    ORDER BY bm25(items_fts, 10.0, 5.0, 1.0)
    LIMIT 50
"""


@router.get("/search", response_model=SearchOut)
def search(
    q: str = Query(min_length=1, max_length=300),
    include_archived: bool = False,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    sql = SQL.format(status="" if include_archived else "AND i.status != 'archived'")
    mode: Literal["all", "any"] = "all"
    rows = []
    for mode in ("all", "any"):
        query = fts_query(q, "and" if mode == "all" else "or")
        if not query:
            break
        rows = db.execute(text(sql), {"q": query, "uid": user.id}).all()
        if rows:
            break
    ids = [r[0] for r in rows]
    items = {i.id: i for i in db.scalars(select(Item).options(selectinload(Item.tags)).where(Item.id.in_(ids)))}
    hits = [
        SearchHit(item=ItemCard.of(items[item_id]), snippet=snip or items[item_id].description[:240])
        for item_id, snip in rows
        if item_id in items
    ]
    return SearchOut(query=q, hits=hits, mode=mode)
