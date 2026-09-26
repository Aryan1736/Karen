"""
Karen's Ear — Pipeline Orchestrator Subpackage.

Feature 10 — Step 5 of the ML pipeline (architecture/ml-pipeline.md).
Coordinates execution across preprocessing, classification, urgency, extraction,
response mapping, and embedding generation; packaging the final result strictly
validating against ml/schemas/incident_output.json.
"""

from ml.pipeline.inference_engine import (
    InferenceEngine,
    get_inference_engine,
    inference_engine,
)
from ml.pipeline.schema_validator import (
    SchemaValidator,
    get_schema_validator,
    validate_incident_output,
)

__all__: list[str] = [
    "InferenceEngine",
    "inference_engine",
    "get_inference_engine",
    "SchemaValidator",
    "get_schema_validator",
    "validate_incident_output",
]
