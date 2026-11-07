from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from ..config import Settings
from ..deps import current_user, get_db, get_settings, user_zone
from ..models import Briefing, User
from ..schemas import BriefingOut
from ..services import briefing as engine
from ..services.today import take_snapshot, to_day_context
from ..timeutil import local_today
from .dashboard import latest_briefing

router = APIRouter(prefix="/briefing", tags=["briefing"])
log = logging.getLogger(__name__)


def get_ai_client(request: Request) -> anthropic.Anthropic | None:
    """The Anthropic client, or None when no key is configured. Overridden in tests."""
    settings: Settings = request.app.state.settings
    if not settings.ai_enabled:
        return None
    client = getattr(request.app.state, "anthropic_client", None)
    if client is None:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0, max_retries=2)
        request.app.state.anthropic_client = client
    return client


@router.get("/today", response_model=BriefingOut | None)
def get_today(
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
):
    briefing = latest_briefing(db, user, local_today(tz))
    return BriefingOut.model_validate(briefing) if briefing else None


@router.post("", response_model=BriefingOut, status_code=status.HTTP_201_CREATED)
def generate(
    request: Request,
    user: User = Depends(current_user),
    tz: ZoneInfo = Depends(user_zone),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: anthropic.Anthropic | None = Depends(get_ai_client),
):
    limiter = request.app.state.briefing_limiter
    key = str(user.id)
    if limiter.blocked(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "A briefing was just generated. Wait a few seconds before regenerating.",
            headers={"Retry-After": str(limiter.retry_after(key))},
        )
    limiter.hit(key)

    ctx = to_day_context(take_snapshot(db, user, tz))
    source, model, note = "rule", None, None
    if client is not None:
        try:
            content = engine.generate_ai(ctx, client, settings.anthropic_model)
            source, model = "ai", settings.anthropic_model
        except engine.AIBriefingError as exc:
            log.warning("AI briefing failed for user %s: %s", user.id, exc)
            note = f"AI briefing unavailable: {exc}. Showing the rule-based summary instead."
            content = engine.generate_rule_based(ctx)
    else:
        content = engine.generate_rule_based(ctx)

    briefing = Briefing(
        user_id=user.id,
        day=ctx.day,
        source=source,
        model=model,
        note=note,
        content=content.model_dump(),
    )
    db.add(briefing)
    db.commit()
    return BriefingOut.model_validate(briefing)
