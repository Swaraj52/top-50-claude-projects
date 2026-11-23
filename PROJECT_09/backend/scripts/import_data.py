"""Import a Keystone JSON export into an existing account.

    cd PROJECT_09/backend
    python -m scripts.import_data --email you@example.com keystone-export.json [--dry-run]

The file comes from **Settings -> Download JSON export** (``keystone-export-v1``). It holds
ventures and their canvas notes, SWOT items, revenue streams, cost lines, milestones, KPIs and
KPI readings. It contains no passwords, session tokens or API keys, and the importer never asks
for any.

Idempotency is by venture name: a venture whose name already exists for that account is skipped
whole, so importing the same file twice duplicates nothing. Values outside what the app accepts
are clamped; unknown enum values fall back to the model defaults.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.models import (
    CADENCES,
    CANVAS_BLOCKS,
    CONFIDENCE_LEVELS,
    COST_KINDS,
    CURRENCIES,
    DIRECTIONS,
    HORIZONS,
    MILESTONE_HORIZONS,
    MILESTONE_STATUSES,
    QUADRANTS,
    REVENUE_MODELS,
    STAGES,
    CanvasEntry,
    CostLine,
    Kpi,
    KpiReading,
    Milestone,
    RevenueStream,
    SwotItem,
    User,
    Venture,
)

FORMAT = "keystone-export-v1"
MAX_LONG_TEXT = 2000


def _text(value: Any, limit: int) -> str:
    """Collapse whitespace for one-line fields and clamp to the column's limit."""
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _long_text(value: Any, limit: int = MAX_LONG_TEXT) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    return text[:limit]


def _choice(value: Any, allowed: tuple[str, ...], fallback: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else fallback


def _int(value: Any, fallback: int = 0, low: int = 0, high: int = 1_000_000_000) -> int:
    try:
        parsed = int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError, OverflowError):
        return fallback
    return max(low, min(high, parsed))


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError, OverflowError):
        return fallback
    if not math.isfinite(parsed):
        return fallback
    return parsed


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _day(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _moment(value: Any, fallback: datetime | None = None) -> datetime | None:
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


def _read(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("ventures"), list):
        raise SystemExit("Not a Keystone export: expected a 'ventures' list.")
    if payload.get("format") not in (None, FORMAT):
        raise SystemExit(f"Unsupported export format {payload.get('format')!r}; expected {FORMAT!r}.")
    return payload


def _venture_exists(db, user: User, name: str) -> bool:
    return (
        db.scalar(
            select(Venture.id).where(
                Venture.user_id == user.id, func.lower(Venture.name) == name.lower()
            )
        )
        is not None
    )


def _add_canvas(db, venture: Venture, rows: Any, counts: dict) -> None:
    for index, raw in enumerate(rows if isinstance(rows, list) else [], start=1):
        if not isinstance(raw, dict):
            counts["invalid"] += 1
            continue
        title = _text(raw.get("title"), 160)
        block = _choice(raw.get("block"), CANVAS_BLOCKS, "")
        if not title or not block:
            counts["invalid"] += 1
            continue
        db.add(
            CanvasEntry(
                venture_id=venture.id,
                block=block,
                title=title,
                detail=_text(raw.get("detail"), 600),
                sort_order=_int(raw.get("sort_order"), index, 0, 1_000_000),
            )
        )
        counts["canvas"] += 1


def _add_swot(db, venture: Venture, rows: Any, counts: dict) -> None:
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            counts["invalid"] += 1
            continue
        text = _text(raw.get("text"), 300)
        quadrant = _choice(raw.get("quadrant"), QUADRANTS, "")
        if not text or not quadrant:
            counts["invalid"] += 1
            continue
        db.add(
            SwotItem(
                venture_id=venture.id,
                quadrant=quadrant,
                text=text,
                impact=_int(raw.get("impact"), 3, 1, 5),
                evidence=_text(raw.get("evidence"), 300),
            )
        )
        counts["swot"] += 1


def _add_streams(db, venture: Venture, rows: Any, counts: dict) -> None:
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            counts["invalid"] += 1
            continue
        name = _text(raw.get("name"), 120)
        if not name:
            counts["invalid"] += 1
            continue
        db.add(
            RevenueStream(
                venture_id=venture.id,
                name=name,
                model=_choice(raw.get("model"), REVENUE_MODELS, "subscription"),
                price=_int(raw.get("price"), 0),
                unit=_text(raw.get("unit"), 60) or "per month",
                volume=_int(raw.get("volume"), 0),
                confidence=_choice(raw.get("confidence"), CONFIDENCE_LEVELS, "medium"),
                notes=_text(raw.get("notes"), 300),
            )
        )
        counts["streams"] += 1


def _add_costs(db, venture: Venture, rows: Any, counts: dict) -> None:
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            counts["invalid"] += 1
            continue
        name = _text(raw.get("name"), 120)
        if not name:
            counts["invalid"] += 1
            continue
        db.add(
            CostLine(
                venture_id=venture.id,
                name=name,
                amount=_int(raw.get("amount"), 0),
                kind=_choice(raw.get("kind"), COST_KINDS, "fixed"),
                notes=_text(raw.get("notes"), 300),
            )
        )
        counts["costs"] += 1


def _add_milestones(db, venture: Venture, rows: Any, counts: dict) -> None:
    for index, raw in enumerate(rows if isinstance(rows, list) else [], start=1):
        if not isinstance(raw, dict):
            counts["invalid"] += 1
            continue
        title = _text(raw.get("title"), 160)
        if not title:
            counts["invalid"] += 1
            continue
        status = _choice(raw.get("status"), MILESTONE_STATUSES, "planned")
        db.add(
            Milestone(
                venture_id=venture.id,
                title=title,
                success_criterion=_text(raw.get("success_criterion"), 300),
                owner=_text(raw.get("owner"), 80),
                due_date=_day(raw.get("due_date")),
                horizon=_choice(raw.get("horizon"), MILESTONE_HORIZONS, "now"),
                status=status,
                sort_order=_int(raw.get("sort_order"), index, 0, 1_000_000),
                completed_at=_moment(raw.get("completed_at")) if status == "done" else None,
            )
        )
        counts["milestones"] += 1


def _add_kpis(db, venture: Venture, rows: Any, counts: dict) -> None:
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            counts["invalid"] += 1
            continue
        name = _text(raw.get("name"), 120)
        if not name:
            counts["invalid"] += 1
            continue
        baseline = _float(raw.get("baseline"), 0.0)
        target = _float(raw.get("target"), 0.0)
        kpi = Kpi(
            venture_id=venture.id,
            name=name,
            unit=_text(raw.get("unit"), 40),
            direction=_choice(raw.get("direction"), DIRECTIONS, "up"),
            baseline=baseline,
            target=target,
            target_date=_day(raw.get("target_date")),
            cadence=_choice(raw.get("cadence"), CADENCES, "monthly"),
        )
        db.add(kpi)
        db.flush()
        counts["kpis"] += 1

        seen: set[date] = set()
        readings = raw.get("readings")
        for row in readings if isinstance(readings, list) else []:
            if not isinstance(row, dict):
                counts["invalid"] += 1
                continue
            day = _day(row.get("recorded_on"))
            if day is None or day in seen:
                counts["invalid"] += 1
                continue
            seen.add(day)
            db.add(
                KpiReading(
                    kpi_id=kpi.id,
                    value=_float(row.get("value"), 0.0),
                    recorded_on=day,
                    note=_text(row.get("note"), 200),
                )
            )
            counts["readings"] += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a Keystone JSON export")
    parser.add_argument("file", type=Path)
    parser.add_argument("--email", required=True, help="account that receives the portfolio")
    parser.add_argument("--dry-run", action="store_true", help="validate and count without saving")
    args = parser.parse_args()

    payload = _read(args.file)
    settings = Settings()
    engine = make_engine(settings.database_url)
    Session = make_sessionmaker(engine)
    now = datetime.now(timezone.utc)

    counts = {
        "ventures": 0,
        "canvas": 0,
        "swot": 0,
        "streams": 0,
        "costs": 0,
        "milestones": 0,
        "kpis": 0,
        "readings": 0,
        "skipped": 0,
        "invalid": 0,
    }

    try:
        with Session() as db:
            user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
            if user is None:
                raise SystemExit(f"No account with email {args.email!r}.")

            for raw in payload["ventures"]:
                if not isinstance(raw, dict):
                    counts["invalid"] += 1
                    continue
                name = _text(raw.get("name"), 120)
                if len(name) < 2:
                    counts["invalid"] += 1
                    continue
                if _venture_exists(db, user, name):
                    counts["skipped"] += 1
                    continue

                narrative_source = str(raw.get("narrative_source") or "local").strip().lower()
                venture = Venture(
                    user_id=user.id,
                    name=name,
                    one_liner=_text(raw.get("one_liner"), 240),
                    stage=_choice(raw.get("stage"), STAGES, "idea"),
                    horizon=_choice(raw.get("horizon"), HORIZONS, "90 days"),
                    currency=_choice(raw.get("currency"), CURRENCIES, "INR"),
                    market=_long_text(raw.get("market")),
                    segment=_text(raw.get("segment"), 240),
                    alternatives=_long_text(raw.get("alternatives")),
                    differentiation=_long_text(raw.get("differentiation")),
                    narrative=_long_text(raw.get("narrative"), 8000),
                    narrative_source=narrative_source if narrative_source in ("local", "claude") else "local",
                    narrative_at=_moment(raw.get("narrative_at")),
                    archived=_flag(raw.get("archived")),
                )
                db.add(venture)
                db.flush()
                counts["ventures"] += 1

                _add_canvas(db, venture, raw.get("canvas"), counts)
                _add_swot(db, venture, raw.get("swot"), counts)
                _add_streams(db, venture, raw.get("streams"), counts)
                _add_costs(db, venture, raw.get("costs"), counts)
                _add_milestones(db, venture, raw.get("milestones"), counts)
                _add_kpis(db, venture, raw.get("kpis"), counts)

            if args.dry_run:
                db.rollback()
            else:
                db.commit()
    finally:
        engine.dispose()

    prefix = "Would import" if args.dry_run else "Imported"
    print(prefix + ": " + ", ".join(f"{value} {name}" for name, value in counts.items() if value))
    if args.dry_run:
        print("Dry run: nothing was written.")
    if counts["invalid"]:
        print(f"Skipped {counts['invalid']} invalid entr{'y' if counts['invalid'] == 1 else 'ies'} (not valid for this schema).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
