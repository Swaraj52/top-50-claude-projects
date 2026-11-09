from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from . import __version__
from .config import BACKEND_DIR, Settings
from .db import make_engine, make_sessionmaker
from .routers import ask, auth, items, meta, search, tags
from .security import SlidingWindowLimiter

log = logging.getLogger("library")

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "library"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def run_migrations(database_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.run_migrations:
            run_migrations(settings.database_url)
        log.info("Claude features %s", "enabled" if settings.ai_enabled else "disabled (no key)")
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Life Library API", version=__version__, lifespan=lifespan, docs_url="/docs", redoc_url=None)
    engine = make_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.http_transport = None  # tests inject an httpx.MockTransport
    app.state.login_limiter = SlidingWindowLimiter(limit=10, window=15 * 60)
    app.state.summary_limiter = SlidingWindowLimiter(limit=6, window=60)
    app.state.ask_limiter = SlidingWindowLimiter(limit=10, window=60)

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        if (
            request.url.path.startswith("/api/")
            and request.method not in SAFE_METHODS
            and request.headers.get(CSRF_HEADER) != CSRF_VALUE
        ):
            return JSONResponse({"detail": "Missing X-Requested-With header (CSRF protection)"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "invalid")} for e in exc.errors()]
        first = errors[0] if errors else {"loc": [], "msg": "invalid request"}
        field = ".".join(str(p) for p in first["loc"] if p not in ("body", "query"))
        message = f"{field}: {first['msg']}" if field else first["msg"]
        return JSONResponse(status_code=422, content=jsonable_encoder({"detail": message, "errors": errors}))

    for router in (meta.router, auth.router, items.router, tags.router, search.router, ask.router):
        app.include_router(router, prefix="/api")

    _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.exists():
        return
    root = dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)
