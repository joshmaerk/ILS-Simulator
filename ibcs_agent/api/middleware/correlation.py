"""Middleware: propagate X-Correlation-ID through every request."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

try:
    from ibcs_agent.observability import set_correlation_id, clear_correlation_id
    _HAS_OBSERVABILITY = True
except Exception:
    _HAS_OBSERVABILITY = False


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Read or generate X-Correlation-ID and attach it to the request/response."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        # Store on request state so route handlers can read it
        request.state.correlation_id = cid

        if _HAS_OBSERVABILITY:
            set_correlation_id(cid)

        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid

        if _HAS_OBSERVABILITY:
            clear_correlation_id()

        return response
