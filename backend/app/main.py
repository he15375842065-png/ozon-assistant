import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router
from app.core.config import Settings, get_settings
from app.core.errors import (
    ConflictError,
    IntegrationError,
    NotFoundError,
    OzonAssistantError,
    ValidationError,
)
from app.core.security import sanitize_for_log
from app.database import Database


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    runtime_database = database or Database(runtime_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        runtime_database.migrate()
        try:
            yield
        finally:
            from app.integrations.sources.browser_1688 import close_browser_managers
            try:
                close_browser_managers()
            finally:
                runtime_database.dispose()

    application = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        description="Local API for the 1688 → AI → Ozon draft workflow.",
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.database = runtime_database
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router, prefix=runtime_settings.api_prefix)

    error_statuses: list[tuple[type[OzonAssistantError], int]] = [
        (NotFoundError, 404),
        (ValidationError, 422),
        (ConflictError, 409),
        (IntegrationError, 502),
        (OzonAssistantError, 400),
    ]
    for exception_type, status_code in error_statuses:
        application.add_exception_handler(
            exception_type,
            _error_handler(status_code),
        )

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": runtime_settings.app_name,
            "docs": "/docs",
            "api": runtime_settings.api_prefix,
        }

    logging.basicConfig(
        level=getattr(logging, runtime_settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return application


def _error_handler(status_code: int):
    async def handler(_: Request, exc: Exception) -> JSONResponse:
        message = str(sanitize_for_log(str(exc)))
        return JSONResponse(
            status_code=status_code,
            content={
                "message": message,
                "error": {"code": exc.__class__.__name__, "message": message},
            },
        )

    return handler


app = create_app()
