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

from unittest.mock import MagicMock, patch

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


# ==============================================================================
# Feature 10 Discovery & Concurrency Tests
# ==============================================================================


@pytest.fixture(autouse=True)
def clean_discovery_state():
    """Ensure discovery cache is reset before and after every test."""
    from backend.app.services.ml_adapter import reset_discovered_engine
    reset_discovered_engine()
    yield
    reset_discovered_engine()


def test_automatic_discovery_of_get_inference_engine():
    """Verifies adapter discovers and invokes Aryan's get_inference_engine() with correct args."""
    mock_engine = MagicMock()
    mock_engine.analyze.return_value = sample_valid_ml_dict("rep-disc-01")

    mock_pipeline = MagicMock()
    mock_pipeline.get_inference_engine.return_value = mock_engine

    with patch.dict(sys.modules, {"ml": MagicMock(), "ml.pipeline": mock_pipeline}):
        adapter = MLAdapter()
        result = adapter.analyze_report(
            text="Flash flood rising near Rasulgarh",
            report_id="rep-disc-01",
            location_hint={"raw_text": "Rasulgarh", "precision": "approximate"},
        )

        assert isinstance(result, MLPredictionOutput)
        assert result.report_id == "rep-disc-01"
        assert result.processing_status == ProcessingStatus.SUCCESS

        mock_engine.analyze.assert_called_once_with(
            report="Flash flood rising near Rasulgarh",
            report_id="rep-disc-01",
            location_hint={"raw_text": "Rasulgarh", "precision": "approximate"},
            include_embedding=True,
        )


def test_discovered_engine_reused_across_calls_and_instances():
    """Verifies that discovered engine is cached and reused rather than reconstructed."""
    mock_engine = MagicMock()
    mock_engine.analyze.return_value = sample_valid_ml_dict("rep-reuse-01")

    mock_pipeline = MagicMock()
    mock_pipeline.get_inference_engine.return_value = mock_engine

    with patch.dict(sys.modules, {"ml": MagicMock(), "ml.pipeline": mock_pipeline}):
        adapter1 = MLAdapter()
        adapter1.analyze_report(text="Report one", report_id="rep-reuse-01")

        adapter2 = MLAdapter()
        adapter2.analyze_report(text="Report two", report_id="rep-reuse-02")

        # get_inference_engine must be called only once
        assert mock_pipeline.get_inference_engine.call_count == 1
        assert mock_engine.analyze.call_count == 2


def test_process_level_lock_serializes_concurrent_calls():
    """Verifies that process-level lock serializes concurrent calls to the discovered InferenceEngine."""
    import threading
    import time

    concurrent_calls = 0
    max_concurrent_calls = 0
    tracker_lock = threading.Lock()

    def slow_analyze(*args, **kwargs):
        nonlocal concurrent_calls, max_concurrent_calls
        with tracker_lock:
            concurrent_calls += 1
            if concurrent_calls > max_concurrent_calls:
                max_concurrent_calls = concurrent_calls
        time.sleep(0.03)
        with tracker_lock:
            concurrent_calls -= 1
        return sample_valid_ml_dict(kwargs.get("report_id", "rep-lock"))

    mock_engine = MagicMock()
    mock_engine.analyze.side_effect = slow_analyze

    mock_pipeline = MagicMock()
    mock_pipeline.get_inference_engine.return_value = mock_engine

    with patch.dict(sys.modules, {"ml": MagicMock(), "ml.pipeline": mock_pipeline}):
        threads = []
        errors = []

        def worker(idx: int):
            try:
                ad = MLAdapter()
                res = ad.analyze_report(text=f"Concurrent text {idx}", report_id=f"rep-thread-{idx}")
                assert res.processing_status == ProcessingStatus.SUCCESS
            except Exception as e:
                errors.append(e)

        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert not errors
        assert mock_engine.analyze.call_count == 5
        # Under process-level lock, max concurrent calls inside analyze() must strictly be 1
        assert max_concurrent_calls == 1


def test_absence_of_ml_pipeline_produces_safe_fallback():
    """When ml.pipeline is missing/uninstalled, adapter returns canonical fallback without crashing."""
    with patch.dict(sys.modules, {"ml.pipeline": None}):
        with patch("importlib.import_module", side_effect=ModuleNotFoundError("No module named 'ml.pipeline'")):
            adapter = MLAdapter()
            result = adapter.analyze_report(text="Any emergency text", report_id="rep-noml-01")

            assert result.processing_status == ProcessingStatus.FAILED
            assert result.warnings == ["ML_ANALYZER_UNAVAILABLE"]
            assert result.incident_type.label is None


def test_get_inference_engine_exception_produces_safe_fallback():
    """When get_inference_engine raises an exception, adapter safely degrades to fallback."""
    mock_pipeline = MagicMock()
    mock_pipeline.get_inference_engine.side_effect = RuntimeError("Failed to load model weights")

    with patch.dict(sys.modules, {"ml": MagicMock(), "ml.pipeline": mock_pipeline}):
        adapter = MLAdapter()
        result = adapter.analyze_report(text="Any emergency text", report_id="rep-init-fail-01")

        assert result.processing_status == ProcessingStatus.FAILED
        assert result.warnings == ["ML_ANALYZER_UNAVAILABLE"]


def test_engine_analyze_exception_produces_safe_fallback():
    """When engine.analyze raises an exception (e.g. MLInputError), adapter safely degrades to fallback."""
    mock_engine = MagicMock()
    mock_engine.analyze.side_effect = ValueError("Corrupt text input tensor")

    mock_pipeline = MagicMock()
    mock_pipeline.get_inference_engine.return_value = mock_engine

    with patch.dict(sys.modules, {"ml": MagicMock(), "ml.pipeline": mock_pipeline}):
        adapter = MLAdapter()
        result = adapter.analyze_report(text="Emergency text", report_id="rep-analyze-fail-01")

        assert result.processing_status == ProcessingStatus.FAILED
        assert result.warnings == ["ML_ANALYSIS_FAILED"]


def test_exact_384_vector_embedding_passes():
    """Verifies that an exact 384-dimensional dense vector passes validation."""
    valid_payload = sample_valid_ml_dict("rep-emb-384")
    valid_payload["embedding"] = [0.05] * 384

    adapter = MLAdapter(analyzer=lambda t, r, h: valid_payload)
    result = adapter.analyze_report(text="Emergency text", report_id="rep-emb-384")

    assert result.processing_status == ProcessingStatus.SUCCESS
    assert result.embedding is not None
    assert len(result.embedding) == 384


def test_malformed_vector_embedding_fallback():
    """Verifies that an embedding vector with incorrect dimension fails validation and produces fallback."""
    bad_payload = sample_valid_ml_dict("rep-emb-bad")
    bad_payload["embedding"] = [0.05] * 128  # Invalid length (expected 384)

    adapter = MLAdapter(analyzer=lambda t, r, h: bad_payload)
    result = adapter.analyze_report(text="Emergency text", report_id="rep-emb-bad")

    assert result.processing_status == ProcessingStatus.FAILED
    assert result.warnings == ["ML_OUTPUT_INVALID"]


def test_explicit_null_embedding_fallback():
    """Verifies that explicit null embedding is rejected by validator and produces fallback."""
    null_emb_payload = sample_valid_ml_dict("rep-emb-null")
    null_emb_payload["embedding"] = None

    adapter = MLAdapter(analyzer=lambda t, r, h: null_emb_payload)
    result = adapter.analyze_report(text="Emergency text", report_id="rep-emb-null")

    assert result.processing_status == ProcessingStatus.FAILED
    assert result.warnings == ["ML_OUTPUT_INVALID"]


# ==============================================================================
# Caller Location Evidence Overlay Tests
# ==============================================================================


def test_caller_full_coordinate_hint_overlays_ml_null_coordinates():
    """When caller supplies verified coordinates, they overlay ML's null coordinates."""
    ml_output = sample_valid_ml_dict("rep-loc-01")
    ml_output["location"] = {
        "text": "Patia Market",
        "latitude": None,
        "longitude": None,
        "precision": "unknown",
        "confidence": 0.85,
    }

    adapter = MLAdapter(analyzer=lambda t, r, h: ml_output)
    result = adapter.analyze_report(
        text="Tree down on road",
        report_id="rep-loc-01",
        location_hint={
            "latitude": 20.3533,
            "longitude": 85.8266,
            "precision": "exact",
        },
    )

    assert result.location.latitude == 20.3533
    assert result.location.longitude == 85.8266
    assert result.location.precision == LocationPrecision.EXACT
    # ML extracted text retained because caller raw_text was absent
    assert result.location.text == "Patia Market"
    # ML extraction confidence preserved without inventing coordinate confidence
    assert result.location.confidence == 0.85


def test_caller_raw_text_accompanies_caller_coordinates():
    """When caller supplies both coordinates and raw_text, both are overlaid for coherence."""
    ml_output = sample_valid_ml_dict("rep-loc-02")
    ml_output["location"] = {
        "text": "Extracted General Area",
        "latitude": None,
        "longitude": None,
        "precision": "unknown",
        "confidence": 0.75,
    }

    adapter = MLAdapter(analyzer=lambda t, r, h: ml_output)
    result = adapter.analyze_report(
        text="Building collapse",
        report_id="rep-loc-02",
        location_hint={
            "raw_text": "Block C, Metro Tower",
            "latitude": 20.2961,
            "longitude": 85.8245,
            "precision": "exact",
        },
    )

    assert result.location.latitude == 20.2961
    assert result.location.longitude == 85.8245
    assert result.location.precision == LocationPrecision.EXACT
    assert result.location.text == "Block C, Metro Tower"
    assert result.location.confidence == 0.75


def test_partial_coordinate_hint_never_creates_coordinate_pair():
    """Partial coordinates (lat without lon or lon without lat) must never overlay coordinates."""
    ml_output = sample_valid_ml_dict("rep-loc-partial")
    ml_output["location"] = {
        "text": "Rasulgarh",
        "latitude": None,
        "longitude": None,
        "precision": "unknown",
        "confidence": 0.80,
    }

    adapter = MLAdapter(analyzer=lambda t, r, h: ml_output)

    # Latitude only
    res1 = adapter.analyze_report(
        text="Flood water",
        report_id="rep-loc-part-1",
        location_hint={"latitude": 20.2961, "longitude": None, "raw_text": "Flyover"},
    )
    assert res1.location.latitude is None
    assert res1.location.longitude is None
    assert res1.location.text == "Rasulgarh"

    # Longitude only
    res2 = adapter.analyze_report(
        text="Flood water",
        report_id="rep-loc-part-2",
        location_hint={"latitude": None, "longitude": 85.8245, "raw_text": "Flyover"},
    )
    assert res2.location.latitude is None
    assert res2.location.longitude is None
    assert res2.location.text == "Rasulgarh"


def test_ml_text_retained_when_caller_coordinates_exist_without_raw_text():
    """When caller supplies coordinates but raw_text is None, ML-extracted text is strictly preserved."""
    ml_output = sample_valid_ml_dict("rep-loc-coords-only")
    ml_output["location"] = {
        "text": "Kalinga Hospital Underpass",
        "latitude": None,
        "longitude": None,
        "precision": "unknown",
        "confidence": 0.90,
    }

    adapter = MLAdapter(analyzer=lambda t, r, h: ml_output)
    result = adapter.analyze_report(
        text="Stranded ambulances",
        report_id="rep-loc-coords-only",
        location_hint={"latitude": 20.3100, "longitude": 85.8150, "raw_text": None},
    )

    assert result.location.text == "Kalinga Hospital Underpass"
    assert result.location.latitude == 20.3100
    assert result.location.longitude == 85.8150


def test_caller_raw_text_fills_missing_ml_text():
    """When ML extracts null location text, caller raw_text is used to populate location.text."""
    ml_output = sample_valid_ml_dict("rep-loc-fill-text")
    ml_output["location"] = {
        "text": None,
        "latitude": None,
        "longitude": None,
        "precision": "unknown",
        "confidence": None,
    }

    adapter = MLAdapter(analyzer=lambda t, r, h: ml_output)
    result = adapter.analyze_report(
        text="Power lines sparking",
        report_id="rep-loc-fill-text",
        location_hint={"raw_text": "Station Road Near Post Office", "precision": "approximate"},
    )

    assert result.location.text == "Station Road Near Post Office"
    assert result.location.latitude is None
    assert result.location.longitude is None
    assert result.location.precision == LocationPrecision.APPROXIMATE


def test_no_overall_confidence_invented():
    """Verifies adapter does not invent overall_confidence when omitted by ML payload."""
    payload = sample_valid_ml_dict("rep-no-overall")
    del payload["overall_confidence"]  # Feature 10 canonical payload omits this field

    adapter = MLAdapter(analyzer=lambda t, r, h: payload)
    result = adapter.analyze_report(text="Fire report", report_id="rep-no-overall")

    assert result.overall_confidence is None
    assert result.processing_status == ProcessingStatus.SUCCESS


def test_privacy_preservation_no_sensitive_report_or_exception_leak():
    """Raw exceptions and citizen phone numbers / names must never leak into warnings or logs."""
    def leak_prone_analyzer(text, report_id, hint):
        raise RuntimeError("CRITICAL DB ACCESS VIOLATION: db://admin:hunter2@10.0.0.1/production")

    adapter = MLAdapter(analyzer=leak_prone_analyzer)
    result = adapter.analyze_report(
        text="Victim Jane Doe trapped, call her at +1-555-867-5309 immediately",
        report_id="rep-privacy-01",
    )

    assert result.processing_status == ProcessingStatus.FAILED
    assert result.warnings == ["ML_ANALYSIS_FAILED"]
    for warn in result.warnings:
        assert "hunter2" not in warn
        assert "10.0.0.1" not in warn
        assert "Jane Doe" not in warn
        assert "555" not in warn
        assert "867" not in warn

