from fastapi import APIRouter, Depends

from .. import __version__
from ..config import Settings
from ..deps import get_settings
from ..schemas import MetaOut

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/meta", response_model=MetaOut)
def meta(settings: Settings = Depends(get_settings)) -> MetaOut:
    return MetaOut(version=__version__, ai_enabled=settings.ai_enabled, ai_model=settings.anthropic_model if settings.ai_enabled else None)
