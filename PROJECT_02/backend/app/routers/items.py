from __future__ import annotations

import logging
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

import anthropic
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..config import Settings
from ..deps import current_user, get_db, get_owned, get_settings
from ..models import Item, Question, Tag, User, item_tags
from ..schemas import ItemCard, ItemDetail, ItemPage, ItemPatch, SaveResult, Stats, TextIn, UrlIn, _clean_tags
from ..services import extract, fetcher, indexer, summarize, youtube
from ..services.ai import AIError
from .common import ai_client, drop_orphan_tags, rate_limit, set_tags

router = APIRouter(prefix="/items", tags=["items"])
log = logging.getLogger(__name__)

UPLOAD_TYPES = {".txt", ".md", ".markdown", ".html", ".htm", ".eml", ".pdf"}
MAX_UPLOAD = 10 * 1024 * 1024


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def _existing(db: DbSession, user: User, url: str) -> Item | None:
    return db.scalar(select(Item).where(Item.user_id == user.id, Item.url == url))


def _store(db: DbSession, user: User, data: extract.Extracted, *, url: str | None, tags: list[str],
           status_: str, thumbnail: str | None = None, has_transcript: bool = False) -> Item:
    item = Item(
        user_id=user.id,
        kind=data.kind,
        status=status_,
        title=data.title[:500],
        url=url,
        source_name=data.source_name,
        author=data.author,
        published=data.published,
        description=data.description,
        content=data.content,
        thumbnail_url=thumbnail,
        has_transcript=has_transcript,
    )
    db.add(item)
    set_tags(db, user, item, tags)
    db.flush()
    indexer.reindex(db, item)
    db.commit()
    return item


@router.post("/url", response_model=SaveResult, status_code=status.HTTP_201_CREATED)
def save_url(
    body: UrlIn,
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    vid = youtube.video_id(body.url)
    url = youtube.canonical_url(vid) if vid else normalize_url(body.url)
    if (dup := _existing(db, user, url)) is not None:
        response.status_code = status.HTTP_200_OK
        return SaveResult(item=ItemDetail.of(dup), warnings=["You already saved this link."])

    if vid:
        try:
            info = youtube.fetch_info(vid, transport=request.app.state.http_transport)
        except LookupError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        transcript = youtube.fetch_transcript(vid)
        data = extract.Extracted(
            kind="video",
            title=info.title,
            content=transcript or "",
            source_name="YouTube",
            author=info.channel,
            description=f"Video by {info.channel}" if info.channel else "",
        )
        if not transcript:
            data.warnings.append(
                "No transcript was available, so only the title is searchable. "
                "You can paste the transcript into the item later."
            )
        item = _store(db, user, data, url=url, tags=body.tags, status_=body.status,
                      thumbnail=info.thumbnail_url, has_transcript=bool(transcript))
        return SaveResult(item=ItemDetail.of(item), warnings=data.warnings)

    try:
        page = fetcher.fetch(
            url,
            timeout=settings.fetch_timeout,
            max_bytes=settings.fetch_max_bytes,
            allow_private=settings.allow_private_fetch,
            transport=request.app.state.http_transport,
        )
        if page.content_type == "application/pdf":
            data = extract.from_pdf(page.body, urlsplit(url).path.rsplit("/", 1)[-1])
        elif page.content_type in ("text/plain", "text/markdown"):
            data = extract.from_text(page.text, urlsplit(url).path.rsplit("/", 1)[-1])
            data.kind = "article"
        else:
            data = extract.from_html(page.text, page.url)
    except (fetcher.FetchError, extract.ExtractError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Couldn't save that link: {exc}") from exc
    item = _store(db, user, data, url=url, tags=body.tags, status_=body.status)
    return SaveResult(item=ItemDetail.of(item), warnings=data.warnings)


@router.post("/text", response_model=SaveResult, status_code=status.HTTP_201_CREATED)
def save_text(body: TextIn, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    data = extract.from_text(body.content, title=body.title.strip())
    data.kind = body.kind
    url = normalize_url(body.url) if body.url else None
    if url and (dup := _existing(db, user, url)) is not None:
        return SaveResult(item=ItemDetail.of(dup), warnings=["You already saved this link."])
    item = _store(db, user, data, url=url, tags=body.tags, status_=body.status)
    return SaveResult(item=ItemDetail.of(item))


@router.post("/upload", response_model=SaveResult, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    tags: str = Form(""),
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    name = file.filename or "upload"
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if ext not in UPLOAD_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Supported files: .txt, .md, .html, .eml, .pdf")
    raw = await file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Files must be 10 MB or smaller")
    try:
        if ext == ".pdf":
            data = extract.from_pdf(raw, name)
        elif ext == ".eml":
            data = extract.from_eml(raw)
        elif ext in (".html", ".htm"):
            data = extract.from_html(raw.decode("utf-8", errors="replace"))
            if data.title == "Untitled page":
                data.title = name.rsplit(".", 1)[0]
        else:
            data = extract.from_text(raw.decode("utf-8", errors="replace"), filename=name)
    except extract.ExtractError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    try:
        tag_names = _clean_tags([t for t in tags.split(",") if t.strip()]) or []
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    item = _store(db, user, data, url=None, tags=tag_names, status_="inbox")
    return SaveResult(item=ItemDetail.of(item), warnings=data.warnings)


@router.get("", response_model=ItemPage)
def list_items(
    status_filter: Literal["inbox", "library", "archived", "all"] = Query("library", alias="status"),
    kind: Literal["article", "video", "newsletter", "note", "pdf"] | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    sort: Literal["newest", "oldest", "title"] = "newest",
    limit: int = 60,
    offset: int = 0,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
):
    q = select(Item).where(Item.user_id == user.id)
    if status_filter != "all":
        q = q.where(Item.status == status_filter)
    if kind:
        q = q.where(Item.kind == kind)
    if favorite is not None:
        q = q.where(Item.favorite == favorite)
    if tag:
        q = q.where(Item.id.in_(select(item_tags.c.item_id).join(Tag, Tag.id == item_tags.c.tag_id).where(Tag.user_id == user.id, Tag.name == tag)))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    order = {"newest": Item.created_at.desc(), "oldest": Item.created_at.asc(), "title": func.lower(Item.title)}[sort]
    rows = db.scalars(q.options(selectinload(Item.tags)).order_by(order, Item.id.desc()).limit(min(max(limit, 1), 200)).offset(max(offset, 0)))
    return ItemPage(items=[ItemCard.of(i) for i in rows], total=total or 0)


# Declared before /{item_id} so "stats" isn't parsed as an id.
@router.get("/stats", response_model=Stats)
def stats(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    counts = dict(db.execute(select(Item.status, func.count()).where(Item.user_id == user.id).group_by(Item.status)).all())
    kinds = dict(db.execute(select(Item.kind, func.count()).where(Item.user_id == user.id, Item.status != "archived").group_by(Item.kind)).all())
    return Stats(
        inbox=counts.get("inbox", 0),
        library=counts.get("library", 0),
        archived=counts.get("archived", 0),
        favorites=db.scalar(select(func.count()).select_from(Item).where(Item.user_id == user.id, Item.favorite)) or 0,
        by_kind=kinds,
        tags=db.scalar(select(func.count()).select_from(Tag).where(Tag.user_id == user.id)) or 0,
        questions=db.scalar(select(func.count()).select_from(Question).where(Question.user_id == user.id)) or 0,
    )


@router.get("/{item_id}", response_model=ItemDetail)
def get_item(item_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    return ItemDetail.of(get_owned(db, Item, item_id, user))


@router.patch("/{item_id}", response_model=ItemDetail)
def update_item(item_id: int, body: ItemPatch, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    item = get_owned(db, Item, item_id, user)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    reindex = False
    if "title" in changes:
        item.title = changes["title"].strip() or item.title
        reindex = True
    if "status" in changes:
        item.status = changes["status"]
    if "favorite" in changes:
        item.favorite = changes["favorite"]
    if "tags" in changes:
        set_tags(db, user, item, changes["tags"])
        reindex = True
    if "content" in changes:
        item.content = changes["content"].replace("\r\n", "\n").strip()
        if item.kind == "video":
            item.has_transcript = bool(item.content)
        item.summary = None  # the old summary no longer matches the text
        reindex = True
    if reindex:
        indexer.reindex(db, item)
    db.flush()
    drop_orphan_tags(db, user)
    db.commit()
    return ItemDetail.of(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    item = get_owned(db, Item, item_id, user)
    indexer.unindex(db, item)
    db.delete(item)
    db.flush()
    drop_orphan_tags(db, user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{item_id}/summarize", response_model=ItemDetail)
def summarize_item(
    item_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: anthropic.Anthropic | None = Depends(ai_client),
):
    item = get_owned(db, Item, item_id, user)
    rate_limit(request, "summary_limiter", str(user.id), "Too many summaries at once. Wait a moment and try again.")
    if client is not None:
        try:
            item.summary = summarize.summarize_ai(item, client, settings.anthropic_model)
        except AIError as exc:
            log.warning("AI summary failed for item %s: %s", item.id, exc)
            item.summary = summarize.summarize_extractive(
                item, note=f"AI summary unavailable: {exc}. Showing an extractive summary instead."
            )
    else:
        item.summary = summarize.summarize_extractive(item)
    db.commit()
    return ItemDetail.of(item)
