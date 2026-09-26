"""
Karen's Ear — Application Exceptions and Global Exception Handlers
Ensures all errors strictly follow the canonical response envelope.
"""
import logging
from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .envelope import error_response

logger = logging.getLogger("karen.backend")


class AppException(Exception):
    """Base application exception with canonical envelope fields."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class DatabaseUnavailableException(AppException):
    """Raised when PostgreSQL connection or query fails."""

    def __init__(
        self,
        message: str = "Database service is unavailable",
        details: Any = None,
    ):
        super().__init__(
            code="DATABASE_UNAVAILABLE",
            message=message,
            status_code=503,
            details=details,
        )


class ResourceNotFoundException(AppException):
    """Raised when an incident, report, or entity is not found."""

    def __init__(
        self,
        message: str = "Requested resource not found",
        details: Any = None,
    ):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=404,
            details=details,
        )


class ValidationException(AppException):
    """Raised when custom business validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Any = None,
    ):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details=details,
        )


class BadRequestException(AppException):
    """Raised for malformed requests."""

    def __init__(
        self,
        message: str = "Bad request",
        details: Any = None,
    ):
        super().__init__(
            code="BAD_REQUEST",
            message=message,
            status_code=400,
            details=details,
        )


def _format_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format FastAPI / Pydantic validation errors to match contract specifications."""
    formatted = []
    for err in errors:
        loc = err.get("loc", ())
        # Filter out 'body' or 'query' prefix if present for cleaner field names
        field_parts = [str(part) for part in loc if part not in ("body", "query", "path")]
        field_name = ".".join(field_parts) if field_parts else "body"
        msg = err.get("msg", "Validation error")
        formatted.append({
            "field": field_name,
            "issue": msg,
        })
    return formatted


def setup_exception_handlers(app: FastAPI) -> None:
    """Register canonical error envelope handlers for all exceptions."""

    @app.exception_handler(AppException)
    async def handle_app_exception(_request: Request, exc: AppException):
        return error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError):
        details = _format_validation_errors(exc.errors())
        return error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=422,
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_request: Request, exc: StarletteHTTPException):
        status_code = exc.status_code
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            422: "UNPROCESSABLE_ENTITY",
            500: "INTERNAL_SERVER_ERROR",
            503: "SERVICE_UNAVAILABLE",
        }
        code = code_map.get(status_code, f"HTTP_{status_code}")
        message = str(exc.detail) if exc.detail else "HTTP error"
        return error_response(
            code=code,
            message=message,
            status_code=status_code,
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(_request: Request, exc: Exception):
        # Log error securely without exposing secrets to client
        logger.exception("Unhandled server exception: %s", exc)
        return error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred.",
            status_code=500,
        )
