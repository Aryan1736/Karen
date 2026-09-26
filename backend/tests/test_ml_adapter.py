"""
Karen's Ear — Machine Learning Pipeline Adapter Tests
Verifies dependency injection, schema validation, safe fallback generation,
and privacy preservation (no raw exception or citizen report leakage).
"""
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest

from backend.app.schemas.common import (
    IncidentType,
    LocationPrecision,
    ProcessingStatus,
    ResponseCapability,
    UrgencyLevel,
)
from backend.app.schemas.ml import MLPredictionOutput
from backend.app.schemas.report import LocationHint
from backend.app.services.ml_adapter import MLAdapter


def sample_valid_ml_dict(report_id: str = "rep-101") -> dict:
    """Returns a canonical valid ML analyzer output dictionary."""
    return {
        "report_id": report_id,
        "model_version": "test-v1.0",
        "incident_type": {
            "label": "FLOOD_FLASH_FLOOD",
            "confidence": 0.95,
        },
        "urgency": {
            "label": "CRITICAL",
            "confidence": 0.90,
        },
        "location": {
            "text": "Patia Square",
            "latitude": 20.3533,
            "longitude": 85.8266,
            "precision": "approximate",
            "confidence": 0.85,
        },
        "people_at_risk": {
            "count": 3,
            "confidence": 0.80,
        },
        "required_response": [
            {"type": "SEARCH_AND_RESCUE", "confidence": 0.92},
            {"type": "MEDICAL_EMS", "confidence": 0.88},
        ],
        "entities": [
            {"text": "Patia Square", "type": "LOCATION", "confidence": 0.88},
        ],
        "embedding_reference": None,
        "overall_confidence": 0.87,
        "processing_status": "SUCCESS",
        "warnings": [],
    }


def test_canonical_successful_injected_analyzer():
    """Verify that an injected analyzer returning a valid dict produces a validated MLPredictionOutput."""
    called_with = []

    def mock_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> dict:
        called_with.append((text, report_id, location_hint))
        return sample_valid_ml_dict(report_id)

    adapter = MLAdapter(analyzer=mock_analyzer)
    result = adapter.analyze_report(
        text="Severe waterlogging near Patia Square, two cars submerged.",
        report_id="rep-101",
        location_hint={"raw_text": "Patia Square", "precision": "approximate"},
    )

    assert len(called_with) == 1
    assert called_with[0][1] == "rep-101"
    assert isinstance(result, MLPredictionOutput)
    assert result.report_id == "rep-101"
    assert result.processing_status == ProcessingStatus.SUCCESS
    assert result.incident_type.label == IncidentType.FLOOD_FLASH_FLOOD
    assert result.urgency.label == UrgencyLevel.CRITICAL
    assert result.people_at_risk.count == 3
    assert len(result.required_response) == 2
    assert result.required_response[0].type == ResponseCapability.SEARCH_AND_RESCUE


def test_analyzer_missing_fallback():
    """When no analyzer is provided and discovery finds none, returns safe canonical fallback."""
    adapter = MLAdapter(analyzer=None)
    # Ensure discovery probe fails cleanly
    adapter._discovery_attempted = True

    result = adapter.analyze_report(
        text="Any distress text that must not be leaked",
        report_id="rep-fallback-01",
    )

    assert isinstance(result, MLPredictionOutput)
    assert result.report_id == "rep-fallback-01"
    assert result.processing_status == ProcessingStatus.FAILED
    assert result.incident_type.label is None
    assert result.urgency.label is None
    assert result.people_at_risk.count is None
    assert result.required_response == []
    assert result.entities == []
    assert result.embedding is None
    assert result.warnings == ["ML_ANALYZER_UNAVAILABLE"]


def test_analyzer_exception_fallback():
    """When the analyzer raises an unexpected exception, returns canonical fallback with safe warning code."""
    def crashing_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> dict:
        raise RuntimeError("Secret internal exception with sensitive paths /home/secret/db")

    adapter = MLAdapter(analyzer=crashing_analyzer)
    result = adapter.analyze_report(
        text="Emergency text with citizen info John Doe +919876543210",
        report_id="rep-crash-01",
    )

    assert result.processing_status == ProcessingStatus.FAILED
    assert result.warnings == ["ML_ANALYSIS_FAILED"]
    # Verify no raw exception or citizen details appear in visible warnings
    for warn in result.warnings:
        assert "Secret" not in warn
        assert "sensitive" not in warn
        assert "John Doe" not in warn
        assert "9876543210" not in warn


def test_malformed_analyzer_output_fallback():
    """When analyzer returns invalid schema dictionary, returns canonical fallback with ML_OUTPUT_INVALID."""
    def malformed_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> dict:
        return {
            "report_id": report_id,
            # Missing required fields like incident_type, urgency, etc.
            "corrupted_key": 12345,
        }

    adapter = MLAdapter(analyzer=malformed_analyzer)
    result = adapter.analyze_report(
        text="Emergency text",
        report_id="rep-malformed-01",
    )

    assert result.processing_status == ProcessingStatus.FAILED
    assert result.warnings == ["ML_OUTPUT_INVALID"]


def test_non_dict_analyzer_output_fallback():
    """When analyzer returns a non-dict object, returns ML_OUTPUT_INVALID."""
    def string_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> Any:
        return "Not a dictionary"

    adapter = MLAdapter(analyzer=string_analyzer)  # type: ignore
    result = adapter.analyze_report(text="Emergency text", report_id="rep-str-01")

    assert result.processing_status == ProcessingStatus.FAILED
    assert result.warnings == ["ML_OUTPUT_INVALID"]


def test_fallback_location_hint_preservation():
    """Caller-provided location evidence must be safely preserved in fallback without inventing coordinates."""
    adapter = MLAdapter(analyzer=None)
    adapter._discovery_attempted = True

    # Test with dictionary location hint
    hint_dict = {
        "raw_text": "Near Rasulgarh flyover pillar 12",
        "latitude": 20.2961,
        "longitude": 85.8245,
        "precision": "approximate",
    }

    result = adapter.analyze_report(
        text="Water rising rapidly",
        report_id="rep-hint-01",
        location_hint=hint_dict,
    )

    assert result.location.text == "Near Rasulgarh flyover pillar 12"
    assert result.location.latitude == 20.2961
    assert result.location.longitude == 85.8245
    assert result.location.precision == LocationPrecision.APPROXIMATE
    # Confidence remains strictly None on failure (no hallucinated confidence)
    assert result.location.confidence is None

    # Test with LocationHint Pydantic object
    hint_obj = LocationHint(
        raw_text="Near Apollo hospital",
        latitude=None,
        longitude=None,
        precision=LocationPrecision.UNKNOWN,
    )
    result_obj = adapter.analyze_report(
        text="Oxygen cylinder required",
        report_id="rep-hint-02",
        location_hint=hint_obj,
    )
    assert result_obj.location.text == "Near Apollo hospital"
    assert result_obj.location.latitude is None
    assert result_obj.location.precision == LocationPrecision.UNKNOWN
    assert result_obj.location.confidence is None
