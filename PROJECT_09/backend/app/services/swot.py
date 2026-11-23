"""SWOT: counts by quadrant, an impact-weighted balance, and the few items that matter most."""

from __future__ import annotations

from ..models import QUADRANTS, QUADRANT_LABELS, SwotItem

POSITIVE = ("strength", "opportunity")
NEGATIVE = ("weakness", "threat")


def grouped(items: list[SwotItem]) -> dict[str, list[SwotItem]]:
    out: dict[str, list[SwotItem]] = {quadrant: [] for quadrant in QUADRANTS}
    for item in items:
        out.setdefault(item.quadrant, []).append(item)
    for quadrant in out:
        out[quadrant].sort(key=lambda i: (-i.impact, i.id))
    return out


def summary(items: list[SwotItem]) -> dict:
    counts = {quadrant: 0 for quadrant in QUADRANTS}
    impact = {quadrant: 0 for quadrant in QUADRANTS}
    for item in items:
        counts[item.quadrant] = counts.get(item.quadrant, 0) + 1
        impact[item.quadrant] = impact.get(item.quadrant, 0) + item.impact
    positive = sum(impact[q] for q in POSITIVE)
    negative = sum(impact[q] for q in NEGATIVE)
    balance = positive - negative
    if not items:
        tone, tone_label = "empty", "Not started"
    elif balance > 3:
        tone, tone_label = "strong", "Leaning strong"
    elif balance < -3:
        tone, tone_label = "exposed", "Leaning exposed"
    else:
        tone, tone_label = "even", "Balanced"
    by_quadrant = grouped(items)
    risks = sorted(
        [i for i in items if i.quadrant in NEGATIVE], key=lambda i: (-i.impact, i.id)
    )[:3]
    return {
        "total": len(items),
        "counts": counts,
        "impact": impact,
        "positive": positive,
        "negative": negative,
        "balance": balance,
        "tone": tone,
        "tone_label": tone_label,
        "risks": risks,
        "grouped": by_quadrant,
        "quadrant_labels": QUADRANT_LABELS,
    }
