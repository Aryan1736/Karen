"""
Karen's Ear — Canonical API Response Envelope
Adheres strictly to docs/api-contract.md and gemini.md Section 6.6.
"""
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
import uuid
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")

# Context variable to track the active request ID across async tasks
request_id_ctx: ContextVar[str] = ContextVar("request_id_ctx", default="")


def format_utc_now() -> str:
    """Format current time strictly in ISO-8601 UTC format (YYYY-MM-DDTHH:MM:SSZ)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_request_id() -> str:
    """Generate canonical request ID prefixed with 'req-'."""
    return f"req-{uuid.uuid4()}"


def get_request_id() -> str:
    """Get active request ID from context or generate a new one."""
    req_id = request_id_ctx.get()
    if not req_id:
        req_id = generate_request_id()
        request_id_ctx.set(req_id)
    return req_id


def set_request_id(req_id: str) -> None:
    """Set active request ID in context."""
    request_id_ctx.set(req_id)


class ErrorPayload(BaseModel):
    code: str = Field(..., description="Standardized error code string")
    message: str = Field(..., description="Human-readable error explanation")
    details: Any | None = Field(default=None, description="Optional diagnostic details or field issues")


class ResponseEnvelope(BaseModel, Generic[T]):
    success: bool = Field(..., description="True if request succeeded, false otherwise")
    data: T | None = Field(default=None, description="Response payload object or null")
    error: ErrorPayload | None = Field(default=None, description="Error details object or null")
    request_id: str = Field(..., description="Tracing identifier for request")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp")


def create_envelope(
    success: bool,
    data: Any = None,
    error: dict[str, Any] | None = None,
    request_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build the dictionary matching the frozen canonical API response envelope."""
    return {
        "success": success,
        "data": data,
        "error": error,
        "request_id": request_id or get_request_id(),
        "timestamp": timestamp or format_utc_now(),
    }


def success_response(
    data: Any = None,
    status_code: int = 200,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Return canonical success JSONResponse with X-Request-Id header."""
    req_id = request_id or get_request_id()
    resp_headers = {"X-Request-Id": req_id}
    if headers:
        resp_headers.update(headers)

    content = create_envelope(
        success=True,
        data=data,
        error=None,
        request_id=req_id,
    )
    return JSONResponse(
        content=content,
        status_code=status_code,
        headers=resp_headers,
    )


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
    details: Any = None,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Return canonical error JSONResponse with X-Request-Id header."""
    req_id = request_id or get_request_id()
    resp_headers = {"X-Request-Id": req_id}
    if headers:
        resp_headers.update(headers)

    error_payload: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error_payload["details"] = details

    content = create_envelope(
        success=False,
        data=None,
        error=error_payload,
        request_id=req_id,
    )
    return JSONResponse(
        content=content,
        status_code=status_code,
        headers=resp_headers,
    )
