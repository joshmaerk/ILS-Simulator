"""
Enterprise security utilities for the IBCS Feedback Agent.

Responsibilities:
- File type validation via magic bytes (prevents extension spoofing)
- File size enforcement
- Input sanitization (filenames, rule IDs)
- Path traversal prevention
- Audit logging (who analyzed what, when — GDPR-aware)
- Rate limit hooks

Designed for enterprise Copilot Studio deployments where files arrive
as base64 strings through a REST connector.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File magic byte signatures
# ---------------------------------------------------------------------------

# PPTX/XLSX are ZIP-based (PK\x03\x04)
_ZIP_MAGIC = b"\x50\x4b\x03\x04"
# PDF
_PDF_MAGIC = b"\x25\x50\x44\x46"  # %PDF

SUPPORTED_EXTENSIONS = frozenset({"pptx", "pdf", "xlsx", "ppt", "xls"})

EXTENSION_TO_TYPE = {
    "pptx": "pptx",
    "ppt": "pptx",
    "pdf": "pdf",
    "xlsx": "xlsx",
    "xls": "xlsx",
}

MAX_FILENAME_LENGTH = 200
SAFE_FILENAME_PATTERN = re.compile(r"^[\w\-. ]+$")


class SecurityError(ValueError):
    """Raised when a security check fails."""
    pass


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

def validate_file_magic(file_bytes: bytes, declared_type: str) -> None:
    """
    Validate that the file's magic bytes match the declared type.

    Prevents extension spoofing (e.g. a .exe renamed to .pptx).

    Args:
        file_bytes: Raw file content
        declared_type: "pptx", "pdf", or "xlsx"

    Raises:
        SecurityError if magic bytes don't match
    """
    if len(file_bytes) < 8:
        raise SecurityError("File too small to be a valid document")

    header = file_bytes[:8]

    if declared_type in ("pptx", "xlsx"):
        if not header.startswith(_ZIP_MAGIC):
            raise SecurityError(
                f"File does not appear to be a valid {declared_type.upper()} "
                f"(missing ZIP/Office Open XML signature)"
            )
    elif declared_type == "pdf":
        if not header.startswith(_PDF_MAGIC):
            raise SecurityError(
                "File does not appear to be a valid PDF (missing %PDF signature)"
            )


def validate_file_size(file_bytes: bytes, max_mb: float = 50.0) -> None:
    """
    Enforce maximum file size.

    Args:
        file_bytes: Raw file content
        max_mb: Maximum allowed size in megabytes

    Raises:
        SecurityError if file exceeds limit
    """
    actual_mb = len(file_bytes) / (1024 * 1024)
    if actual_mb > max_mb:
        raise SecurityError(
            f"File size {actual_mb:.1f} MB exceeds maximum allowed {max_mb:.0f} MB"
        )


def validate_filename(filename: str) -> str:
    """
    Sanitize and validate a filename.

    - Strips path components (prevents path traversal)
    - Normalizes Unicode
    - Enforces length and character restrictions
    - Returns the sanitized filename

    Args:
        filename: Original filename from user input

    Returns:
        Sanitized filename (basename only)

    Raises:
        SecurityError for invalid filenames
    """
    if not filename or not filename.strip():
        raise SecurityError("Filename must not be empty")

    # Strip path components (path traversal prevention)
    import os
    basename = os.path.basename(filename.replace("\\", "/"))

    # Unicode normalization (NFKC)
    basename = unicodedata.normalize("NFKC", basename).strip()

    if not basename:
        raise SecurityError("Filename is empty after sanitization")

    if len(basename) > MAX_FILENAME_LENGTH:
        raise SecurityError(f"Filename too long (max {MAX_FILENAME_LENGTH} characters)")

    # Prevent null bytes and control characters
    if any(ord(c) < 32 for c in basename):
        raise SecurityError("Filename contains control characters")

    # Extension check
    parts = basename.rsplit(".", 1)
    if len(parts) < 2:
        raise SecurityError(f"Filename '{basename}' has no extension")

    ext = parts[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise SecurityError(
            f"Unsupported file extension '.{ext}'. "
            f"Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    return basename


def validate_rule_id(rule_id: str) -> str:
    """
    Validate and normalize a rule ID input.

    Prevents injection via rule_id parameter.

    Returns:
        Uppercased, stripped rule ID

    Raises:
        SecurityError for invalid format
    """
    if not rule_id or not isinstance(rule_id, str):
        raise SecurityError("rule_id must be a non-empty string")

    normalized = rule_id.strip().upper()

    # Rule IDs are short alphanumeric codes like CK1, S1, SI4, ST3
    if not re.match(r"^[A-Z]{1,3}\d{1,2}$", normalized):
        raise SecurityError(
            f"Invalid rule_id format: '{rule_id}'. "
            "Expected format: 1-3 uppercase letters followed by 1-2 digits (e.g. CK1, E4, SI3)"
        )

    return normalized


def decode_and_validate_file(
    file_content_base64: str,
    file_name: str,
    max_mb: float = 50.0,
) -> tuple[bytes, str, str]:
    """
    Full validation pipeline for an incoming file.

    1. Decode base64
    2. Validate filename
    3. Detect/validate file type
    4. Check magic bytes
    5. Check size

    Args:
        file_content_base64: Base64-encoded file content
        file_name: Original filename
        max_mb: Maximum file size in MB

    Returns:
        Tuple of (file_bytes, sanitized_filename, file_type)

    Raises:
        SecurityError on validation failure
        ValueError on base64 decode failure
    """
    # Decode base64
    try:
        file_bytes = base64.b64decode(file_content_base64, validate=True)
    except Exception:
        raise ValueError("Invalid base64 encoding in file_content_base64")

    # Validate filename and detect type
    safe_name = validate_filename(file_name)
    ext = safe_name.rsplit(".", 1)[1].lower()
    file_type = EXTENSION_TO_TYPE[ext]

    # Validate magic bytes
    validate_file_magic(file_bytes, file_type)

    # Validate size
    validate_file_size(file_bytes, max_mb)

    return file_bytes, safe_name, file_type


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def _file_hash(file_bytes: bytes) -> str:
    """SHA-256 hash of file content (for audit trail, not PII)."""
    return hashlib.sha256(file_bytes).hexdigest()[:16]  # Truncated


class AuditLogger:
    """
    GDPR-aware audit logger for file analysis requests.

    Records:
    - Timestamp (UTC)
    - File type and hash (not file content)
    - Number of pages analyzed
    - Overall score
    - Correlation ID (for tracing across systems)

    Does NOT record:
    - File content
    - Usernames or email addresses (unless explicitly configured)
    - Violation descriptions (may contain business-sensitive data)
    """

    def __init__(self, logger_name: str = "ibcs_agent.audit"):
        self._log = logging.getLogger(logger_name)

    def log_analysis_request(
        self,
        file_name: str,
        file_type: str,
        file_bytes: bytes,
        correlation_id: Optional[str] = None,
        user_context: Optional[str] = None,
    ) -> None:
        """Log the start of a file analysis request."""
        self._log.info(
            "IBCS analysis requested",
            extra={
                "event": "analysis_request",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "file_type": file_type,
                "file_size_kb": round(len(file_bytes) / 1024, 1),
                "file_hash": _file_hash(file_bytes),
                "correlation_id": correlation_id or "none",
                "user_context": user_context or "anonymous",
            },
        )

    def log_analysis_complete(
        self,
        file_type: str,
        total_pages: int,
        overall_score: float,
        overall_grade: str,
        total_violations: int,
        duration_ms: int,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Log the completion of a file analysis."""
        self._log.info(
            "IBCS analysis complete",
            extra={
                "event": "analysis_complete",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "file_type": file_type,
                "total_pages": total_pages,
                "overall_score": round(overall_score, 3),
                "overall_grade": overall_grade,
                "total_violations": total_violations,
                "duration_ms": duration_ms,
                "correlation_id": correlation_id or "none",
            },
        )

    def log_security_event(
        self,
        event_type: str,
        detail: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Log a security-relevant event (validation failure, oversized file, etc.)."""
        self._log.warning(
            f"Security event: {event_type}",
            extra={
                "event": "security_event",
                "event_type": event_type,
                "detail": detail,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id or "none",
            },
        )


# Module-level singleton
_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    return _audit_logger
