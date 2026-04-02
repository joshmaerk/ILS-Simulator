"""Analysis route: POST /v1/analyze-file."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ibcs_agent.agent.tools import analyze_file as _analyze_file_tool
from ibcs_agent.api.schemas.requests import AnalyzeFileRequest, ErrorResponse
from ibcs_agent.models.feedback import IBCSFeedbackReport

router = APIRouter(prefix="/v1", tags=["analysis"])


@router.post(
    "/analyze-file",
    response_model=IBCSFeedbackReport,
    summary="Analyze a file for IBCS compliance",
    operation_id="analyzeFile",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file or request"},
        413: {"model": ErrorResponse, "description": "File exceeds 20 MB limit"},
        422: {"model": ErrorResponse, "description": "Request validation error"},
        500: {"model": ErrorResponse, "description": "Analysis failed"},
    },
)
async def analyze_file_endpoint(body: AnalyzeFileRequest, request: Request) -> Any:
    """
    Analyse a PowerPoint, PDF or Excel file for IBCS SUCCESS standard compliance.

    The file must be provided as a **base64-encoded string**.
    Returns a structured `IBCSFeedbackReport` with per-page violations,
    an overall compliance score and grade (A–F), and correction suggestions.

    **File size limit**: 20 MB (Microsoft Power Platform connector limit).
    """
    correlation_id: str = getattr(request.state, "correlation_id", "")

    # --- basic size guard before decoding ---------------------------------
    # base64 overhead is ~33 %; 20 MB decoded → max ~27 MB encoded
    MAX_ENCODED_BYTES = 27_000_000
    if len(body.file_content_base64) > MAX_ENCODED_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Encoded payload exceeds {MAX_ENCODED_BYTES // 1_000_000} MB limit.",
        )

    # --- run blocking analysis in thread pool ----------------------------
    start = time.perf_counter()
    loop = asyncio.get_event_loop()

    try:
        raw_result: str = await loop.run_in_executor(
            None,
            lambda: _analyze_file_tool(
                body.file_content_base64,
                body.file_name,
                body.file_type,
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis engine error: {exc}") from exc

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # --- parse result -------------------------------------------------------
    try:
        result_dict = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON from analysis engine: {exc}") from exc

    if "error" in result_dict:
        # Map engine-level errors to appropriate HTTP codes
        error_msg: str = str(result_dict["error"])
        if any(kw in error_msg.lower() for kw in ("unsupported", "invalid", "extension")):
            raise HTTPException(status_code=400, detail=error_msg)
        if any(kw in error_msg.lower() for kw in ("size", "too large", "limit")):
            raise HTTPException(status_code=413, detail=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

    try:
        report = IBCSFeedbackReport.model_validate(result_dict)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report serialisation error: {exc}") from exc

    return report
