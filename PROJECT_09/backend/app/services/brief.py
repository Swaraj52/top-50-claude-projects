"""Assemble a strategy brief from the venture's own inputs.

The brief never invents a number: every sentence is built from canvas entries, the revenue model,
the plan or the KPI log. When something is missing it says so, which is more useful than a
confident paragraph with nothing behind it.
"""

from __future__ import annotations

from ..forms import money, number
from ..models import CANVAS_LABELS, STAGE_LABELS, CanvasEntry, Venture


def _entry(entries: list[CanvasEntry], block: str) -> CanvasEntry | None:
    for entry in entries:
        if entry.block == block:
            return entry
    return None


def _entry_text(entry: CanvasEntry | None) -> str:
    if entry is None:
        return ""
    if entry.detail:
        return f"{entry.title} — {entry.detail}"
    return entry.title


def _money(amount: int, currency: str) -> str:
    return money(amount, currency)


def sections(
    venture: Venture,
    entries: list[CanvasEntry],
    finance: dict,
    milestones: dict,
    kpis: dict,
    swot: dict,
) -> list[dict]:
    """The brief as six headed blocks, each a list of short paragraphs."""
    currency = venture.currency
    blocks: list[dict] = []

    opening = [f"{venture.name} is a {STAGE_LABELS.get(venture.stage, venture.stage).lower()} venture."]
    if venture.one_liner:
        opening.append(venture.one_liner)
    if venture.segment:
        opening.append(f"It is aimed at {venture.segment}.")
    if venture.market:
        opening.append(venture.market)
    blocks.append({"key": "opening", "heading": "The opening", "body": opening})

    problem = _entry_text(_entry(entries, "problem"))
    value = _entry_text(_entry(entries, "value"))
    customers = _entry_text(_entry(entries, "customers"))
    market_bits = []
    if problem:
        market_bits.append(f"The problem: {problem}")
    if customers:
        market_bits.append(f"Who feels it: {customers}")
    if value:
        market_bits.append(f"The promise: {value}")
    if venture.alternatives:
        market_bits.append(f"What people use instead: {venture.alternatives}")
    if venture.differentiation:
        market_bits.append(f"Why this is different: {venture.differentiation}")
    if market_bits:
        blocks.append({"key": "market", "heading": "Where it plays", "body": market_bits})

    model = []
    if finance["streams"] == 0:
        model.append("No revenue streams are defined yet, so the model is not costed.")
    else:
        model.append(
            f"At base case the model earns {_money(finance['expected_mrr'], currency)} a month, "
            f"or {_money(finance['arr'], currency)} a year, on {finance['volume']:,} paying units."
        )
        model.append(
            f"Confidence weighting puts it at {_money(finance['weighted_mrr'], currency)} a month; "
            f"monthly cost is {_money(finance['total_cost'], currency)}."
        )
        if finance["margin"] >= 0:
            margin_line = f"That leaves {_money(finance['margin'], currency)} a month"
            if finance["margin_percent"] is not None:
                margin_line += f" ({finance['margin_percent']}% margin)"
            model.append(margin_line + ".")
        else:
            model.append(
                f"That is a {_money(abs(finance['margin']), currency)} monthly shortfall at base case."
            )
        if finance["breakeven_units"]:
            model.append(
                f"Break-even needs {finance['breakeven_units']:,} paying units at the blended price "
                f"of {_money(round(finance['blended_price']), currency)}."
            )
    blocks.append({"key": "model", "heading": "How it earns", "body": model})

    plan = []
    if milestones["total"] == 0:
        plan.append("No milestones are planned yet.")
    else:
        plan.append(
            f"{milestones['done']} of {milestones['total']} milestones are done "
            f"({milestones['progress']}%)."
        )
        nxt = milestones["next_due"]
        if nxt is not None:
            due = f" due {nxt.due_date:%d %b %Y}" if nxt.due_date else " with no date"
            plan.append(f"Next: {nxt.title}{due}.")
        if milestones["overdue_count"]:
            plan.append(f"{milestones['overdue_count']} open milestone(s) are already overdue.")
    blocks.append({"key": "execution", "heading": "What happens next", "body": plan})

    proof = []
    if kpis["total"] == 0:
        proof.append("No KPIs are defined yet, so there is nothing to measure the plan against.")
    else:
        if kpis["health_percent"] is not None:
            proof.append(
                f"{kpis['healthy']} of {kpis['measured']} measured KPIs are on pace "
                f"({kpis['health_percent']}% of the plan)."
            )
        reached = [row for row in kpis["items"] if row["status"] == "reached"]
        if reached:
            names = ", ".join(row["kpi"].name for row in reached[:3])
            proof.append(f"Already reached: {names}.")
        attention = kpis["attention"][:2]
        for row in attention:
            latest = row["latest"]
            if latest is not None:
                proof.append(
                    f"{row['kpi'].name} is {row['status_label'].lower()} at "
                    f"{number(latest.value, row['kpi'].unit)}, against a target of "
                    f"{number(row['kpi'].target, row['kpi'].unit)}."
                )
    blocks.append({"key": "proof", "heading": "What would prove it", "body": proof})

    risks = []
    if swot["total"] == 0:
        risks.append("No SWOT items are recorded yet.")
    else:
        risks.append(
            f"The SWOT ledger is {swot['tone_label'].lower()} "
            f"(+{swot['positive']} positive impact vs {swot['negative']} negative)."
        )
        for item in swot["risks"][:2]:
            risks.append(f"Risk {item.impact}/5: {item.text}")
    if swot["total"] and swot["tone"] == "exposed":
        risks.append("The negative side outweighs the positive: resolve a risk before adding scope.")
    blocks.append({"key": "risks", "heading": "What could break it", "body": risks})
    return blocks


def memo(
    venture: Venture,
    entries: list[CanvasEntry],
    finance: dict,
    milestones: dict,
    kpis: dict,
    swot: dict,
) -> str:
    """A plain-prose memo for the narrative card, built from the same facts as the sections."""
    currency = venture.currency
    parts: list[str] = []

    lead = f"{venture.name} is a {STAGE_LABELS.get(venture.stage, venture.stage).lower()} venture"
    lead += f" aimed at {venture.segment}." if venture.segment else "."
    if venture.one_liner:
        lead += f" {venture.one_liner}"
    parts.append(lead)

    problem = _entry_text(_entry(entries, "problem"))
    value = _entry_text(_entry(entries, "value"))
    if problem or value:
        sentence = "The canvas argues that "
        if problem:
            sentence += f"the problem is {problem.rstrip('.')}"
            sentence += ", and " if value else "."
        if value:
            sentence += f"the promise is {value.rstrip('.')}."
        parts.append(sentence)
    elif venture.market:
        parts.append(venture.market)

    if finance["streams"]:
        numbers = (
            f"The base case is {_money(finance['expected_mrr'], currency)} a month against "
            f"{_money(finance['total_cost'], currency)} of monthly cost"
        )
        if finance["margin"] >= 0:
            numbers += f", leaving {_money(finance['margin'], currency)}"
            if finance["margin_percent"] is not None:
                numbers += f" ({finance['margin_percent']}% margin)"
            numbers += "."
        else:
            numbers += f", a {_money(abs(finance['margin']), currency)} shortfall."
        parts.append(numbers)
    else:
        parts.append("There is no revenue model yet, so the brief cannot make a financial claim.")

    if milestones["total"]:
        plan = f"{milestones['done']} of {milestones['total']} milestones are done"
        if milestones["next_due"] is not None:
            nxt = milestones["next_due"]
            plan += f", and the next is {nxt.title}"
            plan += f" due {nxt.due_date:%d %b}" if nxt.due_date else " (no date set)"
        plan += "."
        if milestones["overdue_count"]:
            plan += f" {milestones['overdue_count']} are overdue."
        parts.append(plan)

    if kpis["health_percent"] is not None:
        parts.append(
            f"{kpis['healthy']} of {kpis['measured']} measured KPIs are on pace, "
            f"which is {kpis['health_percent']}% of the plan."
        )
    elif kpis["total"] == 0:
        parts.append("No KPIs are defined yet.")

    if swot["total"]:
        risk = swot["risks"][0] if swot["risks"] else None
        line = f"On the SWOT ledger the venture is {swot['tone_label'].lower()}"
        if risk is not None:
            line += f"; the sharpest risk is {risk.text.rstrip('.')} ({risk.impact}/5 impact)"
        line += "."
        parts.append(line)

    missing = [CANVAS_LABELS[block] for block in ("problem", "customers", "value") if _entry(entries, block) is None]
    if missing:
        parts.append(f"The brief is thin on {', '.join(missing).lower()}.")
    return "\n\n".join(parts)


def prompt(venture: Venture, memo_text: str, blocks: list[dict]) -> str:
    """The user message for the optional Claude rewrite."""
    outline = "\n".join(
        f"- {block['heading']}: {' '.join(block['body'])}" for block in blocks
    )
    return (
        f"Venture: {venture.name}\nOne-liner: {venture.one_liner or 'not written'}\n"
        f"Stage: {STAGE_LABELS.get(venture.stage, venture.stage)}\n\n"
        f"Local brief:\n{memo_text}\n\nFacts by section:\n{outline}\n\n"
        "Rewrite this as a tight strategy memo of three to five paragraphs. Use only the facts "
        "above; do not invent numbers, customers or dates. Keep the founder's voice: plain, "
        "specific, no slogans. Return JSON: {\"narrative\": \"paragraph\\n\\nparagraph\"}."
    )
