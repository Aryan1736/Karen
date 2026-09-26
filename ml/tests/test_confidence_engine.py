"""
Karen's Ear — Feature 9: Confidence & Quality Engine Comprehensive Test Matrix.

Verifies:
1. All components high confidence
2. All components medium confidence
3. One low-confidence component
4. One zero-confidence component
5. Null confidence handling
6. Missing component handling
7. Single component extraction failure
8. Multiple component extraction failures
9. All components unavailable / all components failed
10. Confidence below 0.60 (NEEDS_REVIEW)
11. Confidence exactly 0.60 (SUCCESS boundary)
12. Confidence above 0.60 (SUCCESS)
13. Confidence = 0.0 limit
14. Confidence = 1.0 boundary
15. Invalid negative confidence (< 0.0) raises MLInputError
16. Invalid confidence > 1.0 raises MLInputError
17. NaN confidence raises MLInputError
18. Infinity confidence raises MLInputError
19. Weighted harmonic mean exact mathematical correctness
20. Changing component weight changes result
21. Weights are not silently normalized incorrectly (scale invariance)
22. Deterministic repeated calculation
23. Status precedence hierarchy (FAILED > NEEDS_REVIEW > PARTIAL > SUCCESS)
24. PARTIAL status behavior and intelligence preservation
25. NEEDS_REVIEW status behavior
26. FAILED status behavior
27. No fabricated confidence for missing/unextracted components
28. Embedding vectors explicitly excluded from harmonic mean
29. Urgency confidence strictly independent from urgency score
30. Classification confidence strictly independent from class label
31. Monotonicity property: increasing c_i increases C
32. Mathematical bound invariant: C in [0.0, 1.0]
33. Evaluator integration verification
34. calculate_from_component_results integration
35. calculate_from_ml_output integration with canonical schema
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from ml.classification.incident_classifier import ClassificationResult
from ml.confidence.confidence_engine import (
    ComponentConfidenceDetail,
    ConfidenceEngine,
    ConfidenceResult,
    calculate_confidence,
    validate_confidence_value,
)
from ml.confidence.evaluator import ConfidenceEvaluator, run_confidence_evaluation
from ml.config import (
    DEFAULT_CONFIDENCE_WEIGHTS,
    ComponentResult,
    MLConfig,
)
from ml.exceptions import MLConfigurationError, MLInputError
from ml.extraction.location_entity_extractor import LocationEntityResult, LocationPrediction
from ml.extraction.people_risk_extractor import PeopleRiskResult
from ml.response.response_extractor import ResponseExtractionResult, ResponseNeed
from ml.urgency.urgency_engine import ComponentScore, UrgencyBreakdown, UrgencyResult


# ==============================================================================
# 1-3. All High, Medium, One Low Confidence Scenarios
# ==============================================================================

def test_all_components_high_confidence():
    """1. All components have high confidence (>= 0.85)."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=0.95,
        urgency=0.90,
        location=0.88,
        people_at_risk=0.85,
        required_response=0.92,
    )
    assert res.overall_confidence is not None
    assert 0.85 <= res.overall_confidence <= 1.0
    assert res.status == "SUCCESS"
    assert res.needs_review is False
    assert len(res.warnings) == 0


def test_all_components_medium_confidence():
    """2. All components have medium confidence (~0.70)."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=0.72,
        urgency=0.70,
        location=0.68,
        people_at_risk=0.70,
        required_response=0.75,
    )
    assert res.overall_confidence is not None
    assert 0.65 <= res.overall_confidence <= 0.75
    assert res.status == "SUCCESS"
    assert res.needs_review is False


def test_one_low_confidence_component_pulls_harmonic_mean():
    """3. One low-confidence component pulls down the harmonic mean disproportionately."""
    engine = ConfidenceEngine()
    # Harmonic mean strongly penalizes low outliers compared to arithmetic mean
    res_uniform = engine.calculate(incident_type=0.85, urgency=0.85)
    res_one_low = engine.calculate(incident_type=0.85, urgency=0.35)

    assert res_uniform.overall_confidence is not None
    assert res_one_low.overall_confidence is not None
    assert res_one_low.overall_confidence < res_uniform.overall_confidence
    # Urgency 0.35 pulls the overall confidence below 0.60
    assert res_one_low.overall_confidence < 0.60
    assert res_one_low.status == "NEEDS_REVIEW"
    assert res_one_low.needs_review is True


# ==============================================================================
# 4-6. Zero, Null, and Missing Components
# ==============================================================================

def test_one_zero_confidence_component_collapses_to_zero():
    """4 & 13. Component with confidence 0.0 collapses overall harmonic mean to 0.0."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=0.95,
        urgency=0.0,  # Zero confidence
        location=0.85,
    )
    assert res.overall_confidence == 0.0
    assert res.status == "NEEDS_REVIEW"
    assert res.needs_review is True
    assert any("Zero confidence" in w for w in res.warnings)


def test_null_confidence_excluded_without_fabrication_or_penalty():
    """5. Null confidence is legitimately excluded, not converted to 0.0 or 1.0."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=0.90,
        urgency=0.80,
        location={"text": None, "confidence": None},  # No location found in report
        people_at_risk={"count": None, "confidence": None},  # No victims mentioned
    )
    assert res.overall_confidence is not None
    # Harmonic mean of 0.90 (w=0.30) and 0.80 (w=0.25):
    # Numerator = 0.55, Denominator = 0.30/0.90 + 0.25/0.80 = 0.333333 + 0.3125 = 0.645833
    # Result = 0.55 / 0.645833 = 0.8516
    assert res.overall_confidence == 0.8516
    assert res.status == "SUCCESS"
    assert res.components["location"].confidence is None
    assert not res.components["location"].included
    assert res.components["location"].reason == "confidence is null / not applicable"
    assert res.components["people_at_risk"].confidence is None
    assert not res.components["people_at_risk"].included


def test_missing_component_not_provided_excluded_gracefully():
    """6. Unprovided/missing components are marked UNAVAILABLE and excluded."""
    engine = ConfidenceEngine()
    res = engine.calculate(incident_type=0.90, urgency=0.85)

    assert res.components["location"].status == "UNAVAILABLE"
    assert not res.components["location"].included
    assert res.components["location"].confidence is None
    assert res.overall_confidence is not None
    assert res.status == "SUCCESS"


# ==============================================================================
# 7-9. Component Extraction Failures & Graceful Degradation
# ==============================================================================

def test_single_component_extraction_failure_degrades_to_partial():
    """7 & 24. Individual extraction failure degrades to PARTIAL, preserving other outputs."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=0.90,
        urgency=0.85,
        location=ComponentResult(
            component="location_and_entities",
            status="FAILED",
            warnings=["Gazetteer connection timeout"],
        ),
    )
    # Remaining components are high confidence (>= 0.60), but location failed
    assert res.status == "PARTIAL"
    assert res.needs_review is False
    assert res.overall_confidence is not None
    assert res.overall_confidence >= 0.60
    assert res.components["location"].status == "FAILED"
    assert not res.components["location"].included
    assert any("Gazetteer connection timeout" in w for w in res.warnings)
    assert any("pipeline degraded gracefully to PARTIAL" in w for w in res.warnings)


def test_multiple_component_extraction_failures():
    """8. Multiple component failures preserve surviving confident outputs with PARTIAL."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=0.92,
        urgency=ComponentResult(component="urgency", status="FAILED", warnings=["Urgency OOM"]),
        location=ComponentResult(component="location_and_entities", status="FAILED", warnings=["NER crashed"]),
        people_at_risk=0.88,
    )
    assert res.status == "PARTIAL"
    assert res.needs_review is False
    assert res.overall_confidence is not None
    assert res.overall_confidence >= 0.60
    assert res.components["urgency"].status == "FAILED"
    assert res.components["location"].status == "FAILED"


def test_all_components_unavailable_or_failed_emits_failed_status():
    """9 & 26. All components failed emits FAILED status and None confidence."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=ComponentResult(component="classification", status="FAILED"),
        urgency=ComponentResult(component="urgency", status="FAILED"),
        location=ComponentResult(component="location_and_entities", status="FAILED"),
    )
    assert res.status == "FAILED"
    assert res.needs_review is True
    assert res.overall_confidence is None
    assert any("All inference components failed" in w for w in res.warnings)

    # Empty calculation also yields FAILED
    res_empty = engine.calculate()
    assert res_empty.status == "FAILED"
    assert res_empty.overall_confidence is None
    assert res_empty.needs_review is True


# ==============================================================================
# 10-14. Threshold Boundaries & Extremes
# ==============================================================================

def test_confidence_strictly_below_review_threshold():
    """10 & 25. Confidence below 0.60 triggers NEEDS_REVIEW."""
    engine = ConfidenceEngine()
    res = engine.calculate(incident_type=0.55, urgency=0.55)
    assert res.overall_confidence == 0.55
    assert res.overall_confidence < 0.60
    assert res.status == "NEEDS_REVIEW"
    assert res.needs_review is True
    assert any("below review threshold" in w for w in res.warnings)


def test_confidence_exactly_at_review_threshold():
    """11. Confidence exactly at 0.60 is NOT strictly below 0.60, so SUCCESS."""
    engine = ConfidenceEngine()
    res = engine.calculate(incident_type=0.60, urgency=0.60)
    assert res.overall_confidence == 0.60
    assert res.status == "SUCCESS"
    assert res.needs_review is False


def test_confidence_above_review_threshold():
    """12. Confidence above 0.60 yields SUCCESS."""
    engine = ConfidenceEngine()
    res = engine.calculate(incident_type=0.61, urgency=0.61)
    assert res.overall_confidence == 0.61
    assert res.status == "SUCCESS"
    assert res.needs_review is False


def test_confidence_perfect_boundary():
    """14. Perfect confidence 1.0 yields overall confidence 1.0."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=1.0,
        urgency=1.0,
        location=1.0,
        people_at_risk=1.0,
        required_response=1.0,
    )
    assert res.overall_confidence == 1.0
    assert res.status == "SUCCESS"
    assert res.needs_review is False


# ==============================================================================
# 15-18. Strict Validation: Rejection of Out-of-Range, NaN, Inf, Types
# ==============================================================================

def test_invalid_negative_confidence_raises_ml_input_error():
    """15. Negative confidence (< 0.0) is strictly rejected with MLInputError."""
    engine = ConfidenceEngine()
    with pytest.raises(MLInputError, match="bounded in \\[0.0, 1.0\\]"):
        engine.calculate(incident_type=-0.05)


def test_invalid_confidence_greater_than_one_raises_ml_input_error():
    """16. Confidence > 1.0 is strictly rejected with MLInputError."""
    engine = ConfidenceEngine()
    with pytest.raises(MLInputError, match="bounded in \\[0.0, 1.0\\]"):
        engine.calculate(urgency=1.05)


def test_nan_confidence_raises_ml_input_error():
    """17. NaN confidence cannot enter calculation and raises MLInputError."""
    engine = ConfidenceEngine()
    with pytest.raises(MLInputError, match="cannot be NaN or infinity"):
        engine.calculate(location=float("nan"))


def test_infinity_confidence_raises_ml_input_error():
    """18. Infinity confidence raises MLInputError."""
    engine = ConfidenceEngine()
    with pytest.raises(MLInputError, match="cannot be NaN or infinity"):
        engine.calculate(incident_type=float("inf"))

    with pytest.raises(MLInputError, match="cannot be NaN or infinity"):
        engine.calculate(incident_type=float("-inf"))


def test_boolean_confidence_rejected():
    """Booleans (True/False) must not be silently treated as 1.0/0.0."""
    engine = ConfidenceEngine()
    with pytest.raises(MLInputError, match="got bool"):
        engine.calculate(incident_type=True)

    with pytest.raises(MLInputError, match="got bool"):
        validate_confidence_value(False)


# ==============================================================================
# 19-21. Weighted Harmonic Mean Correctness & Weight Policies
# ==============================================================================

def test_weighted_harmonic_mean_analytical_correctness():
    """19. Verifies harmonic mean against exact hand-calculated analytical example."""
    engine = ConfidenceEngine()
    # Inputs:
    # incident_type: c=0.90, w=0.30
    # urgency:       c=0.80, w=0.25
    # location:      c=0.70, w=0.20
    # people_at_risk: c=0.60, w=0.15
    # required_response: c=0.85, w=0.10
    # Numerator = 0.30 + 0.25 + 0.20 + 0.15 + 0.10 = 1.00
    # Denominator = 0.30/0.90 + 0.25/0.80 + 0.20/0.70 + 0.15/0.60 + 0.10/0.85
    #             = 0.333333 + 0.312500 + 0.285714 + 0.250000 + 0.117647 = 1.299194
    # H = 1.00 / 1.299194 = 0.7697
    res = engine.calculate(
        incident_type=0.90,
        urgency=0.80,
        location=0.70,
        people_at_risk=0.60,
        required_response=0.85,
    )
    assert res.overall_confidence == 0.7697


def test_changing_component_weight_changes_result():
    """20. Modifying component weight shifts the resulting harmonic mean."""
    engine = ConfidenceEngine()
    # Incident type = 0.40 (low), Urgency = 0.90 (high)
    # Heavy incident type:
    res_heavy_incident = engine.calculate(
        incident_type=0.40,
        urgency=0.90,
        override_weights={"incident_type": 0.80, "urgency": 0.20},
    )
    # Heavy urgency:
    res_heavy_urgency = engine.calculate(
        incident_type=0.40,
        urgency=0.90,
        override_weights={"incident_type": 0.20, "urgency": 0.80},
    )
    assert res_heavy_incident.overall_confidence is not None
    assert res_heavy_urgency.overall_confidence is not None
    # Shifting weight toward high confidence component increases the overall score
    assert res_heavy_urgency.overall_confidence > res_heavy_incident.overall_confidence


def test_weights_scale_invariance():
    """21. Multiplying all weights by a constant factor does not alter harmonic mean."""
    engine = ConfidenceEngine()
    res1 = engine.calculate(
        incident_type=0.80,
        urgency=0.60,
        override_weights={"incident_type": 0.30, "urgency": 0.25},
    )
    res2 = engine.calculate(
        incident_type=0.80,
        urgency=0.60,
        override_weights={"incident_type": 3.0, "urgency": 2.5},
    )
    assert res1.overall_confidence == res2.overall_confidence


# ==============================================================================
# 22. Determinism
# ==============================================================================

def test_deterministic_repeated_calculation():
    """22. Running identical inputs produces bitwise identical results."""
    engine = ConfidenceEngine()
    res1 = engine.calculate(
        incident_type=0.88,
        urgency=0.75,
        location={"text": "Patia", "confidence": 0.72},
        people_at_risk={"count": 3, "confidence": 0.65},
    )
    for _ in range(25):
        res2 = engine.calculate(
            incident_type=0.88,
            urgency=0.75,
            location={"text": "Patia", "confidence": 0.72},
            people_at_risk={"count": 3, "confidence": 0.65},
        )
        assert res1.to_dict() == res2.to_dict()


# ==============================================================================
# 23. Status Precedence Hierarchy (FAILED > NEEDS_REVIEW > PARTIAL > SUCCESS)
# ==============================================================================

def test_status_precedence_low_confidence_and_component_failure():
    """23. Deterministic precedence: Low confidence (< 0.60) + component failure -> NEEDS_REVIEW."""
    engine = ConfidenceEngine()
    # Surviving component has low confidence (0.45), while location failed
    res = engine.calculate(
        incident_type=0.45,
        urgency=0.50,
        location=ComponentResult(component="location_and_entities", status="FAILED"),
    )
    # Low confidence demands operator review; status is NEEDS_REVIEW (not plain PARTIAL)
    assert res.status == "NEEDS_REVIEW"
    assert res.needs_review is True
    assert any("below review threshold" in w for w in res.warnings)
    assert any("failed extraction" in w for w in res.warnings)


def test_status_precedence_critical_conflict():
    """Critical conflict overrides high confidence and forces NEEDS_REVIEW."""
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=0.95,
        urgency=0.92,
        has_conflict=True,
    )
    assert res.status == "NEEDS_REVIEW"
    assert res.needs_review is True
    assert any("Critical conflict detected" in w for w in res.warnings)


# ==============================================================================
# 27-30. Separation of Concerns & Cross-Feature Independence
# ==============================================================================

def test_no_fabricated_confidence_for_missing_components():
    """27. Engine never fabricates default 1.0 or 0.0 for absent extractions."""
    engine = ConfidenceEngine()
    res = engine.calculate(incident_type=0.90)
    for name in ("urgency", "location", "people_at_risk", "required_response"):
        detail = res.components[name]
        assert detail.confidence is None
        assert not detail.included


def test_embedding_vector_excluded_from_confidence_aggregation():
    """28. Raw embedding vector has no intrinsic confidence and is excluded from harmonic mean."""
    engine = ConfidenceEngine()
    emb_vector = [0.123] * 384
    res_with_emb = engine.calculate(
        incident_type=0.85,
        urgency=0.75,
        embedding=emb_vector,
    )
    res_without_emb = engine.calculate(
        incident_type=0.85,
        urgency=0.75,
    )
    assert res_with_emb.overall_confidence == res_without_emb.overall_confidence
    assert "embeddings" in res_with_emb.components
    assert res_with_emb.components["embeddings"].included is False
    assert res_with_emb.components["embeddings"].weight == 0.0


def test_urgency_confidence_independent_from_urgency_score():
    """29. Urgency confidence is decoupled from Feature 7 urgency score."""
    engine = ConfidenceEngine()
    # High urgency score (95.0, CRITICAL) but low confidence (0.45)
    breakdown = UrgencyBreakdown(
        life_safety=ComponentScore(name="life_safety", score=50.0, weight=0.5, weighted_contribution=25.0),
        hazard_velocity=ComponentScore(name="hazard_velocity", score=30.0, weight=0.3, weighted_contribution=9.0),
        vulnerability=ComponentScore(name="vulnerability", score=15.0, weight=0.2, weighted_contribution=3.0),
    )
    urg_res = UrgencyResult(
        score=95.0,
        label="CRITICAL",
        confidence=0.45,
        breakdown=breakdown,
    )
    res = engine.calculate(incident_type=0.90, urgency=urg_res)
    # The confidence engine aggregates 0.45, NOT 95.0
    assert res.components["urgency"].confidence == 0.45
    assert urg_res.score == 95.0


def test_classification_confidence_independent_from_label():
    """30. Classification confidence is decoupled from category label."""
    engine = ConfidenceEngine()
    clf_res = ClassificationResult(
        label="OTHER_GENERAL_INCIDENT",
        confidence=0.88,
        method="keyword_hybrid",
    )
    res = engine.calculate(incident_type=clf_res, urgency=0.80)
    assert res.components["incident_type"].confidence == 0.88
    assert res.status == "SUCCESS"


# ==============================================================================
# 31-32. Property / Invariant Checks
# ==============================================================================

def test_monotonicity_property():
    """31. Increasing component confidence c_i increases or maintains overall confidence."""
    engine = ConfidenceEngine()
    c_vals = [0.30, 0.50, 0.70, 0.85, 0.95]
    prev_overall = 0.0

    for c in c_vals:
        res = engine.calculate(incident_type=c, urgency=0.80)
        assert res.overall_confidence is not None
        assert res.overall_confidence >= prev_overall
        prev_overall = res.overall_confidence


def test_overall_confidence_strictly_bounded_in_unit_interval():
    """32. Overall confidence is mathematically guaranteed in [0.0, 1.0]."""
    engine = ConfidenceEngine()
    for c1 in (0.0, 0.1, 0.5, 0.9, 1.0):
        for c2 in (0.0, 0.2, 0.6, 0.8, 1.0):
            res = engine.calculate(incident_type=c1, urgency=c2)
            assert res.overall_confidence is not None
            assert 0.0 <= res.overall_confidence <= 1.0


# ==============================================================================
# 33-35. Integration Adapters & Schema Compliance
# ==============================================================================

def test_calculate_from_component_results_integration():
    """34. calculate_from_component_results seamlessly integrates pipeline outputs."""
    engine = ConfidenceEngine()
    comp_list = [
        ComponentResult(component="classification", status="SUCCESS", confidence=0.92),
        ComponentResult(component="urgency", status="SUCCESS", confidence=0.84),
        ComponentResult(component="location_and_entities", status="SUCCESS", confidence=0.76),
        ComponentResult(component="embeddings", status="SUCCESS", confidence=None),
    ]
    res = engine.calculate_from_component_results(comp_list)
    assert res.overall_confidence is not None
    assert res.status == "SUCCESS"
    assert res.components["incident_type"].confidence == 0.92
    assert res.components["urgency"].confidence == 0.84
    assert res.components["location"].confidence == 0.76
    assert res.components["embeddings"].included is False


def test_calculate_from_ml_output_schema_integration():
    """35. calculate_from_ml_output processes canonical incident_output.json schema."""
    engine = ConfidenceEngine()
    canonical_output = {
        "report_id": "rep-101",
        "model_version": "all-MiniLM-L6-v2+heuristic-v1",
        "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.94},
        "urgency": {"label": "CRITICAL", "confidence": 0.88},
        "location": {
            "text": "Patia underpass",
            "latitude": 20.35,
            "longitude": 85.81,
            "precision": "approximate",
            "confidence": 0.82,
        },
        "people_at_risk": {"count": 4, "confidence": 0.80},
        "required_response": [
            {"type": "SEARCH_AND_RESCUE", "confidence": 0.90},
            {"type": "MEDICAL_EMS", "confidence": 0.85},
        ],
        "entities": [{"text": "Patia", "type": "LOCATION", "confidence": 0.90}],
        "embedding": [0.05] * 384,
        "processing_status": "SUCCESS",
        "warnings": [],
    }

    res = engine.calculate_from_ml_output(canonical_output)
    assert res.overall_confidence is not None
    assert 0.80 <= res.overall_confidence <= 0.95
    assert res.status == "SUCCESS"
    assert not res.needs_review

    # Check export matches docs/api-contract.md ConfidenceBlock
    conf_block = res.to_canonical_ml_confidence()
    assert "overall" in conf_block
    assert conf_block["overall"] == res.overall_confidence
    assert conf_block["components"]["incident_type"] == 0.94
    assert conf_block["components"]["urgency"] == 0.88
    assert conf_block["components"]["location"] == 0.82


def test_evaluator_suite_passes_all_checks():
    """33. Invariant evaluator suite executes and passes 100% of behavioral checks."""
    evaluator = ConfidenceEvaluator()
    report = evaluator.evaluate()
    assert report.passed_all_invariants is True
    assert report.total_checks_run >= 70
    assert report.mean_latency_ms < 10.0
    summary = report.summary()
    assert "ALL INVARIANTS PASSED" in summary


def test_public_functional_interface():
    """Verifies module-level calculate_confidence functional interface."""
    res = calculate_confidence(incident_type=0.88, urgency=0.82)
    assert isinstance(res, ConfidenceResult)
    assert res.overall_confidence is not None
    assert res.status == "SUCCESS"


def test_config_weight_validation_bounds():
    """Verifies that invalid configuration weights raise MLConfigurationError."""
    with pytest.raises(MLConfigurationError, match="strictly positive"):
        ConfidenceEngine(weights={"incident_type": -0.5})

    with pytest.raises(MLConfigurationError, match="strictly positive"):
        ConfidenceEngine(weights={"incident_type": 0.0})

    with pytest.raises(MLConfigurationError, match="must be a dict"):
        ConfidenceEngine(weights="not_a_dict")  # type: ignore

    with pytest.raises(MLConfigurationError, match="cannot be empty"):
        ConfidenceEngine(weights={})


# ==============================================================================
# Step 22 — Explicit Failure Degradation Scenarios
# ==============================================================================

def test_step22_failure_degradation_preserves_evidence_and_emits_partial():
    """
    Step 22 Scenario A:
    Classification succeeds, location fails, urgency succeeds.
    Expected:
    - valid classification retained
    - valid urgency retained
    - location failure preserved
    - overall pipeline status = PARTIAL
    - no exception escaping the pipeline
    """
    engine = ConfidenceEngine()
    clf = ClassificationResult(label="FLOOD_FLASH_FLOOD", confidence=0.92, method="hybrid")
    urg_breakdown = UrgencyBreakdown(
        life_safety=ComponentScore("life_safety", 50.0, 0.5, 25.0),
        hazard_velocity=ComponentScore("hazard_velocity", 30.0, 0.3, 9.0),
        vulnerability=ComponentScore("vulnerability", 15.0, 0.2, 3.0),
    )
    urg = UrgencyResult(score=85.0, label="HIGH", confidence=0.88, breakdown=urg_breakdown)
    loc_fail = ComponentResult(
        component="location_and_entities",
        status="FAILED",
        warnings=["Gazetteer database connection refused"],
    )

    res = engine.calculate(
        incident_type=clf,
        urgency=urg,
        location=loc_fail,
    )

    # Valid outputs retained
    assert res.components["incident_type"].confidence == 0.92
    assert res.components["incident_type"].status == "SUCCESS"
    assert res.components["incident_type"].included is True

    assert res.components["urgency"].confidence == 0.88
    assert res.components["urgency"].status == "SUCCESS"
    assert res.components["urgency"].included is True

    # Location failure preserved
    assert res.components["location"].status == "FAILED"
    assert res.components["location"].included is False
    assert any("Gazetteer database connection refused" in w for w in res.warnings)

    # Overall pipeline status is PARTIAL
    assert res.status == "PARTIAL"
    assert res.needs_review is False
    assert res.overall_confidence is not None
    assert res.overall_confidence >= 0.60


def test_step22_low_confidence_with_surviving_components_not_failed():
    """
    Step 22 Scenario B:
    Classification succeeds, location has low confidence, urgency succeeds.
    Expected:
    - status reflects confidence policy (NEEDS_REVIEW if pulled < 0.60, or SUCCESS if >= 0.60)
    - NOT automatically FAILED
    """
    engine = ConfidenceEngine()
    clf = ClassificationResult(label="FIRE_WILDFIRE_EXPLOSION", confidence=0.85, method="hybrid")
    loc_low = LocationEntityResult(
        location=LocationPrediction(text="somewhere near hills", confidence=0.25, precision="approximate"),
        warnings=["Vague location phrasing"],
    )
    urg_breakdown = UrgencyBreakdown(
        life_safety=ComponentScore("life_safety", 50.0, 0.5, 25.0),
        hazard_velocity=ComponentScore("hazard_velocity", 30.0, 0.3, 9.0),
        vulnerability=ComponentScore("vulnerability", 15.0, 0.2, 3.0),
    )
    urg = UrgencyResult(score=75.0, label="HIGH", confidence=0.80, breakdown=urg_breakdown)

    res = engine.calculate(
        incident_type=clf,
        location=loc_low,
        urgency=urg,
    )

    # Never automatically FAILED
    assert res.status != "FAILED"
    # Low location confidence (0.25) pulls weighted harmonic mean down:
    # Let's verify harmonic mean:
    # Num = 0.30 + 0.25 + 0.20 = 0.75
    # Den = 0.30/0.85 + 0.25/0.80 + 0.20/0.25 = 0.3529 + 0.3125 + 0.8000 = 1.4654
    # H = 0.75 / 1.4654 = 0.5118 (< 0.60)
    assert res.overall_confidence == 0.5118
    assert res.status == "NEEDS_REVIEW"
    assert res.needs_review is True


def test_step22_all_inference_infrastructure_unavailable_emits_failed():
    """
    Step 22 Scenario C:
    All inference infrastructure unavailable.
    Expected:
    - FAILED according to existing pipeline semantics
    - overall_confidence is None
    - needs_review is True
    """
    engine = ConfidenceEngine()
    res = engine.calculate(
        incident_type=ComponentResult(component="classification", status="FAILED", warnings=["Inference service unavailable"]),
        urgency=ComponentResult(component="urgency", status="FAILED", warnings=["Urgency model uninitialized"]),
        location=ComponentResult(component="location_and_entities", status="FAILED", warnings=["NER process timeout"]),
    )

    assert res.status == "FAILED"
    assert res.overall_confidence is None
    assert res.needs_review is True
    assert any("All inference components failed" in w for w in res.warnings)
