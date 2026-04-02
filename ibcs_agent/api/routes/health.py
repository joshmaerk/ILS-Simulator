"""Health check route: GET /health."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

try:
    from ibcs_agent.observability import health_check
    _HAS_HEALTH = True
except Exception:
    _HAS_HEALTH = False

router = APIRouter(tags=["operations"])


@router.get(
    "/health",
    summary="Health check",
    include_in_schema=False,
)
def health_endpoint(check_azure: bool = Query(default=False, description="Also probe Azure services")) -> JSONResponse:
    """Returns service health.  Used by Container Apps liveness / readiness probes."""
    if _HAS_HEALTH:
        result = health_check(check_azure=check_azure)
    else:
        result = {"status": "healthy", "note": "observability module unavailable"}

    status_code = 200 if result.get("status") == "healthy" else 503
    return JSONResponse(content=result, status_code=status_code)
