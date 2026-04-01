"""
Enterprise observability for the IBCS Feedback Agent.

Provides:
- Structured JSON logging (compatible with Azure Monitor, Splunk, ELK)
- Correlation ID propagation (trace requests across Copilot Studio → Agent)
- Request/response timing
- Health check endpoint data
- Metrics counters (in-process, ready for Azure Application Insights export)

Designed for enterprise environments where log aggregation,
distributed tracing, and SLA monitoring are required.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

# ---------------------------------------------------------------------------
# Correlation ID context (propagated across async/sync call chains)
# ---------------------------------------------------------------------------

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get current correlation ID, generating one if not set."""
    cid = _correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())
        _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set correlation ID (call at request boundary, e.g. from HTTP header)."""
    _correlation_id.set(cid)


def clear_correlation_id() -> None:
    _correlation_id.set(None)


# ---------------------------------------------------------------------------
# Structured JSON log formatter
# ---------------------------------------------------------------------------

class StructuredJSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Compatible with:
    - Azure Monitor / Log Analytics (OMS)
    - Splunk HEC
    - ELK Stack (Logstash JSON input)
    - Google Cloud Logging
    """

    SERVICE_NAME = os.getenv("SERVICE_NAME", "ibcs-feedback-agent")
    SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.SERVICE_NAME,
            "version": self.SERVICE_VERSION,
            "environment": self.ENVIRONMENT,
            "correlation_id": get_correlation_id(),
        }

        # Merge extra fields from logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "id", "levelname", "levelno", "lineno", "message",
                "module", "msecs", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "thread",
                "threadName",
            ):
                log_entry[key] = value

        # Exception info
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def configure_logging(
    level: str = "INFO",
    structured: bool = True,
    stream=None,
) -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        structured: If True, use JSON formatter; otherwise use human-readable
        stream: Output stream (default: stdout)
    """
    if stream is None:
        stream = sys.stdout

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(stream)

    if structured:
        handler.setFormatter(StructuredJSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(correlation_id)s): %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))

    root_logger.addHandler(handler)

    # Suppress noisy Azure SDK logs unless in DEBUG mode
    if level != "DEBUG":
        for noisy in ("azure", "openai", "httpx", "httpcore", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Request timing context manager
# ---------------------------------------------------------------------------

@contextmanager
def timed_operation(operation_name: str, logger: Optional[logging.Logger] = None) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager that measures execution time and logs it.

    Usage:
        with timed_operation("analyze_pptx") as ctx:
            result = process_file(...)
            ctx["pages"] = len(result.slides)
    """
    _logger = logger or logging.getLogger("ibcs_agent.timing")
    context: Dict[str, Any] = {}
    start = time.perf_counter()

    try:
        yield context
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _logger.info(
            f"{operation_name} completed",
            extra={
                "operation": operation_name,
                "duration_ms": elapsed_ms,
                "correlation_id": get_correlation_id(),
                **context,
            },
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _logger.error(
            f"{operation_name} failed",
            extra={
                "operation": operation_name,
                "duration_ms": elapsed_ms,
                "error": str(exc),
                "correlation_id": get_correlation_id(),
            },
            exc_info=True,
        )
        raise


# ---------------------------------------------------------------------------
# In-process metrics (lightweight, no external dependency)
# ---------------------------------------------------------------------------

class Metrics:
    """
    Simple in-process metrics counters.

    In production, these should be exported to Azure Application Insights
    via the `opencensus-ext-azure` or `azure-monitor-opentelemetry` package.
    """

    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._histograms: Dict[str, list] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def record(self, name: str, value: float) -> None:
        self._histograms.setdefault(name, []).append(value)

    def snapshot(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"counters": dict(self._counters)}
        for name, values in self._histograms.items():
            if values:
                result.setdefault("histograms", {})[name] = {
                    "count": len(values),
                    "sum": sum(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                }
        return result

    def reset(self) -> None:
        self._counters.clear()
        self._histograms.clear()


_metrics = Metrics()


def get_metrics() -> Metrics:
    return _metrics


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check(check_azure: bool = False) -> Dict[str, Any]:
    """
    Return a health status dictionary for liveness/readiness probes.

    Suitable for:
    - Kubernetes liveness/readiness probes
    - Azure Container Apps health checks
    - Copilot Studio connector health endpoint

    Args:
        check_azure: If True, attempt a lightweight Azure connectivity check

    Returns:
        Dict with status ("healthy" | "degraded" | "unhealthy") and component details
    """
    from ibcs_agent.config import get_config, validate_config

    status = "healthy"
    components: Dict[str, Any] = {}

    # Config check
    try:
        cfg = get_config()
        config_errors = validate_config(cfg)
        components["config"] = {
            "status": "ok" if not config_errors else "degraded",
            "model": cfg.azure.model_name,
            "visual_analysis_enabled": cfg.analysis.enable_visual_analysis,
        }
        if config_errors:
            components["config"]["errors"] = config_errors
            status = "degraded"
    except Exception as e:
        components["config"] = {"status": "error", "detail": str(e)}
        status = "unhealthy"

    # Rules check
    try:
        from ibcs_agent.rules.ibcs_rules import ALL_RULES
        components["rules"] = {
            "status": "ok",
            "rule_count": len(ALL_RULES),
        }
    except Exception as e:
        components["rules"] = {"status": "error", "detail": str(e)}
        status = "unhealthy"

    # Azure connectivity (optional, skipped in CI)
    if check_azure:
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=cfg.azure.openai_endpoint,
                api_key=cfg.azure.openai_api_key,
                api_version=cfg.azure.openai_api_version,
            )
            models = client.models.list()
            components["azure_openai"] = {"status": "ok"}
        except Exception as e:
            components["azure_openai"] = {"status": "error", "detail": str(e)[:100]}
            status = "degraded"

    return {
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "service": StructuredJSONFormatter.SERVICE_NAME,
        "version": StructuredJSONFormatter.SERVICE_VERSION,
        "components": components,
        "metrics": get_metrics().snapshot(),
    }
