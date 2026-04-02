"""Global exception handlers for the IBCS Feedback Agent API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ibcs_agent.api.schemas.requests import ErrorResponse


def _correlation_id(request: Request) -> str:
    """Extract correlation ID set by CorrelationMiddleware."""
    return getattr(request.state, "correlation_id", "")


def register_error_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to *app*."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=_http_status_label(exc.status_code),
                detail=str(exc.detail),
                correlation_id=_correlation_id(request),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="Validation error",
                detail=str(exc),
                correlation_id=_correlation_id(request),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal server error",
                detail=type(exc).__name__,
                correlation_id=_correlation_id(request),
            ).model_dump(),
        )


def _http_status_label(status_code: int) -> str:
    _labels = {
        400: "Bad request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not found",
        413: "Payload too large",
        422: "Unprocessable entity",
        500: "Internal server error",
        503: "Service unavailable",
    }
    return _labels.get(status_code, f"HTTP {status_code}")
