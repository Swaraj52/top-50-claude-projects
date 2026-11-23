"""The business canvas: nine blocks, completeness, and the gaps worth filling next."""

from __future__ import annotations

from ..models import CANVAS_BLOCKS, CANVAS_LABELS, CANVAS_PROMPTS, CanvasEntry

MIN_TITLE = 3


def grouped(entries: list[CanvasEntry]) -> dict[str, list[CanvasEntry]]:
    """Entries by block, in the canonical block order, each block sorted by sort_order then id."""
    by_block: dict[str, list[CanvasEntry]] = {block: [] for block in CANVAS_BLOCKS}
    for entry in entries:
        by_block.setdefault(entry.block, []).append(entry)
    for block in by_block:
        by_block[block].sort(key=lambda e: (e.sort_order, e.id))
    return by_block


def completeness(entries: list[CanvasEntry]) -> dict:
    """How much of the canvas is filled. A block counts when it has at least one entry."""
    filled = {block for block in CANVAS_BLOCKS if any(e.block == block for e in entries)}
    count = len(filled)
    percent = round(count / len(CANVAS_BLOCKS) * 100)
    missing = [block for block in CANVAS_BLOCKS if block not in filled]
    return {
        "filled": count,
        "total": len(CANVAS_BLOCKS),
        "percent": percent,
        "missing": missing,
        "missing_labels": [CANVAS_LABELS[block] for block in missing],
    }


def gaps(entries: list[CanvasEntry], limit: int = 3) -> list[dict]:
    """The first empty blocks, with a prompt that says what belongs there."""
    filled = {e.block for e in entries}
    return [
        {"block": block, "label": CANVAS_LABELS[block], "prompt": CANVAS_PROMPTS[block]}
        for block in CANVAS_BLOCKS
        if block not in filled
    ][:limit]


def ready(entries: list[CanvasEntry]) -> bool:
    """A canvas is usable for a brief once every block has at least one entry."""
    return len({e.block for e in entries}) == len(CANVAS_BLOCKS)
