"""Import a Loom JSON export into an existing account.

    cd PROJECT_08/backend
    python -m scripts.import_data --email you@example.com loom-export.json [--dry-run]

The file comes from **Settings -> Download JSON** (``loom-export-v1``). Only the archive is read:
collections and items. There are no passwords, session tokens or API keys in that format, and the
importer never asks for any.

An item is skipped when the same account already holds an item with the same title and the same
first 250 characters of body, so the same file can be imported twice without duplicating anything.
Missing collections are created and reused by name. Invalid or out-of-range values are clamped to
what the app accepts; a missing body or an unknown kind is given the model's defaults.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.models import KINDS, ORIGINS, Collection, Item, User
from app.services.search import split_tags

MAX_BODY = 100_000
FORMAT = "loom-export-v1"
PREFIX = 250


def _text(value: Any, limit: int) -> str:
    """Collapse whitespace for one-line fields and clamp to the column's limit."""
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _body(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    return text[:MAX_BODY]


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _moment(value: Any, fallback: datetime) -> datetime:
    """Parse an ISO timestamp (``Z`` or an offset) into an aware UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        return fallback
    raw = value.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _url(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 500:
        return ""
    if not text.startswith(("http://", "https://")):
        return ""
    return text


def _read(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise SystemExit("Not a Loom export: expected an 'items' list.")
    if payload.get("format") not in (None, FORMAT):
        raise SystemExit(f"Unsupported export format {payload.get('format')!r}; expected {FORMAT!r}.")
    return payload


def _collection(db, user: User, name: str, description: str) -> Collection | None:
    name = _text(name, 60)
    if not name:
        return None
    existing = db.scalar(
        select(Collection).where(
            Collection.user_id == user.id,
            func.lower(Collection.name) == name.lower(),
        )
    )
    if existing is not None:
        return existing
    collection = Collection(user_id=user.id, name=name, description=_text(description, 240))
    db.add(collection)
    db.flush()
    return collection


def _already_imported(db, user: User, title: str, body: str) -> bool:
    """True when the same title and opening text are already stored for this account."""
    head = body[:PREFIX]
    candidates = db.scalars(
        select(Item).where(Item.user_id == user.id, Item.title == title).limit(20)
    ).all()
    return any((item.body or "")[:PREFIX] == head for item in candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a Loom JSON export")
    parser.add_argument("file", type=Path)
    parser.add_argument("--email", required=True, help="account that receives the archive")
    parser.add_argument("--dry-run", action="store_true", help="validate and count without saving")
    args = parser.parse_args()

    payload = _read(args.file)
    settings = Settings()
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    now = datetime.now(timezone.utc)

    counts = {
        "items": 0,
        "collections": 0,
        "skipped": 0,
        "invalid": 0,
    }

    with Session() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            raise SystemExit(f"No account with email {args.email!r}.")

        descriptions: dict[str, str] = {}
        for entry in payload.get("collections") or []:
            if isinstance(entry, dict):
                name = _text(entry.get("name"), 60)
                if name:
                    descriptions[name.lower()] = _text(entry.get("description"), 240)

        existing_collections = {
            collection.name.lower()
            for collection in db.scalars(
                select(Collection).where(Collection.user_id == user.id)
            ).all()
        }

        for raw in payload["items"]:
            if not isinstance(raw, dict):
                counts["invalid"] += 1
                continue
            title = _text(raw.get("title"), 200)
            body = _body(raw.get("body"))
            if not title:
                counts["invalid"] += 1
                continue
            if _already_imported(db, user, title, body):
                counts["skipped"] += 1
                continue

            kind = raw.get("kind") if raw.get("kind") in KINDS else "note"
            origin = raw.get("origin") if raw.get("origin") in ORIGINS else "imported"
            tags = ", ".join(split_tags(",".join(str(tag) for tag in raw.get("tags") or [])))
            collection_name = _text(raw.get("collection"), 60)
            collection = _collection(
                db, user, collection_name, descriptions.get(collection_name.lower(), "")
            )
            if collection is not None and collection.name.lower() not in existing_collections:
                existing_collections.add(collection.name.lower())
                counts["collections"] += 1

            created = _moment(raw.get("created_at"), now)
            updated = _moment(raw.get("updated_at"), created)
            db.add(
                Item(
                    user_id=user.id,
                    collection_id=collection.id if collection else None,
                    title=title,
                    body=body,
                    kind=kind,
                    origin=origin,
                    source_url=_url(raw.get("source_url")),
                    author=_text(raw.get("author"), 120),
                    tags=tags,
                    starred=_flag(raw.get("starred")),
                    created_at=created,
                    updated_at=updated,
                )
            )
            counts["items"] += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    engine.dispose()
    prefix = "Would import" if args.dry_run else "Imported"
    print(prefix + ": " + ", ".join(f"{value} {name}" for name, value in counts.items() if value))
    if args.dry_run:
        print("Dry run: nothing was written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
