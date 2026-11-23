"""KPI plan: progress against a baseline, pace against a target date, and a tiny sparkline.

Progress is clamped to 0-100 so a spectacular overshoot does not distort the chart, but the raw
latest value is always shown next to it. Pace compares progress with the share of time elapsed.
"""

from __future__ import annotations

from datetime import date

from ..models import Kpi, KpiReading

STATUS_LABELS = {
    "reached": "Reached",
    "ahead": "Ahead",
    "on_track": "On track",
    "behind": "Behind",
    "missed": "Missed",
    "no_data": "No readings",
}
STATUS_ORDER = {"missed": 0, "behind": 1, "no_data": 2, "on_track": 3, "ahead": 4, "reached": 5}
PACE_TOLERANCE = 10.0


def latest_reading(kpi: Kpi) -> KpiReading | None:
    if not kpi.readings:
        return None
    return max(kpi.readings, key=lambda r: (r.recorded_on, r.id))


def ordered_readings(kpi: Kpi) -> list[KpiReading]:
    return sorted(kpi.readings, key=lambda r: (r.recorded_on, r.id))


def progress(kpi: Kpi, value: float | None) -> float | None:
    """0-100 share of the way from baseline to target, respecting direction."""
    if value is None:
        return None
    if kpi.direction == "down":
        span = kpi.baseline - kpi.target
        moved = kpi.baseline - value
    else:
        span = kpi.target - kpi.baseline
        moved = value - kpi.baseline
    if abs(span) < 1e-9:
        reached = value <= kpi.target if kpi.direction == "down" else value >= kpi.target
        return 100.0 if reached else 0.0
    return round(max(0.0, min(100.0, moved / span * 100)), 1)


def expected_progress(kpi: Kpi, today: date) -> float | None:
    """The progress a straight line from creation to target date would have reached today."""
    if kpi.target_date is None:
        return None
    start = kpi.created_at.date()
    total = (kpi.target_date - start).days
    if total <= 0:
        return 100.0
    elapsed = (today - start).days
    if elapsed <= 0:
        return 0.0
    if elapsed >= total:
        return 100.0
    return round(elapsed / total * 100, 1)


def status_for(kpi: Kpi, today: date) -> tuple[str, dict]:
    reading = latest_reading(kpi)
    expected = expected_progress(kpi, today)
    base = {
        "latest": reading,
        "progress": None,
        "expected": expected,
        "delta": None,
        "from_baseline": None,
    }
    if reading is None:
        return "no_data", base
    value = reading.value
    p = progress(kpi, value)
    base["progress"] = p
    base["from_baseline"] = round(value - kpi.baseline, 2)
    if p is not None and p >= 100:
        return "reached", base
    if kpi.target_date is not None and today > kpi.target_date:
        return "missed", base
    if expected is None:
        # Without a date, use a plain midpoint rule and say so in the docs.
        return ("on_track" if (p or 0) >= 50 else "behind"), base
    delta = round((p or 0) - expected, 1)
    base["delta"] = delta
    if delta >= PACE_TOLERANCE:
        return "ahead", base
    if delta <= -PACE_TOLERANCE:
        return "behind", base
    return "on_track", base


def sparkline(readings: list[KpiReading], width: int = 132, height: int = 34, pad: int = 3) -> dict | None:
    """Points for an inline SVG polyline; None when there is nothing to draw."""
    if len(readings) < 2:
        return None
    values = [r.value for r in readings]
    low, high = min(values), max(values)
    span = high - low
    usable_w = width - pad * 2
    usable_h = height - pad * 2
    points = []
    for index, value in enumerate(values):
        x = pad + (usable_w * index / (len(values) - 1))
        y = pad + (usable_h / 2 if span == 0 else usable_h * (1 - (value - low) / span))
        points.append(f"{x:.1f},{y:.1f}")
    return {"points": " ".join(points), "width": width, "height": height, "low": low, "high": high}


def item(kpi: Kpi, today: date) -> dict:
    key, detail = status_for(kpi, today)
    return {
        "kpi": kpi,
        "status": key,
        "status_label": STATUS_LABELS[key],
        "spark": sparkline(ordered_readings(kpi)),
        **detail,
    }


def summary(kpis: list[Kpi], today: date) -> dict:
    items = [item(kpi, today) for kpi in kpis]
    measured = [row for row in items if row["status"] != "no_data"]
    healthy = [row for row in measured if row["status"] in ("reached", "ahead", "on_track")]
    return {
        "total": len(items),
        "measured": len(measured),
        "healthy": len(healthy),
        "health_percent": round(len(healthy) / len(measured) * 100) if measured else None,
        "items": items,
        "counts": {key: sum(1 for row in items if row["status"] == key) for key in STATUS_LABELS},
        "attention": sorted(
            [row for row in items if row["status"] in ("missed", "behind")],
            key=lambda row: STATUS_ORDER.get(row["status"], 9),
        ),
    }
