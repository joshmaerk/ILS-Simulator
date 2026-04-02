"""Tests for GET /health."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_json_has_status(client: TestClient) -> None:
    resp = client.get("/health")
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded", "unhealthy")


def test_health_no_auth_required(client: TestClient) -> None:
    """Health endpoint must be accessible without Authorization header."""
    resp = client.get("/health", headers={})
    assert resp.status_code in (200, 503)  # not 401
