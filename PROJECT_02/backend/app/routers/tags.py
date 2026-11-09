from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..deps import current_user, get_db, get_owned
from ..models import Tag, User, item_tags
from ..schemas import TagOut, TagRename
from ..services import indexer
from ..services.text import normalize_tag

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    rows = db.execute(
        select(Tag.id, Tag.name, func.count(item_tags.c.item_id))
        .outerjoin(item_tags, item_tags.c.tag_id == Tag.id)
        .where(Tag.user_id == user.id)
        .group_by(Tag.id)
        .order_by(func.count(item_tags.c.item_id).desc(), Tag.name)
    ).all()
    return [TagOut(id=i, name=n, count=c) for i, n, c in rows]


@router.patch("/{tag_id}", response_model=TagOut)
def rename_tag(tag_id: int, body: TagRename, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    tag = get_owned(db, Tag, tag_id, user)
    name = normalize_tag(body.name)
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tag names need letters or numbers")
    items = list(tag.items)
    target = db.scalar(select(Tag).where(Tag.user_id == user.id, Tag.name == name, Tag.id != tag.id))
    if target is not None:  # renaming onto an existing tag merges the two
        for item in items:
            if target not in item.tags:
                item.tags.append(target)
            item.tags.remove(tag)
        db.delete(tag)
        tag = target
    else:
        tag.name = name
    db.flush()
    for item in items:
        indexer.reindex(db, item)
    db.commit()
    return TagOut(id=tag.id, name=tag.name, count=len(tag.items))


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    tag = get_owned(db, Tag, tag_id, user)
    items = list(tag.items)
    db.delete(tag)
    db.flush()
    for item in items:
        db.refresh(item)
        indexer.reindex(db, item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
