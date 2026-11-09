from __future__ import annotations

import logging

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..config import Settings
from ..deps import current_user, get_db, get_owned, get_settings
from ..models import Question, Tag, User
from ..schemas import AskIn, AskOut
from ..services import ask as engine
from ..services.ai import AIError
from ..services.text import normalize_tag
from .common import ai_client, rate_limit

router = APIRouter(prefix="/ask", tags=["ask"])
log = logging.getLogger(__name__)

NOTHING_FOUND = (
    "Nothing in your library matches that question yet. Try different words, "
    "or save a few things on this topic first."
)
PASSAGES_ONLY = "No AI answer (Claude is not configured). These are the passages from your library that best match your question."


@router.post("", response_model=AskOut, status_code=status.HTTP_201_CREATED)
def ask(
    body: AskIn,
    request: Request,
    user: User = Depends(current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: anthropic.Anthropic | None = Depends(ai_client),
):
    rate_limit(request, "ask_limiter", str(user.id), "You're asking too quickly. Wait a moment and try again.")
    tag_id = None
    if body.tag:
        tag = db.scalar(select(Tag).where(Tag.user_id == user.id, Tag.name == normalize_tag(body.tag)))
        if tag is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No tag named '{body.tag}'")
        tag_id = tag.id

    question = body.question.strip()
    passages = engine.retrieve(db, user.id, question, tag_id)
    record = Question(user_id=user.id, question=question, source="passages", citations=[])

    if not passages:
        record.answer = NOTHING_FOUND
    elif client is not None:
        try:
            answer, cited, confidence = engine.answer_ai(question, passages, client, settings.anthropic_model)
            record.source, record.model, record.answer, record.confidence = "ai", settings.anthropic_model, answer, confidence
            record.citations = [p.citation() for p in passages if p.n in cited]
        except AIError as exc:
            log.warning("AI answer failed for user %s: %s", user.id, exc)
            record.note = f"AI answer unavailable: {exc}. Showing the most relevant passages instead."
            record.answer = "These are the passages from your library that best match your question."
            record.citations = [p.citation() for p in passages]
    else:
        record.answer = PASSAGES_ONLY
        record.citations = [p.citation() for p in passages]

    db.add(record)
    db.commit()
    return record


@router.get("/history", response_model=list[AskOut])
def history(limit: int = 30, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    return db.scalars(
        select(Question).where(Question.user_id == user.id).order_by(Question.created_at.desc(), Question.id.desc()).limit(min(max(limit, 1), 100))
    ).all()


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def forget(question_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    db.delete(get_owned(db, Question, question_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
