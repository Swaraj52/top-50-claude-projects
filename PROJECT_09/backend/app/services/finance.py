"""Revenue model arithmetic.

Everything here is deterministic and integer-based: a stream is price x volume per month, and
costs are monthly. Confidence weights adjust the "weighted" total, and scenarios scale volume.
The point is that a reader can redo every number on paper.
"""

from __future__ import annotations

import math

from ..models import CONFIDENCE_WEIGHTS, REVENUE_MODEL_LABELS, RevenueStream, CostLine

SCENARIOS = (
    ("conservative", "Conservative", 0.7),
    ("base", "Base", 1.0),
    ("upside", "Upside", 1.4),
)
SCENARIO_FACTORS = {key: factor for key, _label, factor in SCENARIOS}


def stream_expected(stream: RevenueStream) -> int:
    return max(0, stream.price) * max(0, stream.volume)


def weighted_revenue(streams: list[RevenueStream]) -> int:
    total = 0.0
    for stream in streams:
        total += stream_expected(stream) * CONFIDENCE_WEIGHTS.get(stream.confidence, 0.7)
    return round(total)


def cost_totals(costs: list[CostLine]) -> tuple[int, int]:
    fixed = sum(c.amount for c in costs if c.kind == "fixed")
    variable = sum(c.amount for c in costs if c.kind == "variable")
    return fixed, variable


def summary(streams: list[RevenueStream], costs: list[CostLine], scenario: str = "base", currency: str = "INR") -> dict:
    factor = SCENARIO_FACTORS.get(scenario, 1.0)
    expected = sum(stream_expected(s) for s in streams)
    volume = sum(max(0, s.volume) for s in streams)
    fixed, variable = cost_totals(costs)
    total_cost = fixed + variable
    revenue = round(expected * factor)
    margin = revenue - total_cost
    blended = (expected / volume) if volume else 0.0
    breakeven = math.ceil(total_cost / blended) if blended > 0 else None
    return {
        "streams": len(streams),
        "expected_mrr": expected,
        "weighted_mrr": weighted_revenue(streams),
        "arr": expected * 12,
        "volume": volume,
        "fixed_cost": fixed,
        "variable_cost": variable,
        "total_cost": total_cost,
        "scenario": scenario,
        "scenario_factor": factor,
        "revenue": revenue,
        "margin": margin,
        "margin_percent": round(margin / revenue * 100) if revenue else None,
        "blended_price": round(blended, 2),
        "breakeven_units": breakeven,
        "breakeven_reached": expected >= total_cost and total_cost > 0,
        "costed": bool(streams) and bool(costs),
    }


def scenario_table(streams: list[RevenueStream], costs: list[CostLine]) -> list[dict]:
    rows = []
    for key, label, factor in SCENARIOS:
        row = summary(streams, costs, scenario=key)
        rows.append(
            {
                "key": key,
                "label": label,
                "factor": factor,
                "revenue": row["revenue"],
                "cost": row["total_cost"],
                "margin": row["margin"],
                "margin_percent": row["margin_percent"],
            }
        )
    return rows


def by_model(streams: list[RevenueStream]) -> list[dict]:
    """Revenue split by pricing model, largest first, with each model's share."""
    buckets: dict[str, int] = {}
    for stream in streams:
        buckets[stream.model] = buckets.get(stream.model, 0) + stream_expected(stream)
    total = sum(buckets.values())
    rows = [
        {
            "model": model,
            "label": REVENUE_MODEL_LABELS.get(model, model.title()),
            "amount": amount,
            "share": round(amount / total * 100) if total else 0,
        }
        for model, amount in buckets.items()
    ]
    return sorted(rows, key=lambda row: (-row["amount"], row["label"]))
