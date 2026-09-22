"""api — FastAPI, desktop-facing. Run under Uvicorn workers.

Imports domain code from src/licensing only; contains no business logic
itself (see docs/architecture.md layering rules).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.error_handlers import register_exception_handlers
from apps.api.middleware import correlation_id_and_access_log
from apps.api.routers import (
    account_links,
    activation,
    alarm_rules,
    chambers,
    health,
    licenses,
    test_profiles,
)
from licensing.config import get_settings

logging.basicConfig(level=get_settings().log_level)


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_production()

    # Docs URLs are under /api/ so they resolve correctly whether hit
    # directly on this container or through Nginx's /api/ proxy prefix
    # (see nginx/nginx.conf — the prefix is forwarded, not stripped).
    docs_enabled = not settings.is_production
    app = FastAPI(
        title="deepvac-insight Licensing API",
        version="1.0.0",
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url="/api/redoc" if docs_enabled else None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )

    app.middleware("http")(correlation_id_and_access_log)
    register_exception_handlers(app)

    # Desktop clients call this API directly (not via browser XHR from a
    # webpage), but CORS is configured narrowly in case a future web-based
    # activation helper needs it.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.management_base_url],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(activation.router, prefix="/api/v1")
    app.include_router(account_links.router, prefix="/api/v1")
    app.include_router(licenses.router, prefix="/api/v1")
    app.include_router(test_profiles.router, prefix="/api/v1")
    app.include_router(chambers.router, prefix="/api/v1")
    app.include_router(alarm_rules.router, prefix="/api/v1")

    return app


app = create_app()
