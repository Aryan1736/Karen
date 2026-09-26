"""
Karen's Ear — ML Pipeline Exception Hierarchy.

Small, typed exception classes for ML-specific failures.
Adheres to the architectural principle of resilience and graceful degradation:
failures are caught, categorized, and translated into diagnostic warnings
rather than crashing the host application.
"""


class MLBaseError(Exception):
    """Base exception for all Karen's Ear ML pipeline failures."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class MLConfigurationError(MLBaseError):
    """Raised when ML configuration is invalid, missing, or out of acceptable bounds."""
    pass


class MLInputError(MLBaseError):
    """Raised when an input emergency report violates pipeline constraints (e.g., text length, type)."""
    pass


class MLInferenceError(MLBaseError):
    """Raised when an internal ML model or rule-based component inference fails during execution."""
    pass


class MLModelError(MLBaseError):
    """Raised when model loading, weight resolution, or runtime device allocation fails."""
    pass


class MLSchemaValidationError(MLInferenceError):
    """Raised when an ML output payload fails validation against the canonical schema."""
    pass

