from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .services.text import normalize_tag, reading_minutes

Kind = Literal["article", "video", "newsletter", "note", "pdf"]
Status = Literal["inbox", "library", "archived"]
MAX_TAGS = 20


def _clean_tags(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    out: list[str] = []
    for v in values:
        name = normalize_tag(v)
        if name and name not in out:
            out.append(name)
    if len(out) > MAX_TAGS:
        raise ValueError(f"at most {MAX_TAGS} tags per item")
    return out


# --- auth -------------------------------------------------------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name is required")
        return v.strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str


# --- items ------------------------------------------------------------------------------


class UrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    status: Literal["inbox", "library"] = "inbox"

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if not v.lower().startswith(("http://", "https://")):
            v = "https://" + v
        return v

    _tags = field_validator("tags")(lambda cls, v: _clean_tags(v))


class TextIn(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(min_length=1, max_length=2_000_000)
    kind: Literal["newsletter", "note"] = "note"
    url: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    status: Literal["inbox", "library"] = "inbox"

    _tags = field_validator("tags")(lambda cls, v: _clean_tags(v))


class ItemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    status: Status | None = None
    favorite: bool | None = None
    tags: list[str] | None = None
    content: str | None = Field(default=None, max_length=2_000_000)

    _tags = field_validator("tags")(lambda cls, v: _clean_tags(v))


class Summary(BaseModel):
    source: Literal["ai", "extractive"]
    model: str | None = None
    tldr: str
    key_points: list[str]
    suggested_tags: list[str]
    truncated: bool = False
    note: str | None = None
    created_at: str


class ItemCard(BaseModel):
    id: int
    kind: Kind
    status: Status
    favorite: bool
    title: str
    url: str | None
    source_name: str
    author: str
    word_count: int
    reading_minutes: int
    has_transcript: bool
    thumbnail_url: str | None
    tags: list[str]
    tldr: str | None
    created_at: datetime

    @classmethod
    def of(cls, item) -> ItemCard:
        return cls(
            id=item.id,
            kind=item.kind,
            status=item.status,
            favorite=item.favorite,
            title=item.title,
            url=item.url,
            source_name=item.source_name,
            author=item.author,
            word_count=item.word_count,
            reading_minutes=reading_minutes(item.word_count),
            has_transcript=item.has_transcript,
            thumbnail_url=item.thumbnail_url,
            tags=sorted(t.name for t in item.tags),
            tldr=(item.summary or {}).get("tldr"),
            created_at=item.created_at,
        )


class ItemDetail(ItemCard):
    description: str
    content: str
    published: str
    summary: Summary | None
    updated_at: datetime

    @classmethod
    def of(cls, item) -> ItemDetail:  # type: ignore[override]
        card = ItemCard.of(item).model_dump()
        return cls(
            **card,
            description=item.description,
            content=item.content,
            published=item.published,
            summary=item.summary,
            updated_at=item.updated_at,
        )


class SaveResult(BaseModel):
    item: ItemDetail
    warnings: list[str] = Field(default_factory=list)


class ItemPage(BaseModel):
    items: list[ItemCard]
    total: int


class Stats(BaseModel):
    inbox: int
    library: int
    archived: int
    favorites: int
    by_kind: dict[str, int]
    tags: int
    questions: int


# --- tags, search, ask --------------------------------------------------------------------


class TagOut(BaseModel):
    id: int
    name: str
    count: int


class TagRename(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class SearchHit(BaseModel):
    item: ItemCard
    snippet: str


class SearchOut(BaseModel):
    query: str
    hits: list[SearchHit]
    mode: Literal["all", "any"]


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    tag: str | None = Field(default=None, max_length=40)


class Citation(BaseModel):
    n: int
    item_id: int
    title: str
    url: str | None
    excerpt: str


class AskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    question: str
    answer: str
    source: Literal["ai", "passages"]
    model: str | None
    note: str | None
    confidence: str | None
    citations: list[Citation]
    created_at: datetime


class MetaOut(BaseModel):
    version: str
    ai_enabled: bool
    ai_model: str | None
