"""One venture, summarised for the dashboard, the overview page and the brief."""

from __future__ import annotations

from datetime import date

from ..forms import money
from ..models import CANVAS_LABELS, Venture
from . import canvas as canvas_service
from . import finance as finance_service
from . import kpis as kpi_service
from . import milestones as milestone_service
from . import swot as swot_service


def snapshot(venture: Venture, today: date) -> dict:
    entries = sorted(venture.canvas, key=lambda e: (e.sort_order, e.id))
    cv = canvas_service.completeness(entries)
    fin = finance_service.summary(venture.streams, venture.costs, currency=venture.currency)
    plan = milestone_service.summary(venture.milestones, today)
    health = kpi_service.summary(venture.kpis, today)
    ledger = swot_service.summary(venture.swot)
    return {
        "venture": venture,
        "entries": entries,
        "canvas": cv,
        "gaps": canvas_service.gaps(entries),
        "finance": fin,
        "scenarios": finance_service.scenario_table(venture.streams, venture.costs),
        "models": finance_service.by_model(venture.streams),
        "plan": plan,
        "kpis": health,
        "swot": ledger,
        "actions": next_actions(venture, cv, fin, plan, health, ledger),
        "currency": venture.currency,
    }


def next_actions(venture: Venture, cv: dict, fin: dict, plan: dict, health: dict, ledger: dict) -> list[dict]:
    """The few things worth doing next, in a deliberate order, with a reason each."""
    base = f"/ventures/{venture.id}"
    actions: list[dict] = []
    if cv["missing"]:
        first = cv["missing"][0]
        actions.append(
            {
                "label": f"Fill {len(cv['missing'])} canvas block{'s' if len(cv['missing']) > 1 else ''}",
                "why": f"Start with {CANVAS_LABELS[first]}.",
                "href": f"{base}/canvas",
            }
        )
    if not fin["streams"]:
        actions.append(
            {
                "label": "Add a revenue stream",
                "why": "Without one, the model cannot be costed or tested.",
                "href": f"{base}/revenue",
            }
        )
    elif not venture.costs:
        actions.append(
            {
                "label": "Cost the model",
                "why": "Revenue without costs cannot show a margin.",
                "href": f"{base}/revenue",
            }
        )
    if plan["overdue_count"]:
        actions.append(
            {
                "label": f"Resolve {plan['overdue_count']} overdue milestone{'s' if plan['overdue_count'] > 1 else ''}",
                "why": "Move the date, finish it, or mark the risk honestly.",
                "href": f"{base}/plan",
            }
        )
    if health["total"] == 0:
        actions.append(
            {
                "label": "Define your KPIs",
                "why": "Three numbers are enough to show whether the plan works.",
                "href": f"{base}/kpis",
            }
        )
    elif health["attention"]:
        actions.append(
            {
                "label": f"Review {len(health['attention'])} KPI{'s' if len(health['attention']) > 1 else ''} off pace",
                "why": "A reading below the plan is a decision, not a report.",
                "href": f"{base}/kpis",
            }
        )
    if ledger["total"] == 0:
        actions.append(
            {
                "label": "Record strengths and risks",
                "why": "The SWOT ledger keeps the brief honest.",
                "href": f"{base}/swot",
            }
        )
    elif ledger["tone"] == "exposed":
        actions.append(
            {
                "label": "Address the top risk",
                "why": f"The ledger is {ledger['tone_label'].lower()}.",
                "href": f"{base}/swot",
            }
        )
    if not venture.narrative:
        actions.append(
            {
                "label": "Write the strategy brief",
                "why": "Turn the canvas into one page you can send.",
                "href": f"{base}/brief",
            }
        )
    return actions[:4]


def headline(venture: Venture, snap: dict) -> dict:
    """Values for the dashboard row, kept in one place so the card and overview agree."""
    fin = snap["finance"]
    return {
        "mrr": money(fin["expected_mrr"], venture.currency),
        "weighted": money(fin["weighted_mrr"], venture.currency),
        "margin": money(fin["margin"], venture.currency),
        "margin_percent": fin["margin_percent"],
        "canvas": snap["canvas"]["percent"],
        "milestones": f"{snap['plan']['done']}/{snap['plan']['total']}",
        "kpi_health": snap["kpis"]["health_percent"],
        "next": snap["plan"]["next_due"],
        "overdue": snap["plan"]["overdue_count"],
    }
