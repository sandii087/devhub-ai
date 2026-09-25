"""HTTP boundary, health probes, and consistent non-sensitive errors."""

import logging
import json
from contextlib import asynccontextmanager
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from devhub import auth, core, github, ai
from devhub.config import settings
from devhub.db import engine
from devhub.http_limits import BodyLimitMiddleware

log = logging.getLogger("devhub.http")


def create_app() -> FastAPI:
    if settings.process_role != "api":
        raise RuntimeError("HTTP server requires PROCESS_ROLE=api")

    @asynccontextmanager
    async def lifespan(app):
        if settings.environment == "production":
            with engine.connect() as connection:
                unsafe = connection.scalar(
                    text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
                )
                owns = connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user"
                    )
                )
                if unsafe or owns:
                    raise RuntimeError("Production must use a non-owner PostgreSQL role without BYPASSRLS")
        yield

    app = FastAPI(
        title="DevHub API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[urlsplit(settings.app_origin).hostname, "127.0.0.1", "localhost", "testserver"],
    )
    app.add_middleware(BodyLimitMiddleware)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        started = monotonic()
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 1_048_576):
            response = JSONResponse({"detail": "Request body exceeds 1 MiB"}, status_code=413)
        else:
            try:
                response = await call_next(request)
            except Exception as exc:
                log.error(
                    "Unhandled request failure type=%s request_id=%s",
                    type(exc).__name__,
                    request.state.request_id,
                )
                response = JSONResponse(
                    {"detail": "Internal server error", "request_id": request.state.request_id},
                    status_code=500,
                )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        log.info(
            "request method=%s path=%s status=%s elapsed_ms=%.1f request_id=%s",
            request.method,
            json.dumps(getattr(request.scope.get("route"), "path", "unmatched")),
            response.status_code,
            (monotonic() - started) * 1000,
            request.state.request_id,
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail.get("detail", "Request failed") if isinstance(exc.detail, dict) else exc.detail
        code = (
            exc.detail.get("code", f"http_{exc.status_code}")
            if isinstance(exc.detail, dict)
            else f"http_{exc.status_code}"
        )
        return JSONResponse(
            {"detail": detail, "code": code, "request_id": request.state.request_id},
            exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {
                "detail": "Invalid request fields",
                "code": "validation_error",
                "errors": [
                    {"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()
                ],
                "request_id": request.state.request_id,
            },
            status_code=422,
        )

    @app.exception_handler(IntegrityError)
    async def conflict(request: Request, exc: IntegrityError):
        return JSONResponse(
            {
                "detail": "A record already exists or its relationships changed",
                "code": "conflict",
                "request_id": request.state.request_id,
            },
            status_code=409,
        )

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as db:
                revision = db.scalar(text("SELECT version_num FROM alembic_version"))
                if revision != "0002_ai":
                    raise HTTPException(503, "Database migration required")
        except SQLAlchemyError as exc:
            raise HTTPException(503, "Database unavailable") from exc
        return {"status": "ready"}

    app.include_router(auth.router)
    app.include_router(core.router)
    app.include_router(github.router)
    app.include_router(ai.router)
    return app


app = create_app()
