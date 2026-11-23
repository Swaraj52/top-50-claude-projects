from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..models import Person, Run, Sop
from ..services import overview as overview_service
from ..web import Ctx, ctx, get_db, render

router = APIRouter()


def library(db: DbSession, user_id: int) -> list[Sop]:
    return db.scalars(
        select(Sop)
        .options(selectinload(Sop.owner), selectinload(Sop.steps))
        .where(Sop.user_id == user_id)
    ).all()


def run_rows(db: DbSession, user_id: int) -> list[Run]:
    return db.scalars(
        select(Run)
        .join(Sop, Sop.id == Run.sop_id)
        .options(selectinload(Run.items), selectinload(Run.sop), selectinload(Run.owner))
        .where(Sop.user_id == user_id)
    ).all()


def people_rows(db: DbSession, user_id: int) -> list[Person]:
    return db.scalars(select(Person).where(Person.user_id == user_id).order_by(Person.name)).all()


@router.get("/")
def dashboard_page(
    request: Request,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    sops = library(db, c.user.id)
    runs = run_rows(db, c.user.id)
    people = people_rows(db, c.user.id)
    data = overview_service.dashboard(sops, runs, people, c.today)
    return render(request, "dashboard.html", c, **data)
