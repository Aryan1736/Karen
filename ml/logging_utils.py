"""
Karen's Ear — Lightweight Structured Logging Utilities for ML Pipeline.

Provides structured logging helpers using Python's standard logging facilities.
Adheres to the observability specification in architecture/observability.md.

Key Safety Principles:
- Raw emergency text is NEVER logged by default to protect sensitive distress info.
- Credentials, tokens, and secrets are sanitized/redacted.
- Contextual ML fields (component, model_version, report_id, processing_status) are supported.
- Zero external dependencies.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# Sensitive keys that must be redacted if passed into extra context
SECRET_KEYS = frozenset({
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "auth",
    "authorization",
    "private_key",
})

# Text fields representing raw citizen distress dispatches that should not be dumped raw
RAW_TEXT_KEYS = frozenset({
    "text",
    "raw_text",
    "report_text",
    "emergency_text",
    "transcript",
    "dispatch_text",
})


def sanitize_context_value(key: str, value: Any, visited: set[int] | None = None) -> Any:
    """
    Sanitizes values passed to log records:
    - Redacts secrets and passwords.
    - Summarizes raw emergency text by length rather than logging full raw text.
    - Handles nested dictionaries and non-serializable objects.
    - Protects against circular references.
    """
    if visited is None:
        visited = set()

    obj_id = id(value)
    if isinstance(value, (dict, list, tuple)):
        if obj_id in visited:
            return "[CIRCULAR_REFERENCE]"
        visited.add(obj_id)

    normalized_key = key.lower().replace("-", "_")

    if any(secret in normalized_key for secret in SECRET_KEYS):
        return "[REDACTED_SECRET]"

    if normalized_key in RAW_TEXT_KEYS and isinstance(value, str):
        return f"[REDACTED_TEXT: length={len(value)}]"

    if isinstance(value, dict):
        return {
            k: sanitize_context_value(k, v, visited)
            for k, v in value.items()
            if k != "extra_context"
        }

    if isinstance(value, (list, tuple)):
        return [sanitize_context_value(key, v, visited) for v in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


class MLJsonFormatter(logging.Formatter):
    """
    Formats log records into single-line JSON adhering to
    Karen's Ear observability standards (architecture/observability.md Section 3).
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include standard ML contextual attributes if present
        for attr in ("component", "model_version", "report_id", "processing_status"):
            val = getattr(record, attr, None)
            if val is not None:
                payload[attr] = sanitize_context_value(attr, val)

        # Include any extra custom keys passed by the caller
        if hasattr(record, "extra_context") and isinstance(record.extra_context, dict):
            for k, v in record.extra_context.items():
                if k != "extra_context" and k not in payload:
                    payload[k] = sanitize_context_value(k, v)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class MLLoggerAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter that binds standard ML execution context to all log calls.
    Supports creating child contexts via with_context().
    """

    def __init__(self, logger: logging.Logger, extra: dict[str, Any] | None = None) -> None:
        super().__init__(logger, extra or {})

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = {k: v for k, v in self.extra.items() if k != "extra_context"}
        # Merge caller's extra kwargs if present
        passed_extra = kwargs.get("extra")
        if passed_extra and isinstance(passed_extra, dict):
            extra.update({k: v for k, v in passed_extra.items() if k != "extra_context"})

        # Clean caller extras and save under extra_context
        sanitized = {k: sanitize_context_value(k, v) for k, v in extra.items()}
        kwargs["extra"] = dict(sanitized)
        # Also store explicitly for the formatter
        kwargs["extra"]["extra_context"] = dict(sanitized)

        # Promote core fields directly to the record attributes
        for field in ("component", "model_version", "report_id", "processing_status"):
            if field in sanitized:
                kwargs["extra"][field] = sanitized[field]

        return msg, kwargs

    def with_context(
        self,
        component: str | None = None,
        model_version: str | None = None,
        report_id: str | None = None,
        processing_status: str | None = None,
        **custom_extras: Any,
    ) -> MLLoggerAdapter:
        """Derives a new adapter instance inheriting existing context plus updates."""
        new_extra = dict(self.extra)
        if component is not None:
            new_extra["component"] = component
        if model_version is not None:
            new_extra["model_version"] = model_version
        if report_id is not None:
            new_extra["report_id"] = report_id
        if processing_status is not None:
            new_extra["processing_status"] = processing_status
        new_extra.update(custom_extras)
        return MLLoggerAdapter(self.logger, new_extra)


def get_ml_logger(
    name: str = "karen.ml",
    component: str | None = None,
    model_version: str | None = None,
    report_id: str | None = None,
    processing_status: str | None = None,
) -> MLLoggerAdapter:
    """
    Returns a configured structured logger adapter for an ML subcomponent.

    Args:
        name: Hierarchical logger name (e.g. 'karen.ml.urgency')
        component: ML component name (e.g. 'urgency', 'classification', 'extraction')
        model_version: Pipeline or model version string
        report_id: Active emergency report identifier if available
        processing_status: Current execution status (e.g. 'SUCCESS', 'NEEDS_REVIEW')

    Returns:
        MLLoggerAdapter configured with JSON output and context propagation.
    """
    logger = logging.getLogger(name)

    # Initialize handler if the logger (or root) has no handlers attached
    if not logger.handlers and not logger.parent.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(MLJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    context: dict[str, Any] = {}
    if component is not None:
        context["component"] = component
    if model_version is not None:
        context["model_version"] = model_version
    if report_id is not None:
        context["report_id"] = report_id
    if processing_status is not None:
        context["processing_status"] = processing_status

    return MLLoggerAdapter(logger, context)
