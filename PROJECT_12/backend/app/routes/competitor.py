from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select, func

from ..web import get_db, utcnow
from ..models import User, Session as SessionModel, Competitor, Comparison, OpportunityNote
from ..web import ctx

router = APIRouter()


@router.get("/")
async def competitor_dashboard(request: Request, db=Depends(get_db), user=Depends(ctx)):
    """Competitor research dashboard."""
    ctx_data = ctx(request, db)
    user_id = ctx_data.user_id if ctx_data else 0

    # Count competitors for this user
    count = db.scalar(
        select(func.count(Competitor.id)).where(Competitor.user_id == user_id)
    ) or 0

    # Get competitors with their comparison data
    competitors = db.scalars(
        select(Competitor).where(Competitor.user_id == user_id)
        .order_by(Competitor.name.asc())
    ).all() if user_id else []

    # Get opportunity notes
    opportunities = db.scalars(
        select(OpportunityNote).where(OpportunityNote.user_id == user_id)
        .order_by(OpportunityNote.created_at.desc())
    ).all() if user_id else []

    return await render(
        request,
        "competitor_dashboard.html",
        {
            "competitor_count": count,
            "competitors": competitors,
            "opportunities": opportunities,
        }
    )


@router.post("/add")
async def competitor_add(
    request: Request,
    db=Depends(get_db),
    user=Depends(ctx),
    name: str = ...,
    website: str = ...,
    positioning: str = ...,
):
    """Add a new competitor."""
    form = await request.form()
    name = form.get("name")
    website = form.get("website")
    positioning = form.get("positioning")

    if not name:
        return Response("Competitor name is required", status_code=400)

    competitor = Competitor(
        user_id=user.id,
        name=name,
        website=website or "",
        positioning=positioning or "",
    )
    db.add(competitor)
    db.commit()
    db.refresh(competitor)

    return {"status": "success", "competitor_id": competitor.id}


@router.post("/comparison/add")
async def comparison_add(
    request: Request,
    db=Depends(get_db),
    user=Depends(ctx),
    competitor_id: int = ...,
    metric: str = ...,
    score: float = ...,
    notes: str = ...,
):
    """Add a comparison entry for a competitor."""
    form = await request.form()
    competitor_id = int(form.get("competitor_id"))
    metric = form.get("metric")
    score = float(form.get("score")) if form.get("score") else None
    notes = form.get("notes")

    comparison = Comparison(
        user_id=user.id,
        competitor_id=competitor_id,
        metric=metric,
        score=score,
        notes=notes or "",
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)

    return {"status": "success", "comparison_id": comparison.id}


@router.post("/opportunity/add")
async def opportunity_add(
    request: Request,
    db=Depends(get_db),
    user=Depends(ctx),
    competitor_id: int = ...,
    title: str = ...,
    description: str = ...,
):
    """Add an opportunity note for a competitor."""
    form = await request.form()
    competitor_id = int(form.get("competitor_id"))
    title = form.get("title")
    description = form.get("description")

    opportunity = OpportunityNote(
        user_id=user.id,
        competitor_id=competitor_id,
        title=title,
        description=description,
    )
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)

    return {"status": "success", "opportunity_id": opportunity.id}


@router.post("/clear")
async def competitor_clear(
    request: Request,
    db=Depends(get_db),
    user=Depends(ctx),
):
    """Clear all competitor data."""
    from ..models import Competitor, Comparison, OpportunityNote

    db.execute(
        delete(Competitor).where(Competitor.user_id == user.id)
    )
    db.execute(
        delete(Comparison).where(Comparison.user_id == user.id)
    )
    db.execute(
        delete(OpportunityNote).where(OpportunityNote.user_id == user.id)
    )
    db.commit()
    return {"status": "success", "redirect": "/competitor"}