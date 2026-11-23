"""Small, shared input parsing and formatting helpers.

Every route parses form values through these functions so validation behaves the same
everywhere, and templates format numbers through the same filters the tests check.
"""

from __future__ import annotations

from datetime import date

from .models import CURRENCY_SYMBOLS


def clean(value: str | None, max_len: int) -> str:
    return (value or "").strip()[:max_len]


def integer(value: str | None, default: int = 0, low: int = 0, high: int = 1_000_000_000) -> int:
    try:
        parsed = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def real(value: str | None, default: float = 0.0) -> float:
    try:
        parsed = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default
    if parsed != parsed or parsed in (float("inf"), float("-inf")):  # NaN and infinities
        return default
    return parsed


def real_or_none(value: str | None) -> float | None:
    """Parse a decimal that must be present, returning None when it is not a number."""
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return None
    return parsed


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


def money(amount: int | float | None, currency: str = "INR") -> str:
    """Full amount with the currency symbol and thousands separators: ₹240,000."""
    if amount is None:
        return "—"
    symbol = CURRENCY_SYMBOLS.get(currency, "")
    return f"{symbol}{round(amount):,}"


def compact_money(amount: int | float | None, currency: str = "INR") -> str:
    """A short amount for cards: ₹9.6L, ₹1.2Cr, $12k, $1.4M."""
    if amount is None:
        return "—"
    value = float(amount)
    symbol = CURRENCY_SYMBOLS.get(currency, "")
    if currency == "INR":
        if abs(value) >= 10_000_000:
            return f"{symbol}{value / 10_000_000:.1f}Cr".replace(".0Cr", "Cr")
        if abs(value) >= 100_000:
            return f"{symbol}{value / 100_000:.1f}L".replace(".0L", "L")
        if abs(value) >= 1_000:
            return f"{symbol}{value / 1_000:.1f}k".replace(".0k", "k")
        return f"{symbol}{round(value):,}"
    if abs(value) >= 1_000_000:
        return f"{symbol}{value / 1_000_000:.1f}M".replace(".0M", "M")
    if abs(value) >= 1_000:
        return f"{symbol}{value / 1_000:.1f}k".replace(".0k", "k")
    return f"{symbol}{round(value):,}"


def number(value: float | int | None, unit: str = "") -> str:
    """A KPI value with at most two decimals and an optional unit."""
    if value is None:
        return "—"
    if abs(value - round(value)) < 1e-9:
        text = f"{round(value):,}"
    else:
        text = f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{text} {unit}".strip()
