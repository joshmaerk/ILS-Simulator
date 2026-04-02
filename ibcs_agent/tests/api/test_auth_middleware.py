"""Tests for AzureADAuthMiddleware.

When AZURE_AD_TENANT_ID is set, requests without a token must get 401.
When unset (as in conftest), all requests pass through unauthenticated.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def auth_client() -> TestClient:
    """Client with auth middleware enabled (non-empty tenant ID)."""
    original = os.environ.get("AZURE_AD_TENANT_ID", "")
    os.environ["AZURE_AD_TENANT_ID"] = "dummy-tenant-id"
    try:
        from ibcs_agent.api.main import create_app
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        os.environ["AZURE_AD_TENANT_ID"] = original


def test_protected_route_requires_token(auth_client: TestClient) -> None:
    resp = auth_client.get("/v1/rules")
    assert resp.status_code == 401


def test_health_no_token_required(auth_client: TestClient) -> None:
    resp = auth_client.get("/health")
    assert resp.status_code in (200, 503)  # not 401


def test_openapi_no_token_required(auth_client: TestClient) -> None:
    resp = auth_client.get("/openapi.json")
    assert resp.status_code in (200, 404)  # not 401


def test_no_auth_when_tenant_unset(client: TestClient) -> None:
    """Default test client (AZURE_AD_TENANT_ID="") allows unauthenticated access."""
    resp = client.get("/v1/rules")
    assert resp.status_code == 200
