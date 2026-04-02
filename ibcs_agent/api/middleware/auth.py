"""Middleware: validate Azure AD Bearer tokens (OAuth 2.0 / OIDC).

Bypass behaviour:
  - If AZURE_AD_TENANT_ID env var is empty / unset → middleware is a no-op.
    This allows local development and tests without real AAD credentials.
  - /health, /openapi.json, /docs, /redoc paths always pass unauthenticated.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

try:
    import jwt
    from jwt import PyJWKClient
    _HAS_JWT = True
except BaseException:  # covers ImportError and pyo3 PanicException (BaseException subclass)
    _HAS_JWT = False

# ---------------------------------------------------------------------------
# JWKS client cache (module-level, shared across requests)
# ---------------------------------------------------------------------------
_jwks_clients: Dict[str, Any] = {}  # tenant_id → PyJWKClient
_JWKS_CACHE_TTL = 3600  # 1 hour

# Paths that are always public (no token required)
_PUBLIC_PATHS = {"/health", "/openapi.json", "/docs", "/redoc"}


class AzureADAuthMiddleware(BaseHTTPMiddleware):
    """Validate Azure AD Bearer tokens on every protected endpoint."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        tenant_id = os.environ.get("AZURE_AD_TENANT_ID", "").strip()
        if not tenant_id:
            # Auth disabled (local dev / CI)
            return await call_next(request)

        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        token = _extract_bearer(request)
        if not token:
            return JSONResponse(status_code=401, content={"error": "Unauthorized", "detail": "Missing Bearer token"})

        client_id = os.environ.get("AZURE_AD_CLIENT_ID", "").strip()
        try:
            _validate_token(token, tenant_id, client_id)
        except Exception as exc:
            return JSONResponse(status_code=401, content={"error": "Unauthorized", "detail": str(exc)})

        return await call_next(request)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _validate_token(token: str, tenant_id: str, audience: str) -> None:
    """Raise HTTPException(401) on validation failure."""
    if not _HAS_JWT:
        # PyJWT not installed → skip validation (should not happen in production)
        return

    jwks_uri = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"

    if tenant_id not in _jwks_clients:
        _jwks_clients[tenant_id] = PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=_JWKS_CACHE_TTL)

    client: Any = _jwks_clients[tenant_id]
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        options = {"verify_aud": bool(audience)}
        kwargs: Dict[str, Any] = {
            "algorithms": ["RS256"],
            "options": options,
            "leeway": 60,
        }
        if audience:
            kwargs["audience"] = audience
        jwt.decode(token, signing_key.key, **kwargs)
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}")
    except Exception as exc:
        raise ValueError(f"Auth error: {exc}")
