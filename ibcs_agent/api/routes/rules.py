"""Rules routes: GET /v1/rules, GET /v1/rules/{rule_id}."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from ibcs_agent.agent.tools import get_ibcs_rule_details, list_ibcs_rules

router = APIRouter(prefix="/v1", tags=["rules"])


@router.get(
    "/rules",
    summary="List IBCS rules",
    response_model=List[Dict[str, Any]],
    operation_id="listRules",
)
def list_rules_endpoint(
    category: Optional[str] = Query(
        default=None,
        description="Filter by SUCCESS category: SAY, UNIFY, CONDENSE, CHECK, EXPRESS, SIMPLIFY, STRUCTURE",
    )
) -> List[Dict[str, Any]]:
    """Return all IBCS rules, optionally filtered by SUCCESS category."""
    raw = list_ibcs_rules(category)  # type: ignore[arg-type]
    data = json.loads(raw)
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data  # type: ignore[return-value]


@router.get(
    "/rules/{rule_id}",
    summary="Get rule details",
    response_model=Dict[str, Any],
    operation_id="getRuleDetails",
)
def get_rule_endpoint(
    rule_id: str = Path(..., description="Rule ID, e.g. CK1, E4, U1, UN-T-01.1"),
) -> Dict[str, Any]:
    """Return metadata and guidance for a specific IBCS rule."""
    raw = get_ibcs_rule_details(rule_id)
    data = json.loads(raw)
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data  # type: ignore[return-value]
