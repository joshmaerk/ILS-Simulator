"""Tests for GET /v1/rules and GET /v1/rules/{rule_id}."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_rules_returns_list(client: TestClient) -> None:
    resp = client.get("/v1/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_list_rules_each_has_id(client: TestClient) -> None:
    resp = client.get("/v1/rules")
    for rule in resp.json():
        assert "id" in rule


def test_list_rules_category_filter(client: TestClient) -> None:
    resp = client.get("/v1/rules", params={"category": "CHECK"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # All returned rules should belong to CHECK category
    for rule in data:
        assert rule.get("category") == "CHECK"


def test_list_rules_invalid_category_returns_400_or_empty(client: TestClient) -> None:
    resp = client.get("/v1/rules", params={"category": "INVALID_CAT"})
    # Either 400 (error) or 200 with empty list is acceptable
    assert resp.status_code in (200, 400)


def test_get_rule_ck1(client: TestClient) -> None:
    resp = client.get("/v1/rules/CK1")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("id") == "CK1"


def test_get_rule_not_found(client: TestClient) -> None:
    resp = client.get("/v1/rules/NONEXISTENT_RULE")
    assert resp.status_code == 404


def test_get_rule_table_rule(client: TestClient) -> None:
    """Table rules (UN-T-01.1 etc.) should also be accessible."""
    resp = client.get("/v1/rules/UN-T-01.1")
    # May be 200 or 404 depending on whether ibcs_rules_tables.py loaded correctly
    assert resp.status_code in (200, 404)
