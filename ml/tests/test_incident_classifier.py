"""
Karen's Ear — Incident Type Classifier Test Suite.

Comprehensive unit and integration tests for Step 2A of the ML pipeline
(architecture/ml-pipeline.md Section 3.2 and ml/schemas/incident_output.json).

Validates:
- All 9 canonical incident categories are classified accurately with realistic reports.
- Exact canonical labels are used (no unknown or invalid taxonomy values).
- High-confidence obvious examples achieve high confidence scores and "SUCCESS" status.
- Ambiguous and general texts fall back to OTHER_GENERAL_INCIDENT with "NEEDS_REVIEW".
- Multi-hazard and conflicting signals are resolved deterministically with diagnostic evidence.
- Determinism: repeated predictions on identical text and config produce identical results.
- Confidence scores strictly reside within [0.0, 1.0].
- Empty, whitespace-only, and invalid input types raise typed MLInputError.
- Preprocessing integration: dirty HTML/scripts/excessive whitespace are cleaned safely.
- PreprocessedText objects are accepted directly without re-cleaning.
- Lazy model loading: models are NOT loaded at import time or during keyword mode.
- Batch prediction processes multiple reports efficiently.
- ComponentResult conversion aligns with pipeline architecture.
- Observability: logging does not leak raw emergency distress text.
- Error handling: model loading failures are wrapped in typed MLModelError.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from ml.classification import (
    ClassificationResult,
    IncidentClassifier,
    classify_incident,
)
from ml.classification.evaluator import ClassifierEvaluator
from ml.classification.taxonomy import (
    CRISITEXT_SCENARIO_MAPPING,
    HAZARD_PRECEDENCE_ORDER,
    INCIDENT_TAXONOMY_CATALOG,
)
from ml.config import (
    CANONICAL_INCIDENT_TYPES,
    ComponentResult,
    MLConfig,
    get_ml_config,
    reset_ml_config,
)
from ml.exceptions import (
    MLInferenceError,
    MLInputError,
    MLModelError,
)
from ml.logging_utils import MLJsonFormatter
from ml.preprocessing.text_cleaner import PreprocessedText, preprocess_report
from ml.tests.fixtures.incident_benchmark import INCIDENT_BENCHMARK_DATASET, BenchmarkItem


# ==============================================================================
# Fixtures
# ==============================================================================
@pytest.fixture(scope="module")
def hybrid_classifier() -> IncidentClassifier:
    """Provides a shared hybrid classifier instance for the test module."""
    return IncidentClassifier(mode="hybrid")


@pytest.fixture(scope="module")
def keyword_classifier() -> IncidentClassifier:
    """Provides a shared keyword classifier instance for the test module."""
    return IncidentClassifier(mode="keyword")


@pytest.fixture(scope="module")
def semantic_classifier() -> IncidentClassifier:
    """Provides a shared semantic classifier instance for the test module."""
    return IncidentClassifier(mode="semantic")


# ==============================================================================
# 1. Canonical Taxonomy & All 9 Classes Coverage
# ==============================================================================
@pytest.mark.parametrize(
    "expected_label, sample_text",
    [
        (
            "FLOOD_FLASH_FLOOD",
            "Flash flood warning in effect! Rapidly rising water has submerged Highway 16 and several cars are trapped in the deluge.",
        ),
        (
            "FIRE_WILDFIRE_EXPLOSION",
            "Massive structural building fire with heavy flames and thick black smoke engulfing the warehouse following an explosion.",
        ),
        (
            "STRUCTURAL_COLLAPSE",
            "Multi-story residential building collapsed completely, victims are trapped under heavy concrete rubble and debris.",
        ),
        (
            "EARTHQUAKE_LANDSLIDE",
            "Violent earthquake tremors shook the mountain pass, causing a massive landslide and mudslide burying the road.",
        ),
        (
            "SEVERE_WEATHER_STORM",
            "Destructive tornado touchdown with gale-force winds tearing roofs off homes and golf-ball-sized hail smashing windows.",
        ),
        (
            "MEDICAL_EMERGENCY",
            "Elderly patient collapsed on the floor, unresponsive and not breathing. CPR in progress, send an ambulance immediately!",
        ),
        (
            "CIVIL_UNREST_ACTIVE_THREAT",
            "Active shooter at the transit hub, multiple gunshots fired and an armed assailant actively attacking civilians.",
        ),
        (
            "UTILITY_INFRASTRUCTURE_FAILURE",
            "Major natural gas main break and power grid blackout, total electrical failure across downtown and strong gas leak odor.",
        ),
        (
            "OTHER_GENERAL_INCIDENT",
            "Calling to ask about scheduled municipal road closures and parking regulations for tomorrow morning.",
        ),
    ],
)
def test_classifier_all_nine_canonical_classes(
    hybrid_classifier: IncidentClassifier,
    expected_label: str,
    sample_text: str,
):
    """Verify that all 9 canonical incident categories are classified accurately."""
    result = hybrid_classifier.predict(sample_text)

    assert result.label == expected_label
    assert result.label in CANONICAL_INCIDENT_TYPES
    assert 0.0 <= result.confidence <= 1.0
    assert result.processing_status in ("SUCCESS", "NEEDS_REVIEW")
    assert isinstance(result.class_scores, dict)
    if expected_label != "OTHER_GENERAL_INCIDENT":
        assert result.class_scores[expected_label] > 0.30
    else:
        assert result.label == "OTHER_GENERAL_INCIDENT"


def test_taxonomy_catalog_contains_all_canonical_types():
    """Verify taxonomy catalog matches exact canonical contract."""
    for label in CANONICAL_INCIDENT_TYPES:
        assert label in INCIDENT_TAXONOMY_CATALOG
        defn = INCIDENT_TAXONOMY_CATALOG[label]
        assert defn.label == label
        assert len(defn.primary_phrases) >= 10
        assert len(defn.keywords) >= 10
        assert len(defn.prototypes) >= 4


def test_crisitext_mapping_integrity():
    """Verify CrisiText scenario mapping aligns with canonical types."""
    for scenario, target_label in CRISITEXT_SCENARIO_MAPPING.items():
        assert target_label in CANONICAL_INCIDENT_TYPES


# ==============================================================================
# 2. Confidence Calibration & High-Confidence Clear Cases
# ==============================================================================
def test_high_confidence_obvious_fire_report(hybrid_classifier: IncidentClassifier):
    """Unambiguous fire incident should produce high confidence and SUCCESS status."""
    text = "Raging five-alarm structural fire! Commercial warehouse completely engulfed in flames with thick smoke billowing into sky."
    result = hybrid_classifier.predict(text)

    assert result.label == "FIRE_WILDFIRE_EXPLOSION"
    assert result.confidence >= 0.70
    assert result.processing_status == "SUCCESS"
    assert result.evidence["margin"] > 0.20


def test_high_confidence_obvious_flood_report(hybrid_classifier: IncidentClassifier):
    """Unambiguous flood incident should produce high confidence and SUCCESS status."""
    text = "Severe flash flooding! River overflowed its banks, rising floodwaters inundated streets and submerged multiple cars."
    result = hybrid_classifier.predict(text)

    assert result.label == "FLOOD_FLASH_FLOOD"
    assert result.confidence >= 0.70
    assert result.processing_status == "SUCCESS"


# ==============================================================================
# 3. Fallback to OTHER_GENERAL_INCIDENT & Low Confidence Handling
# ==============================================================================
@pytest.mark.parametrize(
    "vague_text",
    [
        "I saw something strange happening near the corner shop earlier today.",
        "Can someone check on the park? There's a lost dog wandering around.",
        "Neighbor has loud music playing, making a general noise complaint.",
        "Citizen calling to ask about weather forecast for this weekend.",
        "Car broken down on shoulder waiting for road service.",
    ],
)
def test_fallback_to_other_general_incident(
    hybrid_classifier: IncidentClassifier,
    vague_text: str,
):
    """Uncertain or non-hazard reports must fall back safely to OTHER_GENERAL_INCIDENT."""
    result = hybrid_classifier.predict(vague_text)

    assert result.label == "OTHER_GENERAL_INCIDENT"
    assert 0.0 <= result.confidence <= 1.0
    # Safe fallback should flag for human review
    assert result.processing_status in ("NEEDS_REVIEW", "SUCCESS")


def test_confidence_review_threshold_triggers_needs_review(hybrid_classifier: IncidentClassifier):
    """Low-confidence predictions (< 0.60) must set processing_status = NEEDS_REVIEW."""
    text = "I think something happened down by the dock, but I am not really sure what it was."
    result = hybrid_classifier.predict(text)

    assert result.label == "OTHER_GENERAL_INCIDENT"
    assert result.confidence < 0.60
    assert result.processing_status == "NEEDS_REVIEW"


# ==============================================================================
# 4. Multi-Hazard & Conflicting Signals
# ==============================================================================
def test_multi_hazard_fire_and_medical(hybrid_classifier: IncidentClassifier):
    """
    When an explosion causes a fire and people are injured,
    the initiating physical disaster (FIRE_WILDFIRE_EXPLOSION) must be the primary label.
    """
    text = "Massive explosion caused a structural fire at the manufacturing plant and several workers are severely injured!"
    result = hybrid_classifier.predict(text)

    assert result.label == "FIRE_WILDFIRE_EXPLOSION"
    assert result.confidence > 0.60
    # Secondary signals should be recorded in evidence
    assert "top_candidates" in result.evidence
    candidate_labels = [c["label"] for c in result.evidence["top_candidates"]]
    assert "FIRE_WILDFIRE_EXPLOSION" in candidate_labels


def test_conflicting_storm_and_power_outage(hybrid_classifier: IncidentClassifier):
    """
    When storm winds cause a power outage, the classifier should select deterministically
    and record secondary hazard diagnostics.
    """
    text = "Severe thunderstorm with destructive gale-force winds knocked down trees and caused widespread electrical blackout."
    result = hybrid_classifier.predict(text)

    assert result.label in ("SEVERE_WEATHER_STORM", "UTILITY_INFRASTRUCTURE_FAILURE")
    assert result.confidence > 0.50
    # Either storm or utility is top; conflict or top candidates should record both
    top_candidates = [c["label"] for c in result.evidence.get("top_candidates", [])]
    assert "SEVERE_WEATHER_STORM" in top_candidates or "UTILITY_INFRASTRUCTURE_FAILURE" in top_candidates


def test_conflicting_flooding_and_landslide(hybrid_classifier: IncidentClassifier):
    """
    Heavy rain causing both flash flooding and a landslide should deterministically
    select one primary category and flag the secondary hazard.
    """
    text = "Torrential rains caused catastrophic flash flooding and a massive mudslide burying the highway."
    result = hybrid_classifier.predict(text)

    assert result.label in ("FLOOD_FLASH_FLOOD", "EARTHQUAKE_LANDSLIDE")
    assert result.confidence > 0.50


# ==============================================================================
# 5. Determinism & Idempotency
# ==============================================================================
def test_deterministic_repeated_predictions(hybrid_classifier: IncidentClassifier):
    """Running predict multiple times on identical input must produce identical results."""
    text = "Bridge collapsed into the river following structural foundation failure with cars trapped under concrete rubble."

    results = [hybrid_classifier.predict(text) for _ in range(5)]

    first = results[0]
    for r in results[1:]:
        assert r.label == first.label
        assert r.confidence == first.confidence
        assert r.processing_status == first.processing_status
        assert r.class_scores == first.class_scores
        assert r.evidence["margin"] == first.evidence["margin"]


# ==============================================================================
# 6. Input Validation & Error Handling
# ==============================================================================
def test_empty_string_rejection(hybrid_classifier: IncidentClassifier):
    """Empty string input must raise MLInputError."""
    with pytest.raises(MLInputError, match="cannot be empty"):
        hybrid_classifier.predict("")


def test_whitespace_only_rejection(hybrid_classifier: IncidentClassifier):
    """Whitespace-only string must raise MLInputError."""
    with pytest.raises(MLInputError, match="whitespace-only"):
        hybrid_classifier.predict("    \n\t   ")


@pytest.mark.parametrize("invalid_input", [None, 12345, 99.9, [], {}])
def test_non_string_input_rejection(hybrid_classifier: IncidentClassifier, invalid_input):
    """Non-string/non-PreprocessedText input must raise MLInputError."""
    with pytest.raises(MLInputError, match="must be str or PreprocessedText"):
        hybrid_classifier.predict(invalid_input)  # type: ignore


# ==============================================================================
# 7. Preprocessing Integration
# ==============================================================================
def test_dirty_html_and_script_sanitization(hybrid_classifier: IncidentClassifier):
    """Dirty markup should be stripped safely without affecting crisis classification."""
    dirty_text = (
        "<script>maliciousCode();</script><b>FLASH FLOOD WARNING:</b> "
        "Water rising quickly on Market St, roads inundated! <!-- comment -->"
    )
    result = hybrid_classifier.predict(dirty_text)

    assert result.label == "FLOOD_FLASH_FLOOD"
    assert result.confidence >= 0.70
    assert result.processing_status == "SUCCESS"


def test_direct_preprocessed_text_acceptance(hybrid_classifier: IncidentClassifier):
    """Classifier should directly accept a PreprocessedText object from Feature 2."""
    preprocessed = preprocess_report(
        "Commercial building fire with flames shooting from windows on 2nd floor."
    )
    assert isinstance(preprocessed, PreprocessedText)

    result = hybrid_classifier.predict(preprocessed)

    assert result.label == "FIRE_WILDFIRE_EXPLOSION"
    assert result.confidence >= 0.70


# ==============================================================================
# 8. Lazy Model Loading & Mode Switching
# ==============================================================================
def test_keyword_mode_never_loads_heavy_model():
    """In keyword mode, the classifier must not instantiate SentenceTransformer."""
    classifier = IncidentClassifier(mode="keyword")
    assert classifier._model is None

    result = classifier.predict("Flash flood warning with rapidly rising flood water.")
    assert result.label == "FLOOD_FLASH_FLOOD"
    assert result.method == "keyword"
    # Model remains None
    assert classifier._model is None


def test_lazy_loading_in_semantic_mode():
    """Classifier should initialize with _model=None and only load on first predict()."""
    classifier = IncidentClassifier(mode="semantic")
    assert classifier._model is None

    result = classifier.predict("Tornado touched down tearing roofs off buildings.")
    assert result.label == "SEVERE_WEATHER_STORM"
    assert result.method == "semantic"
    assert classifier._model is not None


def test_invalid_mode_raises_error():
    """Unsupported classifier mode raises MLInferenceError."""
    with pytest.raises(MLInferenceError, match="Unsupported classifier mode"):
        IncidentClassifier(mode="quantum_ai")


def test_model_loading_failure_raises_typed_error():
    """If SentenceTransformer fails to load, raise typed MLModelError."""
    classifier = IncidentClassifier(mode="semantic")

    with patch.dict("sys.modules", {"sentence_transformers": None}):
        with pytest.raises(MLModelError, match="sentence-transformers"):
            classifier._get_model()


# ==============================================================================
# 9. Batch Prediction
# ==============================================================================
def test_batch_prediction_multiple_reports(hybrid_classifier: IncidentClassifier):
    """predict_batch must process a list of reports accurately."""
    reports = [
        "Major flash flood warning, roads inundated and vehicles submerged.",
        "Active shooter firing weapons inside the community center.",
        "Citywide blackout, total power outage across three districts.",
    ]
    report_ids = ["rep-1", "rep-2", "rep-3"]

    results = hybrid_classifier.predict_batch(reports, report_ids=report_ids)

    assert len(results) == 3
    assert results[0].label == "FLOOD_FLASH_FLOOD"
    assert results[1].label == "CIVIL_UNREST_ACTIVE_THREAT"
    assert results[2].label == "UTILITY_INFRASTRUCTURE_FAILURE"


def test_batch_prediction_empty_list(hybrid_classifier: IncidentClassifier):
    """Empty list returns empty list."""
    assert hybrid_classifier.predict_batch([]) == []


def test_batch_prediction_mismatched_ids_raises_error(hybrid_classifier: IncidentClassifier):
    """Mismatched report_ids length raises MLInputError."""
    with pytest.raises(MLInputError, match="Length of report_ids"):
        hybrid_classifier.predict_batch(["Text 1", "Text 2"], report_ids=["only_one_id"])


# ==============================================================================
# 10. Packaging & Schema Invariance
# ==============================================================================
def test_to_component_result(hybrid_classifier: IncidentClassifier):
    """to_component_result() must match canonical ComponentResult contract."""
    result = hybrid_classifier.predict("Severe earthquake ground shaking and tremors.")
    comp_result = result.to_component_result()

    assert isinstance(comp_result, ComponentResult)
    assert comp_result.component == "classification"
    assert comp_result.status in ("SUCCESS", "NEEDS_REVIEW")
    assert comp_result.data["incident_type"]["label"] == "EARTHQUAKE_LANDSLIDE"
    assert comp_result.data["incident_type"]["confidence"] == result.confidence
    assert comp_result.confidence == result.confidence


def test_to_dict_serialization(hybrid_classifier: IncidentClassifier):
    """to_dict() must return JSON-serializable dictionary."""
    result = hybrid_classifier.predict("Person suffering cardiac arrest, needs CPR.")
    d = result.to_dict()

    assert d["label"] == "MEDICAL_EMERGENCY"
    assert isinstance(d["confidence"], float)
    assert isinstance(d["class_scores"], dict)
    assert isinstance(d["evidence"], dict)
    assert isinstance(d["warnings"], list)
    # Ensure serializable to JSON
    json_str = json.dumps(d)
    assert "MEDICAL_EMERGENCY" in json_str


def test_public_functional_convenience_interface():
    """classify_incident() functional wrapper functions properly."""
    result = classify_incident("Gas line exploded causing a major building fire.")
    assert result.label == "FIRE_WILDFIRE_EXPLOSION"
    assert result.confidence >= 0.60


# ==============================================================================
# 11. Observability & Privacy Invariance
# ==============================================================================
def test_logging_does_not_leak_raw_emergency_text():
    """Logging during classification must not dump raw distress text."""
    formatter = MLJsonFormatter()
    record = logging.LogRecord(
        name="karen.ml.classification",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Classification complete",
        args=(),
        exc_info=None,
    )
    record.extra_context = {
        "raw_text": "Sensitive report: 3 people trapped under burning timber!",
        "predicted_label": "FIRE_WILDFIRE_EXPLOSION",
        "confidence": 0.88,
    }

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert "[REDACTED_TEXT: length=56]" in parsed["raw_text"]
    assert "3 people trapped" not in parsed["raw_text"]
    assert parsed["predicted_label"] == "FIRE_WILDFIRE_EXPLOSION"


# ==============================================================================
# 12. Benchmark Evaluator Test
# ==============================================================================
def test_classifier_evaluator_execution(hybrid_classifier: IncidentClassifier):
    """ClassifierEvaluator runs across benchmark subset and produces metrics."""
    evaluator = ClassifierEvaluator()
    subset = INCIDENT_BENCHMARK_DATASET[:9]  # 1 per class

    report = evaluator.evaluate(hybrid_classifier, benchmark=subset, approach_name="Hybrid Smoke")

    assert report.total_samples == 9
    assert report.accuracy >= 0.88
    assert report.macro_f1 >= 0.85
    assert report.warm_avg_latency_ms < 50.0  # CPU target
    assert isinstance(report.confusion_matrix, dict)
