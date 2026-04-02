"""Pydantic request models for the IBCS Feedback Agent REST API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AnalyzeFileRequest(BaseModel):
    """Request body for POST /v1/analyze-file."""

    file_content_base64: str = Field(
        description="Base64-encoded file content (max 20 MB decoded).",
        max_length=28_000_000,  # ~20 MB after base64 overhead
    )
    file_name: str = Field(
        description="Original filename including extension (.pptx, .pdf, .xlsx).",
        max_length=200,
    )
    file_type: Optional[Literal["pptx", "pdf", "xlsx"]] = Field(
        default=None,
        description="Explicit file type override; detected from extension if omitted.",
    )

    model_config = {"json_schema_extra": {"example": {
        "file_content_base64": "<base64-encoded bytes>",
        "file_name": "Q1_Report.pptx",
    }}}


class ErrorResponse(BaseModel):
    """Standard error envelope returned by all error handlers."""

    error: str = Field(description="Short error category.")
    detail: Optional[str] = Field(default=None, description="Human-readable detail.")
    correlation_id: Optional[str] = Field(default=None, description="Request correlation ID.")
