"""Ownership: who holds which process, and what nobody holds.

The tracker is derived from SOP owners; there is no separate assignment table to drift out of sync.
"""

from __future__ import annotations

from datetime import date

from ..models import AREAS, AREA_LABELS, Person, Sop
from .sops import review_state


def coverage(people: list[Person], sops: list[Sop], today: date) -> dict:
    active_sops = [sop for sop in sops if sop.status == "active"]
    rows = []
    for person in sorted(people, key=lambda p: (not p.active, p.name.lower())):
        owned = [sop for sop in sops if sop.owner_id == person.id]
        active = [sop for sop in owned if sop.status == "active"]
        due = [sop for sop in active if review_state(sop, today)["key"] in ("overdue", "never")]
        rows.append(
            {
                "person": person,
                "owned": len(owned),
                "active": len(active),
                "drafts": sum(1 for sop in owned if sop.status == "draft"),
                "due": len(due),
                "sops": sorted(active, key=lambda s: s.code),
            }
        )
    rows.sort(key=lambda row: (-row["active"], row["person"].name.lower()))
    unowned = sorted(
        [sop for sop in active_sops if sop.owner_id is None], key=lambda sop: sop.code
    )
    owned_active = len(active_sops) - len(unowned)
    return {
        "rows": rows,
        "people": len(people),
        "active_people": sum(1 for person in people if person.active),
        "active_sops": len(active_sops),
        "owned_active": owned_active,
        "unowned": unowned,
        "unowned_count": len(unowned),
        "coverage_percent": round(owned_active / len(active_sops) * 100) if active_sops else None,
    }


def matrix(people: list[Person], sops: list[Sop]) -> dict:
    """Area × person counts for active SOPs, plus a row total and an unowned column."""
    active = [sop for sop in sops if sop.status == "active"]
    ordered = sorted([p for p in people if p.active], key=lambda p: p.name.lower())
    rows = []
    for area in AREAS:
        in_area = [sop for sop in active if sop.area == area]
        cells = [
            {
                "person": person,
                "count": sum(1 for sop in in_area if sop.owner_id == person.id),
            }
            for person in ordered
        ]
        rows.append(
            {
                "area": area,
                "label": AREA_LABELS[area],
                "cells": cells,
                "unowned": sum(1 for sop in in_area if sop.owner_id is None),
                "total": len(in_area),
            }
        )
    totals = [
        sum(row["cells"][index]["count"] for row in rows) for index in range(len(ordered))
    ]
    return {"people": ordered, "rows": rows, "total": len(active), "totals": totals}

