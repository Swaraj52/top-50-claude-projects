from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings
from .db import make_engine, make_sessionmaker, utcnow
from .routes.auth import router as auth_router
from .routes.feedback import router as feedback_router
from .web import LoginRequired, is_htmx, optional_ctx, render, see_other

log = logging.getLogger("foundry")


@asynccontextmanager
def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Initialize sessionmaker and store in app state
    settings = Settings()
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    app.sessionmaker = sessionmaker
    #
    from .web import init_templates
    init_templates(str(Path(__file__).parent / "templates"))
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="Customer Feedback Analyzer",
        version=__version__,
        description="Analyze customer feedback for sentiment themes, pain points, and feature requests",
        lifespan=lifespan,
    )

    # Mount static files
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include routes
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(feedback_router, prefix="/feedback", tags=["feedback"])

    # Add static middleware for favicon
    favicon_path = static_dir / "favicon.ico" if static_dir else None
    if favicon_path and favicon_path.exists():
        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon():
            from fastapi.responses import FileResponse
            return FileResponse(favicon_path)

    return app