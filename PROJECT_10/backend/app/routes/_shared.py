"""Ownership checks and small route helpers shared by the workspace modules."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import utcnow
from ..models import Person, Run, RunItem, Sop, SopStep


def owned_sop(db: DbSession, user_id: int, sop_id: int) -> Sop:
    sop = db.scalar(select(Sop).where(Sop.id == sop_id, Sop.user_id == user_id))
    if sop is None:
        raise HTTPException(404, "That process doesn't exist.")
    return sop


def owned_person(db: DbSession, user_id: int, person_id: int) -> Person:
    person = db.scalar(select(Person).where(Person.id == person_id, Person.user_id == user_id))
    if person is None:
        raise HTTPException(404, "That person doesn't exist.")
    return person


def owned_step(db: DbSession, user_id: int, step_id: int) -> tuple[SopStep, Sop]:
    step = db.get(SopStep, step_id)
    if step is None:
        raise HTTPException(404, "That step doesn't exist.")
    return step, owned_sop(db, user_id, step.sop_id)


def owned_run(db: DbSession, user_id: int, run_id: int) -> tuple[Run, Sop]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "That checklist doesn't exist.")
    return run, owned_sop(db, user_id, run.sop_id)


def owned_item(db: DbSession, user_id: int, item_id: int) -> tuple[RunItem, Run, Sop]:
    item = db.get(RunItem, item_id)
    if item is None:
        raise HTTPException(404, "That checklist item doesn't exist.")
    run, sop = owned_run(db, user_id, item.run_id)
    return item, run, sop


def touch(sop: Sop) -> None:
    sop.updated_at = utcnow()


def person_options(db: DbSession, user_id: int, include_id: int | None = None) -> list[Person]:
    """Active people, plus an inactive person already assigned so an edit does not silently drop them."""
    people = db.scalars(select(Person).where(Person.user_id == user_id).order_by(Person.name)).all()
    return [person for person in people if person.active or person.id == include_id]
