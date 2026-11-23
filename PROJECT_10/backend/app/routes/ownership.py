from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..models import Person, Sop
from ..services import ownership as ownership_service
from ..web import Ctx, ctx, get_db, render

router = APIRouter()


@router.get("/ownership")
def ownership_page(
    request: Request,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    people = db.scalars(select(Person).where(Person.user_id == c.user.id).order_by(Person.name)).all()
    sops = db.scalars(
        select(Sop).options(selectinload(Sop.owner), selectinload(Sop.steps)).where(Sop.user_id == c.user.id)
    ).all()
    return render(
        request,
        "ownership.html",
        c,
        cover=ownership_service.coverage(people, sops, c.today),
        matrix=ownership_service.matrix(people, sops),
        people=people,
    )
