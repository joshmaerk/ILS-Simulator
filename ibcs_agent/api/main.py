"""FastAPI application factory for the IBCS Feedback Agent REST API.

Entry point:
    uvicorn ibcs_agent.api.main:app --host 0.0.0.0 --port 8000

Copilot Studio Custom Connector:
    1. Export OpenAPI spec:  curl http://localhost:8000/openapi.json -o ibcs_openapi.json
    2. Import in Power Platform → Custom Connectors → New → Import OpenAPI file
    3. Security tab → OAuth 2.0 → Azure Active Directory
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ibcs_agent.api.errors import register_error_handlers
from ibcs_agent.api.middleware.auth import AzureADAuthMiddleware
from ibcs_agent.api.middleware.correlation import CorrelationMiddleware
from ibcs_agent.api.routes.analysis import router as analysis_router
from ibcs_agent.api.routes.health import router as health_router
from ibcs_agent.api.routes.rules import router as rules_router


def create_app(deployed_url: str = "") -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        deployed_url: Public HTTPS base URL (e.g. from Azure Container Apps).
                      Added to `servers` array in OpenAPI spec so Copilot Studio
                      can use the correct endpoint URL automatically.
    """
    servers = [{"url": deployed_url, "description": "Production"}] if deployed_url else []

    app = FastAPI(
        title="IBCS Feedback Agent API",
        description=(
            "REST API exposing IBCS SUCCESS standard compliance analysis for "
            "Microsoft Copilot Studio.\n\n"
            "Supported file formats: **PPTX**, **PDF**, **XLSX**.\n\n"
            "Authentication: **OAuth 2.0 / Azure AD** (Bearer token)."
        ),
        version="1.0.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        servers=servers,
        license_info={"name": "Proprietary"},
    )

    # ------------------------------------------------------------------
    # Middleware (outermost = first to run on request, last on response)
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://make.powerautomate.com",
            "https://flow.microsoft.com",
            "https://make.powerapps.com",
            "https://copilotstudio.microsoft.com",
        ],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "X-Correlation-ID", "Content-Type"],
        expose_headers=["X-Correlation-ID"],
    )
    app.add_middleware(AzureADAuthMiddleware)
    app.add_middleware(CorrelationMiddleware)

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------
    register_error_handlers(app)

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(health_router)
    app.include_router(analysis_router)
    app.include_router(rules_router)

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------
    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover
        try:
            from ibcs_agent.observability import configure_logging
            log_level = os.environ.get("LOG_LEVEL", "INFO")
            configure_logging(level=log_level)
        except Exception:
            pass  # observability module not available — silent fallback

    return app


# Module-level instance used by uvicorn / gunicorn
app = create_app(deployed_url=os.environ.get("API_BASE_URL", ""))
