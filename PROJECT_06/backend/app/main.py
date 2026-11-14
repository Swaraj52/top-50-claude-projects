from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import BACKEND_DIR, Settings
from .db import make_engine, make_sessionmaker
from .routes import auth, meetings, settings as settings_routes
from .security import SlidingWindowLimiter
from .web import LoginRequired, is_htmx, optional_ctx, render, see_other

log = logging.getLogger("quorum")

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


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
        log.info("Memory extractor: %s", "Claude enabled" if settings.ai_enabled else "local extractor (no key)")
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="Quorum: Meeting Memory Assistant",
        version=__version__,
        description="Turn meeting notes into a summary, decisions, owners and follow-ups.",
        contact={"name": "Swayam"},
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    engine = make_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.login_limiter = SlidingWindowLimiter(limit=10, window=15 * 60)
    app.state.extract_limiter = SlidingWindowLimiter(limit=6, window=10 * 60)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.exception_handler(LoginRequired)
    async def login_required(request: Request, _exc: LoginRequired):
        if is_htmx(request):
            return Response(status_code=401, headers={"HX-Redirect": "/login"})
        return see_other("/login")

    async def show_error(request: Request, status: int, message: str):
        if is_htmx(request):
            return Response(
                status_code=status,
                headers={"HX-Reswap": "none", "HX-Trigger": json.dumps({"app-error": message})},
            )
        db = request.app.state.sessionmaker()
        try:
            c = optional_ctx(request, db)
            return render(request, "error.html", c, http_status=status, status_code=status, message=message)
        finally:
            db.close()

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if request.url.path == "/health":
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        message = exc.detail if isinstance(exc.detail, str) else "Something went wrong"
        if exc.status_code == 404 and message == "Not Found":
            message = "That page doesn't exist."
        return await show_error(request, exc.status_code, message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = str(first.get("loc", ["", "value"])[-1]).replace("_", " ")
        return await show_error(request, 422, f"Please check the {field} field.")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
    for router in (auth.router, meetings.router, settings_routes.router):
        app.include_router(router)
    return app
