from __future__ import annotations

import html
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..db import utcnow
from ..models import KINDS, Collection, Item
from ..services import ai
from ..services.ask import compose
from ..services.clusters import build_clusters
from ..services.search import (
    parse_query,
    related,
    search,
    snippet,
    split_tags,
    url_host,
)
from ..web import Ctx, csrf, ctx, get_db, render, safe_next, see_other

router = APIRouter()

MAX_BODY = 100_000
MAX_UPLOAD = 512 * 1024
UPLOAD_SUFFIXES = (".md", ".markdown", ".txt", ".text", ".html", ".htm")
TAG_RE = re.compile(r"<[^>]+>")
BLOCK_RE = re.compile(r"</?(?:p|div|br|li|tr|h[1-6]|section|article|header|footer|blockquote)\b[^>]*>", re.I)


def _clean(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:limit]


def _items(db: DbSession, c: Ctx) -> list[Item]:
    return list(
        db.scalars(
            select(Item)
            .where(Item.user_id == c.user.id)
            .options(selectinload(Item.collection))
            .order_by(Item.updated_at.desc())
        ).all()
    )


def _item_or_404(db: DbSession, c: Ctx, item_id: int) -> Item:
    item = db.scalar(
        select(Item)
        .where(Item.id == item_id, Item.user_id == c.user.id)
        .options(selectinload(Item.collection))
    )
    if item is None:
        raise HTTPException(404, "That item doesn't exist.")
    return item


def _collections(db: DbSession, c: Ctx) -> list[Collection]:
    return list(db.scalars(select(Collection).where(Collection.user_id == c.user.id).order_by(Collection.name)).all())


def _collection_for(db: DbSession, c: Ctx, value: str) -> Collection | None:
    if not value or not value.isdigit():
        return None
    return db.scalar(select(Collection).where(Collection.id == int(value), Collection.user_id == c.user.id))


def _stats(items: list[Item]) -> dict:
    kinds: dict[str, int] = {}
    tags: dict[str, int] = {}
    words = 0
    for item in items:
        kinds[item.kind] = kinds.get(item.kind, 0) + 1
        words += len((item.body or "").split())
        for tag in split_tags(item.tags):
            key = tag.lower()
            tags[key] = tags.get(key, 0) + 1
    return {
        "total": len(items),
        "kinds": kinds,
        "tags": tags,
        "starred": sum(1 for item in items if item.starred),
        "words": words,
        "links": sum(1 for item in items if item.source_url),
    }


def _valid_url(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) > 500:
        raise ValueError("Source links must be 500 characters or fewer.")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("A source link must start with http:// or https:// and include a host.")
    return text


def _apply_form(item: Item, values: dict, db: DbSession, c: Ctx) -> None:
    title = _clean(values.get("title", ""), 200)
    if not title:
        raise ValueError("Give the item a title.")
    body = (values.get("body") or "").replace("\r\n", "\n").strip()
    if len(body) > MAX_BODY:
        raise ValueError(f"The body is too long ({len(body):,} characters; the limit is {MAX_BODY:,}).")
    kind = values.get("kind", "note")
    if kind not in KINDS:
        raise ValueError("Choose one of the four kinds.")
    item.title = title
    item.body = body
    item.kind = kind
    item.tags = ", ".join(split_tags(values.get("tags", "")))
    item.author = _clean(values.get("author", ""), 120)
    item.source_url = _valid_url(values.get("source_url", ""))
    item.collection = _collection_for(db, c, str(values.get("collection_id", "")))
    item.starred = bool(values.get("starred"))
    item.updated_at = utcnow()


def _download_name(filename: str) -> str:
    stem = re.split(r"[\\/]", filename or "Untitled")[-1]
    stem = re.sub(r"\.(md|markdown|txt|text|html|htm)$", "", stem, flags=re.I)
    return _clean(stem.replace("_", " ").replace("-", " "), 200) or "Untitled upload"


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    raw = BLOCK_RE.sub("\n", raw)
    raw = TAG_RE.sub(" ", raw)
    text = html.unescape(raw)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)[:MAX_BODY]


@router.get("/")
def dashboard(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    items = _items(db, c)
    stats = _stats(items)
    clusters = build_clusters(items, limit=4)
    collections = []
    for collection in _collections(db, c):
        collections.append((collection, sum(1 for item in items if item.collection_id == collection.id)))
    top_tags = sorted(stats["tags"].items(), key=lambda pair: (-pair[1], pair[0].lower()))[:10]
    return render(
        request,
        "dashboard.html",
        c,
        stats=stats,
        recent=items[:5],
        clusters=clusters,
        collections=collections,
        top_tags=top_tags,
        empty=not items,
    )


@router.get("/library")
def library(
    request: Request,
    kind: str = "",
    tag: str = "",
    collection: str = "",
    starred: str = "",
    sort: str = "recent",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    items = _items(db, c)
    selected_collection = _collection_for(db, c, collection)
    if kind and kind not in KINDS:
        kind = ""
    if collection and selected_collection is None:
        collection = ""
    if tag:
        tag = tag.lower()
    if starred not in ("", "1", "yes"):
        starred = ""
    filtered = [
        item
        for item in items
        if (not kind or item.kind == kind)
        and (not tag or tag in {value.lower() for value in split_tags(item.tags)})
        and (not collection or (item.collection_id is not None and item.collection_id == selected_collection.id))
        and (not starred or item.starred)
    ]
    if sort == "title":
        filtered.sort(key=lambda item: item.title.lower())
    elif sort == "oldest":
        filtered.sort(key=lambda item: item.updated_at)
    else:
        sort = "recent"
    return render(
        request,
        "library.html",
        c,
        items=filtered,
        total=len(items),
        stats=_stats(items),
        kinds=list(KINDS),
        kind=kind,
        tag=tag,
        collection=collection,
        selected_collection=selected_collection,
        starred=starred,
        sort=sort,
        collections=_collections(db, c),
        clear_url="/library",
    )


@router.get("/search")
def search_page(
    request: Request,
    q: str = "",
    kind: str = "",
    tag: str = "",
    collection: str = "",
    starred: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    raw = q if q else ""
    if not raw and not any((kind, tag, collection, starred)):
        return render(
            request,
            "search.html",
            c,
            q="",
            query=parse_query(""),
            hits=[],
            total=0,
            show_help=True,
            kinds=list(KINDS),
        )
    if kind or tag or collection or starred:
        extras = []
        if kind:
            extras.append(f"kind:{kind}")
        if tag:
            extras.append(f"tag:{tag}")
        if collection:
            extras.append(f"in:{collection}")
        if starred:
            extras.append("is:starred")
        raw = (raw + " " + " ".join(extras)).strip()
    query = parse_query(raw)
    items = _items(db, c)
    hits = search(items, query)
    return render(
        request,
        "search.html",
        c,
        q=q,
        query=query,
        hits=hits,
        total=len(items),
        show_help=query.active,
        kinds=list(KINDS),
    )


@router.get("/ask")
def ask_page(request: Request, c: Ctx = Depends(ctx)):
    return render(request, "ask.html", c, q="", query=parse_query(""), answer=None, hits=[])


@router.post("/ask")
def ask(
    request: Request,
    q: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    question = _clean(q, 500)
    query = parse_query(question)
    if not query.active:
        return render(
            request,
            "ask.html",
            c,
            q=q,
            query=query,
            answer=None,
            hits=[],
            error="Ask a question with at least one meaningful word.",
        )
    hits = search(_items(db, c), query, limit=8)
    answer = compose(question, query, hits)
    note = answer.note
    settings = request.app.state.settings
    if settings.ai_enabled and answer.citations:
        key = str(c.user.id)
        limiter = request.app.state.ai_limiter
        if limiter.blocked(key):
            note = "Claude rate limit reached; the local extractive answer is shown."
        else:
            limiter.hit(key)
            answer, note = ai.upgrade(settings, question, answer, hits)
    return render(
        request,
        "ask.html",
        c,
        q=q,
        query=query,
        answer=answer,
        hits=hits[:5],
        ai_note=note,
        used_claude=answer.source == "claude",
    )


@router.get("/clusters")
def clusters_page(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    items = _items(db, c)
    clusters = build_clusters(items)
    covered = {item.id for cluster in clusters for item in cluster.items}
    return render(
        request,
        "clusters.html",
        c,
        clusters=clusters,
        total=len(items),
        uncovered=len(items) - len(covered),
    )


@router.get("/clusters/{slug}")
def cluster_detail(slug: str, request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    items = _items(db, c)
    clusters = build_clusters(items)
    cluster = next((entry for entry in clusters if entry.slug == slug), None)
    if cluster is None:
        raise HTTPException(404, "That cluster isn't in this library right now.")
    return render(request, "cluster_detail.html", c, cluster=cluster, total=len(items))


@router.get("/collections")
def collections_page(
    request: Request,
    error: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    items = _items(db, c)
    rows = []
    for collection in _collections(db, c):
        members = [item for item in items if item.collection_id == collection.id]
        rows.append((collection, members, sum(1 for item in members if item.source_url)))
    loose = [item for item in items if item.collection_id is None]
    return render(request, "collections.html", c, rows=rows, loose=loose, error=error)


@router.post("/collections")
def create_collection(
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    cleaned = _clean(name, 60)
    if not cleaned:
        return see_other("/collections?error=name")
    exists = db.scalar(
        select(Collection).where(Collection.user_id == c.user.id, func.lower(Collection.name) == cleaned.lower())
    )
    if exists:
        return see_other("/collections?error=duplicate")
    db.add(Collection(user_id=c.user.id, name=cleaned, description=_clean(description, 240)))
    db.commit()
    return see_other("/collections")


@router.post("/collections/{collection_id}")
def rename_collection(
    collection_id: int,
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    collection = _collection_for(db, c, str(collection_id))
    if collection is None:
        raise HTTPException(404, "That collection doesn't exist.")
    cleaned = _clean(name, 60)
    if not cleaned:
        return see_other("/collections?error=name")
    clash = db.scalar(
        select(Collection).where(
            Collection.user_id == c.user.id,
            func.lower(Collection.name) == cleaned.lower(),
            Collection.id != collection.id,
        )
    )
    if clash:
        return see_other("/collections?error=duplicate")
    collection.name = cleaned
    collection.description = _clean(description, 240)
    db.commit()
    return see_other("/collections")


@router.post("/collections/{collection_id}/delete")
def delete_collection(
    collection_id: int,
    request: Request,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    collection = _collection_for(db, c, str(collection_id))
    if collection is None:
        raise HTTPException(404, "That collection doesn't exist.")
    for item in db.scalars(select(Item).where(Item.collection_id == collection.id)).all():
        item.collection_id = None
    db.delete(collection)
    db.commit()
    return see_other("/collections")


@router.get("/tags")
def tags_page(request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    items = _items(db, c)
    counts: dict[str, int] = {}
    for item in items:
        for tag in split_tags(item.tags):
            key = tag.lower()
            counts[key] = counts.get(key, 0) + 1
    rows = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].lower()))
    return render(request, "tags.html", c, rows=rows, total=len(items))


@router.get("/items/new")
def new_item(
    request: Request,
    kind: str = "",
    upload: str = "",
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    upload_errors = {
        "missing": "Choose a file before uploading.",
        "type": "That file type is not supported. Use Markdown, plain text or HTML.",
        "large": "That file is larger than 512 KB.",
    }
    return render(
        request,
        "item_form.html",
        c,
        item=None,
        values={"kind": kind if kind in KINDS else "note"},
        collections=_collections(db, c),
        error=None,
        upload_error=upload_errors.get(upload),
        kind=kind if kind in KINDS else "",
    )


@router.post("/items/new")
async def create_item(
    request: Request,
    title: str = Form(""),
    body: str = Form(""),
    kind: str = Form("note"),
    tags: str = Form(""),
    author: str = Form(""),
    source_url: str = Form(""),
    collection_id: str = Form(""),
    starred: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    values = {
        "title": title,
        "body": body,
        "kind": kind,
        "tags": tags,
        "author": author,
        "source_url": source_url,
        "collection_id": collection_id,
        "starred": starred,
    }
    item = Item(user_id=c.user.id, origin="written")
    try:
        _apply_form(item, values, db, c)
    except ValueError as exc:
        return render(
            request,
            "item_form.html",
            c,
            item=None,
            values=values,
            collections=_collections(db, c),
            error=str(exc),
            upload_error=None,
            http_status=422,
        )
    db.add(item)
    db.commit()
    return see_other(f"/items/{item.id}")


@router.get("/items/{item_id}")
def item_detail(item_id: int, request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    item = _item_or_404(db, c, item_id)
    items = _items(db, c)
    return render(
        request,
        "item_detail.html",
        c,
        item=item,
        related=related(items, item),
        host=url_host(item.source_url),
        body_html=snippet(item.body, [], 100_000),
        total=len(items),
    )


@router.get("/items/{item_id}/edit")
def edit_item(item_id: int, request: Request, c: Ctx = Depends(ctx), db: DbSession = Depends(get_db)):
    item = _item_or_404(db, c, item_id)
    return render(
        request,
        "item_form.html",
        c,
        item=item,
        values={},
        collections=_collections(db, c),
        error=None,
        upload_error=None,
    )


@router.post("/items/{item_id}/edit")
def update_item(
    item_id: int,
    request: Request,
    title: str = Form(""),
    body: str = Form(""),
    kind: str = Form("note"),
    tags: str = Form(""),
    author: str = Form(""),
    source_url: str = Form(""),
    collection_id: str = Form(""),
    starred: str = Form(""),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    item = _item_or_404(db, c, item_id)
    values = {
        "title": title,
        "body": body,
        "kind": kind,
        "tags": tags,
        "author": author,
        "source_url": source_url,
        "collection_id": collection_id,
        "starred": starred,
    }
    try:
        _apply_form(item, values, db, c)
    except ValueError as exc:
        return render(
            request,
            "item_form.html",
            c,
            item=item,
            values=values,
            collections=_collections(db, c),
            error=str(exc),
            upload_error=None,
            http_status=422,
        )
    db.commit()
    return see_other(f"/items/{item.id}")


@router.post("/items/{item_id}/star")
def star_item(
    item_id: int,
    request: Request,
    next: str = Form("/library"),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    item = _item_or_404(db, c, item_id)
    item.starred = not item.starred
    item.updated_at = utcnow()
    db.commit()
    return see_other(safe_next(next, f"/items/{item.id}"))


@router.post("/items/{item_id}/delete")
def delete_item(
    item_id: int,
    request: Request,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    item = _item_or_404(db, c, item_id)
    db.delete(item)
    db.commit()
    return see_other("/library")


@router.post("/items/upload")
async def upload_item(
    request: Request,
    file: UploadFile | None = File(None),
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    if file is None or not file.filename:
        return see_other("/items/new?upload=missing")
    filename = file.filename
    if not filename.lower().endswith(UPLOAD_SUFFIXES):
        return see_other("/items/new?upload=type")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        return see_other("/items/new?upload=large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if filename.lower().endswith((".html", ".htm")):
        text = _html_to_text(text)
    item = Item(
        user_id=c.user.id,
        title=_download_name(filename),
        body=text[:MAX_BODY],
        kind="article" if filename.lower().endswith((".html", ".htm")) else "note",
        origin="uploaded",
    )
    db.add(item)
    db.commit()
    return see_other(f"/items/{item.id}/edit")
