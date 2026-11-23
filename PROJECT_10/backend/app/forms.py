"""Small, shared input parsing helpers.

Every route parses form values through these functions so validation behaves the same everywhere.
"""

from __future__ import annotations

from datetime import date


def clean(value: str | None, max_len: int) -> str:
    return (value or "").strip()[:max_len]


def integer(value: str | None, default: int = 0, low: int = 0, high: int = 1_000_000) -> int:
    try:
        parsed = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def parse_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def choice(value: str | None, allowed: tuple[str, ...], default: str) -> str:
    text = (value or "").strip()
    return text if text in allowed else default


def boolean(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "on", "yes")


def code(value: str | None, fallback: str = "OPS-01") -> str:
    """An SOP code: uppercase letters, digits and dashes, 3-20 characters."""
    text = "".join(ch for ch in (value or "").upper() if ch.isalnum() or ch == "-")[:20]
    return text if len(text) >= 3 else fallback
