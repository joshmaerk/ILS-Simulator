"""Tests for CorrelationMiddleware."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_correlation_id_echoed_on_response(client: TestClient) -> None:
    cid = "my-request-id-abc123"
    resp = client.get("/health", headers={"X-Correlation-ID": cid})
    assert resp.headers.get("x-correlation-id") == cid


def test_correlation_id_generated_when_absent(client: TestClient) -> None:
    resp = client.get("/health")
    header_value = resp.headers.get("x-correlation-id", "")
    assert header_value != ""
    # Should be a valid UUID
    try:
        uuid.UUID(header_value)
    except ValueError:
        pytest.fail(f"Generated correlation ID is not a UUID: {header_value!r}")


def test_correlation_id_consistent_in_response(client: TestClient) -> None:
    for _ in range(3):
        cid = str(uuid.uuid4())
        resp = client.get("/health", headers={"X-Correlation-ID": cid})
        assert resp.headers.get("x-correlation-id") == cid


import pytest
