"""
Karen's Ear — Canonical ML Output Schema Validator.

Enforces strict compliance with the frozen ML output contract defined in
ml/schemas/incident_output.json, docs/api-contract.md, and docs/data-schema.md.

Guarantees:
1. Strict schema compliance: Any malformed or unauthorized fields are rejected.
2. Clear diagnostics: Detailed error information including failing path, validator, and rule.
3. Fast execution: Pre-compiles JSON schema validator on initialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError

from ml.exceptions import MLSchemaValidationError

# Default path to canonical JSON schema
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "incident_output.json"


class SchemaValidator:
    """
    Validates ML pipeline output payloads against the frozen canonical JSON schema.
    Serves as the final validation gate before output is returned to callers.
    """

    def __init__(self, schema_path: Path | str | None = None) -> None:
        self.schema_path = Path(schema_path or DEFAULT_SCHEMA_PATH)
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Canonical schema not found at: {self.schema_path}")

        try:
            self._raw_schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise MLSchemaValidationError(
                f"Failed to read or parse canonical schema file: {exc}",
                details={"schema_path": str(self.schema_path)},
            ) from exc

        # Create Draft7Validator for efficient reuse
        cls = jsonschema.validators.validator_for(self._raw_schema)
        cls.check_schema(self._raw_schema)
        self._validator = cls(self._raw_schema)

    @property
    def schema(self) -> dict[str, Any]:
        """Returns a copy of the canonical JSON schema dictionary."""
        return dict(self._raw_schema)

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Validates an ML analysis payload against the frozen schema.

        Args:
            payload: Output dictionary from InferenceEngine.

        Returns:
            The identical payload if valid.

        Raises:
            MLSchemaValidationError: If payload violates any schema constraint.
        """
        if not isinstance(payload, dict):
            raise MLSchemaValidationError(
                f"Payload must be a dictionary, got {type(payload).__name__}",
                details={"type": type(payload).__name__},
            )

        errors = list(self._validator.iter_errors(payload))
        if errors:
            first_err: ValidationError = errors[0]
            field_path = ".".join(str(p) for p in first_err.absolute_path) or "(root)"
            details = {
                "field": field_path,
                "validator": first_err.validator,
                "validator_value": str(first_err.validator_value),
                "error_message": first_err.message,
                "all_errors": [
                    {
                        "path": ".".join(str(p) for p in err.absolute_path) or "(root)",
                        "message": err.message,
                        "validator": err.validator,
                    }
                    for err in errors
                ],
            }
            raise MLSchemaValidationError(
                f"ML output payload failed schema validation at '{field_path}': {first_err.message}",
                details=details,
            )

        return payload

    def is_valid(self, payload: dict[str, Any]) -> bool:
        """Returns True if the payload conforms to the canonical schema, False otherwise."""
        if not isinstance(payload, dict):
            return False
        return self._validator.is_valid(payload)

    def get_validation_errors(self, payload: dict[str, Any]) -> list[str]:
        """
        Returns a list of human-readable error messages without raising an exception.
        Returns an empty list if payload is valid.
        """
        if not isinstance(payload, dict):
            return [f"Payload must be a dictionary, got {type(payload).__name__}"]

        return [
            f"'{'.'.join(str(p) for p in err.absolute_path) or '(root)'}': {err.message}"
            for err in self._validator.iter_errors(payload)
        ]


# Singleton validator instance
_default_validator: SchemaValidator | None = None


def get_schema_validator() -> SchemaValidator:
    """Returns the process-level singleton SchemaValidator instance."""
    global _default_validator
    if _default_validator is None:
        _default_validator = SchemaValidator()
    return _default_validator


def validate_incident_output(
    payload: dict[str, Any],
    schema_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Public functional convenience interface for validating an incident output payload.
    """
    if schema_path is not None:
        validator = SchemaValidator(schema_path=schema_path)
    else:
        validator = get_schema_validator()
    return validator.validate(payload)
