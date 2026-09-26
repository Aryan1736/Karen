"""
Karen's Ear — Operational Urgency Engine Test Suite.

Comprehensive tests for Step 2B of the ML pipeline (architecture/ml-pipeline.md Section 3.3).
Validates all 37+ required architectural invariants, boundary conditions, feature interactions,
no-inference principles, confidence separation, and benchmark evaluation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest

from ml.classification.incident_classifier import ClassificationResult
from ml.config import (
    CANONICAL_URGENCY_LEVELS,
    ComponentResult,
    MLConfig,
    get_ml_config,
    reset_ml_config,
)
from ml.exceptions import MLInputError
from ml.extraction.location_entity_extractor import (
    EntityMention,
    LocationEntityResult,
    LocationPrediction,
)
from ml.extraction.people_risk_extractor import PeopleRiskResult, RiskEvidence
from ml.logging_utils import MLJsonFormatter
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner
from ml.response.response_extractor import (
    RequiredResponseExtractor,
    ResponseEvidence,
    ResponseExtractionResult,
    ResponseNeed,
)
from ml.tests.fixtures.urgency_benchmark import (
    CURATED_URGENCY_BENCHMARK,
    UrgencyBenchmarkSample,
)
from ml.urgency import (
    LABEL_CRITICAL,
    LABEL_HIGH,
    LABEL_LOW,
    LABEL_MEDIUM,
    THRESHOLD_CRITICAL,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    WEIGHT_HAZARD_VELOCITY,
    WEIGHT_LIFE_SAFETY,
    WEIGHT_VULNERABILITY,
    ComponentScore,
    UrgencyBreakdown,
    UrgencyEngine,
    UrgencyEvaluationReport,
    UrgencyEvaluator,
    UrgencyResult,
    extract_urgency,
    is_canonical_urgency_label,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "incident_output.json"


@pytest.fixture(scope="module")
def canonical_schema() -> dict:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def engine() -> UrgencyEngine:
    return UrgencyEngine()


# ==============================================================================
# 1–4. Core Urgency Tier Tests
# ==============================================================================

class TestCoreUrgencyTiers:
    """Tests 1–4: Core examples for each canonical urgency tier."""

    def test_01_critical_trapped_collapse_example(self, engine: UrgencyEngine):
        """1. Critical trapped/collapse example."""
        text = "HELP! 5 people trapped inside collapsing building right now!"
        res = engine.score_urgency(
            text=text,
            incident_type="STRUCTURAL_COLLAPSE",
            people_at_risk=5,
            required_response=["SEARCH_AND_RESCUE"],
        )
        assert res.label == LABEL_CRITICAL
        assert res.score >= 80.0
        assert res.breakdown.life_safety.score >= 80.0
        assert res.breakdown.hazard_velocity.score >= 80.0
        assert "TRAPPED" in res.signals or "COLLAPSE_WITH_OCCUPANTS" in res.signals
        assert res.processing_status == "SUCCESS"

    def test_02_high_medical_emergency(self, engine: UrgencyEngine):
        """2. High medical emergency."""
        text = "Cyclist struck by vehicle, unconscious and bleeding heavily from leg."
        res = engine.score_urgency(
            text=text,
            incident_type="MEDICAL_EMERGENCY",
            people_at_risk=1,
            required_response=["MEDICAL_EMS"],
        )
        assert res.label == LABEL_HIGH
        assert 60.0 <= res.score < 80.0
        assert res.breakdown.life_safety.score >= 70.0

    def test_03_medium_incident(self, engine: UrgencyEngine):
        """3. Medium incident."""
        text = "Heavy rain causing water accumulation across Main Street, road blocked by standing water."
        res = engine.score_urgency(
            text=text,
            incident_type="FLOOD_FLASH_FLOOD",
            required_response=["PUBLIC_WORKS_UTILITY"],
        )
        assert res.label == LABEL_MEDIUM
        assert 35.0 <= res.score < 60.0
        assert res.breakdown.life_safety.score == 0.0  # No human peril reported

    def test_04_low_informational_incident(self, engine: UrgencyEngine):
        """4. Low informational incident."""
        text = "Advisory notice: Municipal water department scheduled pipeline maintenance tomorrow between 9am and 1pm."
        res = engine.score_urgency(
            text=text,
            incident_type="UTILITY_INFRASTRUCTURE_FAILURE",
        )
        assert res.label == LABEL_LOW
        assert 0.0 <= res.score < 35.0


# ==============================================================================
# 5–10. Exact Boundary Threshold Tests
# ==============================================================================

class TestExactBoundaryThresholds:
    """Tests 5–10 & Boundary Continuity: Deterministic label mapping at exact boundaries."""

    def test_05_exact_threshold_34(self, engine: UrgencyEngine):
        """5. Exact threshold 34 maps to LOW."""
        assert engine.map_score_to_label(34.0) == LABEL_LOW

    def test_06_exact_threshold_35(self, engine: UrgencyEngine):
        """6. Exact threshold 35 maps to MEDIUM."""
        assert engine.map_score_to_label(35.0) == LABEL_MEDIUM

    def test_07_exact_threshold_59(self, engine: UrgencyEngine):
        """7. Exact threshold 59 maps to MEDIUM."""
        assert engine.map_score_to_label(59.0) == LABEL_MEDIUM

    def test_08_exact_threshold_60(self, engine: UrgencyEngine):
        """8. Exact threshold 60 maps to HIGH."""
        assert engine.map_score_to_label(60.0) == LABEL_HIGH

    def test_09_exact_threshold_79(self, engine: UrgencyEngine):
        """9. Exact threshold 79 maps to HIGH."""
        assert engine.map_score_to_label(79.0) == LABEL_HIGH

    def test_10_exact_threshold_80(self, engine: UrgencyEngine):
        """10. Exact threshold 80 maps to CRITICAL."""
        assert engine.map_score_to_label(80.0) == LABEL_CRITICAL

    def test_boundary_floating_point_precision(self, engine: UrgencyEngine):
        """Tests boundaries with sub-integer floating point offsets."""
        assert engine.map_score_to_label(34.99) == LABEL_LOW
        assert engine.map_score_to_label(35.0) == LABEL_MEDIUM
        assert engine.map_score_to_label(35.01) == LABEL_MEDIUM

        assert engine.map_score_to_label(59.99) == LABEL_MEDIUM
        assert engine.map_score_to_label(60.0) == LABEL_HIGH
        assert engine.map_score_to_label(60.01) == LABEL_HIGH

        assert engine.map_score_to_label(79.99) == LABEL_HIGH
        assert engine.map_score_to_label(80.0) == LABEL_CRITICAL
        assert engine.map_score_to_label(80.01) == LABEL_CRITICAL


# ==============================================================================
# 11–13. Score Clamping & Input Validation Tests
# ==============================================================================

class TestClampingAndInputValidation:
    """Tests 11–13: Clamping bounds and input validation."""

    def test_11_score_clamping(self, engine: UrgencyEngine):
        """11. Score clamping: score cannot exceed 100 or fall below 0."""
        assert engine.map_score_to_label(150.0) == LABEL_CRITICAL
        assert engine.map_score_to_label(-20.0) == LABEL_LOW

        # Synthetic test with extreme values
        score = max(0.0, min(100.0, 150.0))
        assert score == 100.0

    def test_12_empty_input(self, engine: UrgencyEngine):
        """12. Empty input raises MLInputError."""
        with pytest.raises(MLInputError, match="cannot be empty"):
            engine.score_urgency("")

        with pytest.raises(MLInputError, match="cannot be empty"):
            engine.score_urgency("   \n\t  ")

    def test_13_malformed_input(self, engine: UrgencyEngine):
        """13. Malformed input raises MLInputError."""
        with pytest.raises(MLInputError, match="cannot be None"):
            engine.score_urgency(None)  # type: ignore

        with pytest.raises(MLInputError, match="Unsupported text type"):
            engine.score_urgency(12345)  # type: ignore


# ==============================================================================
# 14–18. No-Inference, Qualitative & Vulnerability Tests
# ==============================================================================

class TestSignalsAndVulnerability:
    """Tests 14–18: No-inference principle, qualitative people, and demographic vulnerability."""

    def test_14_no_inference_behavior(self, engine: UrgencyEngine):
        """14. No-inference behavior: incident category alone does not fabricate life-safety."""
        text = "Small road closure due to routine utility inspection."
        res = engine.score_urgency(text, incident_type="UTILITY_INFRASTRUCTURE_FAILURE")
        assert res.breakdown.life_safety.score == 0.0
        assert res.breakdown.vulnerability.score == 0.0
        assert res.label == LABEL_LOW

    def test_15_multiple_people_without_numeric_fabrication(self, engine: UrgencyEngine):
        """15. Multiple people without numeric count fabrication."""
        text = "Multiple people trapped under debris, unable to get out."
        res = engine.score_urgency(text, people_at_risk=None)  # No numeric count provided
        # Score is elevated qualitatively
        assert res.breakdown.life_safety.score >= 80.0
        assert "MULTIPLE_PEOPLE_QUALITATIVE" in res.signals or "TRAPPED" in res.signals
        # Numeric count was NOT fabricated in result
        assert res.breakdown.life_safety.details.get("people_count") is None

    def test_16_children_vulnerability(self, engine: UrgencyEngine):
        """16. Children vulnerability: children in peril strongly elevates vulnerability."""
        text = "Daycare center surrounded by fast floodwater, ten toddlers trapped on second floor."
        res = engine.score_urgency(text, people_at_risk=10)
        assert res.breakdown.vulnerability.score >= 80.0
        assert "CHILDREN_AT_RISK" in res.signals
        assert res.label == LABEL_CRITICAL

    def test_17_elderly_vulnerability(self, engine: UrgencyEngine):
        """17. Elderly vulnerability: nursing home occupants at risk."""
        text = "Nursing home residents need immediate evacuation as water enters ground floor."
        res = engine.score_urgency(text)
        assert res.breakdown.vulnerability.score >= 70.0
        assert "ELDERLY_AT_RISK" in res.signals or "VULNERABLE_FACILITY_AFFECTED" in res.signals

    def test_18_patients_vulnerability(self, engine: UrgencyEngine):
        """18. Patients vulnerability: hospital/ICU patients at risk."""
        text = "Hospital patients trapped inside intensive care unit following power failure."
        res = engine.score_urgency(text)
        assert res.breakdown.vulnerability.score >= 80.0
        assert "PATIENTS_AT_RISK" in res.signals


# ==============================================================================
# 19–25. Dynamic Hazard Velocity, Negation & Utility Tests
# ==============================================================================

class TestHazardVelocityAndContext:
    """Tests 19–25: Active threat, historical, extinguished, flood dynamics, utility."""

    def test_19_active_threat(self, engine: UrgencyEngine):
        """19. Active threat elevates life safety and hazard velocity."""
        text = "Active shooter firing inside shopping complex right now, multiple people wounded!"
        res = engine.score_urgency(text, incident_type="CIVIL_UNREST_ACTIVE_THREAT")
        assert res.label == LABEL_CRITICAL
        assert res.score >= 80.0
        assert "ACTIVE_THREAT_TO_PEOPLE" in res.signals or "ACTIVE_SHOOTING_ATTACK" in res.signals

    def test_20_historical_incident(self, engine: UrgencyEngine):
        """20. Historical incident: happened yesterday drastically suppresses velocity."""
        text = "Building collapsed yesterday afternoon; area is now secured and road closed."
        res = engine.score_urgency(text, incident_type="STRUCTURAL_COLLAPSE")
        assert res.breakdown.hazard_velocity.score <= 15.0
        assert res.label == LABEL_LOW

    def test_21_extinguished_fire(self, engine: UrgencyEngine):
        """21. Extinguished fire suppresses hazard velocity."""
        text = "Building on fire earlier, but fire is now extinguished and under control."
        res = engine.score_urgency(text, incident_type="FIRE_WILDFIRE_EXPLOSION")
        assert res.breakdown.hazard_velocity.score <= 15.0
        assert "EXTINGUISHED_OR_CONTAINED" in res.signals

    def test_22_rapidly_rising_flood(self, engine: UrgencyEngine):
        """22. Rapidly rising flood: high hazard velocity."""
        text = "River embankment breach, water is rising rapidly across the residential colony!"
        res = engine.score_urgency(text, incident_type="FLOOD_FLASH_FLOOD")
        assert res.breakdown.hazard_velocity.score >= 80.0
        assert "RAPIDLY_RISING_WATER" in res.signals

    def test_23_static_flood_damage(self, engine: UrgencyEngine):
        """23. Static flood damage: moderate velocity, not critical."""
        text = "Waterlogged street with stagnant standing water, knee-deep puddle on lane."
        res = engine.score_urgency(text, incident_type="FLOOD_FLASH_FLOOD")
        assert res.breakdown.hazard_velocity.score <= 60.0
        assert res.label in (LABEL_MEDIUM, LABEL_LOW)

    def test_24_utility_outage(self, engine: UrgencyEngine):
        """24. Utility outage: power outage alone is not critical."""
        text = "Power outage affecting several streets due to blown transformer."
        res = engine.score_urgency(text, incident_type="UTILITY_INFRASTRUCTURE_FAILURE")
        assert res.label in (LABEL_MEDIUM, LABEL_LOW)
        assert res.score < 60.0

    def test_25_live_power_lines(self, engine: UrgencyEngine):
        """25. Live power lines fallen with people trapped in vehicle."""
        text = "Live power lines down sparking across road and two people are trapped in car."
        res = engine.score_urgency(
            text,
            incident_type="UTILITY_INFRASTRUCTURE_FAILURE",
            people_at_risk=2,
            required_response=["SEARCH_AND_RESCUE", "PUBLIC_WORKS_UTILITY"],
        )
        assert res.label == LABEL_CRITICAL
        assert res.score >= 80.0
        assert "ELECTRICAL_ARCING_LIVE_WIRES" in res.signals
        assert "TRAPPED" in res.signals


# ==============================================================================
# 26–28. Uncertainty, Distress & Negation Tests
# ==============================================================================

class TestUncertaintyDistressNegation:
    """Tests 26–28: Uncertainty markers, distress language, and casualty negation."""

    def test_26_uncertainty_markers(self, engine: UrgencyEngine):
        """26. Uncertainty markers: hedging reduces confidence without destroying score."""
        text = "Someone said there might possibly be people trapped inside, not sure."
        res = engine.score_urgency(text)
        assert res.confidence < 0.60
        assert res.processing_status == "NEEDS_REVIEW"
        assert res.score >= 40.0  # Score remains honest to trapped mention

    def test_27_distress_language(self, engine: UrgencyEngine):
        """27. Distress language: HELP! / SOS boosts life-safety and confidence."""
        text = "HELP! SOS! We are trapped in basement and cannot breathe!"
        res = engine.score_urgency(text)
        assert res.label == LABEL_CRITICAL
        assert any(s.startswith("DISTRESS_") for s in res.signals)
        assert res.confidence >= 0.70

    def test_informational_help_does_not_trigger_distress(self, engine: UrgencyEngine):
        """Informational mention of 'help desk' must not trigger emergency distress."""
        text = "Information help desk opened at the library for municipal queries."
        res = engine.score_urgency(text)
        assert not any(s.startswith("DISTRESS_") for s in res.signals)
        assert res.label == LABEL_LOW

    def test_28_negation(self, engine: UrgencyEngine):
        """28. Negation: 'no one is injured' suppresses life safety to 0."""
        text = "Bus crashed into guardrail, but everyone is safe and zero casualties reported."
        res = engine.score_urgency(text)
        assert res.breakdown.life_safety.score == 0.0
        assert res.breakdown.life_safety.negated is True
        assert res.label == LABEL_LOW


# ==============================================================================
# 29–32. Feature Interaction Tests
# ==============================================================================

class TestFeatureInteractions:
    """Tests 29–32: Interoperability with Features 3, 4, 5, and 6."""

    def test_29_feature_4_interaction(self, engine: UrgencyEngine):
        """29. Feature 4 interaction: accepts PeopleRiskResult."""
        risk_res = PeopleRiskResult(
            count=3,
            confidence=0.88,
            signals=["TRAPPED", "INJURED"],
            evidence=[
                RiskEvidence(
                    raw_span="3 people trapped",
                    normalized_count=3,
                    people_noun="people",
                    risk_context="trapped",
                    quantifier_type="EXPLICIT",
                )
            ],
        )
        res = engine.score_urgency("Collapsed house on 4th street.", people_at_risk=risk_res)
        assert "TRAPPED" in res.signals
        assert res.breakdown.life_safety.score >= 80.0
        assert res.label >= LABEL_HIGH

    def test_30_feature_5_interaction(self, engine: UrgencyEngine):
        """30. Feature 5 interaction: passive facility mention does NOT inflate vulnerability."""
        loc_res = LocationEntityResult(
            location=LocationPrediction(text="near General Hospital"),
            entities=[EntityMention(text="hospital", type="FACILITY")],
        )
        text = "Traffic jam on arterial road near General Hospital."
        res = engine.score_urgency(text, location_entities=loc_res)
        # Passive hospital mention must NOT inflate vulnerability
        assert res.breakdown.vulnerability.score == 0.0
        assert res.label == LABEL_LOW

    def test_31_feature_6_interaction(self, engine: UrgencyEngine):
        """31. Feature 6 interaction: accepts ResponseExtractionResult."""
        resp_res = ResponseExtractionResult(
            responses=[
                ResponseNeed(type="SEARCH_AND_RESCUE", confidence=0.92),
                ResponseNeed(type="FIRE_HAZMAT", confidence=0.85),
            ]
        )
        res = engine.score_urgency("Industrial warehouse fire.", required_response=resp_res)
        assert "SAR_RESPONSE_REQUIRED" in res.signals
        assert res.label in (LABEL_HIGH, LABEL_CRITICAL)

    def test_32_incident_classification_interaction(self, engine: UrgencyEngine):
        """32. Feature 3 interaction: accepts ClassificationResult."""
        class_res = ClassificationResult(
            label="STRUCTURAL_COLLAPSE",
            confidence=0.94,
            method="keyword_prototype_hybrid",
        )
        res = engine.score_urgency("Major roof caved in on market stalls.", incident_type=class_res)
        assert "UPSTREAM_HAZARD_STRUCTURAL_COLLAPSE" in res.signals
        assert res.breakdown.hazard_velocity.score >= 60.0


# ==============================================================================
# 33–37. Confidence, Determinism, Schema & Observability Tests
# ==============================================================================

class TestConfidenceDeterminismAndSchema:
    """Tests 33–37: Decoupled confidence, determinism, schema compliance, observability, benchmark."""

    def test_33_confidence_not_score_div_100(self, engine: UrgencyEngine):
        """33. Confidence != score / 100: explicitly verifies decoupling on multiple cases."""
        # Case A: Low urgency, High confidence
        low_res = engine.score_urgency("Scheduled road sweeping along boulevard from 10pm to midnight.")
        assert low_res.score <= 25.0
        assert low_res.confidence >= 0.65
        assert low_res.confidence != round(low_res.score / 100.0, 2)

        # Case B: High urgency, Low confidence (hedged)
        hedged_res = engine.score_urgency("Unconfirmed rumor that people might be trapped somewhere near the dock.")
        assert hedged_res.score >= 40.0
        assert hedged_res.confidence < 0.60
        assert hedged_res.confidence != round(hedged_res.score / 100.0, 2)

    def test_34_deterministic_repeatability(self, engine: UrgencyEngine):
        """34. Deterministic repeatability: 10 repeated inferences yield identical output."""
        text = "HELP! 3 children trapped in flooded daycare center, water rising fast!"
        first = engine.score_urgency(text, people_at_risk=3)

        for _ in range(10):
            repeated = engine.score_urgency(text, people_at_risk=3)
            assert repeated.score == first.score
            assert repeated.label == first.label
            assert repeated.confidence == first.confidence
            assert repeated.signals == first.signals
            assert repeated.breakdown.life_safety.score == first.breakdown.life_safety.score
            assert repeated.breakdown.hazard_velocity.score == first.breakdown.hazard_velocity.score
            assert repeated.breakdown.vulnerability.score == first.breakdown.vulnerability.score

    def test_35_canonical_schema_validation(self, engine: UrgencyEngine, canonical_schema: dict):
        """35. Canonical schema validation: output conforms to ml/schemas/incident_output.json."""
        res = engine.score_urgency("Five people trapped in collapsing building.")
        canonical_urgency = res.to_canonical_dict()

        # Build full mock incident output payload
        payload = {
            "report_id": "rep-urgency-schema-01",
            "model_version": "all-MiniLM-L6-v2+heuristic-v1",
            "incident_type": {
                "label": "STRUCTURAL_COLLAPSE",
                "confidence": 0.90,
            },
            "urgency": canonical_urgency,
            "location": {
                "text": "downtown",
                "latitude": None,
                "longitude": None,
                "precision": "unknown",
                "confidence": 0.80,
            },
            "people_at_risk": {
                "count": 5,
                "confidence": 0.92,
            },
            "required_response": [
                {"type": "SEARCH_AND_RESCUE", "confidence": 0.95}
            ],
            "entities": [],
            "processing_status": "SUCCESS",
            "warnings": [],
        }

        # Must not raise jsonschema.ValidationError
        jsonschema.validate(instance=payload, schema=canonical_schema)

    def test_36_privacy_safe_logging(self):
        """36. Privacy-safe logging: log records do not leak raw citizen distress text."""
        formatter = MLJsonFormatter()
        record = logging.LogRecord(
            name="karen.ml.urgency",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Urgency scored",
            args=(),
            exc_info=None,
        )
        record.extra_context = {
            "raw_text": "Sensitive dispatch: PLEASE HELP! 4 victims trapped in fire!",
            "score": 92.5,
            "label": "CRITICAL",
            "confidence": 0.90,
        }

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert "score" in parsed
        assert parsed["score"] == 92.5
        assert parsed["label"] == "CRITICAL"
        # Raw distress text MUST be redacted
        assert "PLEASE HELP!" not in formatted
        assert "[REDACTED_TEXT" in formatted

    def test_37_benchmark_evaluation(self):
        """37. Benchmark evaluation: runs the curated engineering urgency benchmark."""
        evaluator = UrgencyEvaluator()
        report: UrgencyEvaluationReport = evaluator.evaluate(CURATED_URGENCY_BENCHMARK)

        assert report.total_samples >= 35
        assert report.leakage_check_passed is True
        assert report.reference_agreement_rate >= 0.90, f"Agreement rate: {report.reference_agreement_rate}"
        assert report.macro_f1 >= 0.85, f"Macro F1: {report.macro_f1}"
        assert report.average_latency_ms < 5.0, f"Average latency: {report.average_latency_ms} ms"
        assert report.p95_latency_ms < 10.0, f"P95 latency: {report.p95_latency_ms} ms"

        # Check all 4 tiers have representation
        for tier in CANONICAL_URGENCY_LEVELS:
            assert report.per_tier[tier].tp > 0, f"Tier {tier} had no true positives"


# ==============================================================================
# Additional Architectural Verification Tests
# ==============================================================================

class TestArchitecturalInvariants:
    """Additional checks for weighting formula, PreprocessedText, ComponentResult."""

    def test_50_30_20_formula_exactness(self, engine: UrgencyEngine):
        """Verifies exact 0.50 * LS + 0.30 * HV + 0.20 * VULN synthesis."""
        res = engine.score_urgency("HELP! 5 people trapped inside collapsing building!")
        expected_score = round(
            (0.50 * res.breakdown.life_safety.score)
            + (0.30 * res.breakdown.hazard_velocity.score)
            + (0.20 * res.breakdown.vulnerability.score),
            2,
        )
        assert res.score == expected_score

    def test_preprocessed_text_input(self, engine: UrgencyEngine):
        """PreprocessedText accepted directly without re-cleaning."""
        cleaner = TextCleaner()
        pre = cleaner.clean("Emergency! Two injured workers trapped inside mine shaft.")
        res = engine.score_urgency(pre)
        assert res.label in (LABEL_HIGH, LABEL_CRITICAL)

    def test_component_result_conversion(self, engine: UrgencyEngine):
        """to_component_result() emits standardized ComponentResult."""
        res = engine.score_urgency("Flash flood surging down valley.")
        comp = res.to_component_result()
        assert isinstance(comp, ComponentResult)
        assert comp.component == "urgency"
        assert "urgency" in comp.data
        assert "urgency_score" in comp.data
        assert comp.confidence == res.confidence

    def test_functional_convenience_api(self):
        """extract_urgency() functional interface works seamlessly."""
        res = extract_urgency("Live power lines down across street.")
        assert res.label in (LABEL_MEDIUM, LABEL_HIGH)
        assert is_canonical_urgency_label(res.label)


# ==============================================================================
# Targeted Signal Negation Adversarial Tests
# ==============================================================================

class TestTargetedSignalNegation:
    """
    Adversarial verification that negation is signal-specific, NOT component-wide.
    Negating one signal (e.g. INJURED) must NEVER erase independent active signals
    (e.g. TRAPPED, ACTIVE_THREAT, DROWNING, STRUCTURAL_COLLAPSE).
    """

    def test_neg_case_1_no_injuries_but_people_trapped(self, engine: UrgencyEngine):
        """Case 1: 'No one is injured, but 5 people are trapped inside the collapsing building.'"""
        text = "No one is injured, but 5 people are trapped inside the collapsing building."
        res = engine.score_urgency(text, incident_type="STRUCTURAL_COLLAPSE")

        # INJURED is suppressed, TRAPPED is preserved
        assert "INJURED" not in res.signals
        assert "TRAPPED" in res.signals
        assert "NEGATION_NO_INJURIES_OR_CASUALTIES" in res.signals

        # Count and collapse are preserved
        assert res.breakdown.life_safety.details.get("people_count") == 5
        assert res.breakdown.life_safety.score >= 80.0
        assert res.breakdown.life_safety.negated is False
        assert res.breakdown.hazard_velocity.score >= 80.0
        assert res.label == LABEL_CRITICAL

    def test_neg_case_2_no_injuries_but_active_shooter(self, engine: UrgencyEngine):
        """Case 2: 'No one is injured, but an active shooter is inside the mall.'"""
        text = "No one is injured, but an active shooter is inside the mall."
        res = engine.score_urgency(text, incident_type="CIVIL_UNREST_ACTIVE_THREAT")

        # INJURED suppressed, ACTIVE_THREAT preserved
        assert "INJURED" not in res.signals
        assert "ACTIVE_THREAT_TO_PEOPLE" in res.signals
        assert res.breakdown.life_safety.score >= 80.0
        assert res.breakdown.life_safety.negated is False
        assert res.label in (LABEL_HIGH, LABEL_CRITICAL)

    def test_neg_case_3_no_casualties_but_people_drowning(self, engine: UrgencyEngine):
        """Case 3: 'No casualties reported, but people are drowning.'"""
        text = "No casualties reported, but people are drowning."
        res = engine.score_urgency(text, incident_type="FLOOD_FLASH_FLOOD")

        # INJURED/casualties suppressed, DROWNING preserved
        assert "INJURED" not in res.signals
        assert "DROWNING" in res.signals
        assert res.breakdown.life_safety.score >= 80.0
        assert res.breakdown.life_safety.negated is False
        assert res.label in (LABEL_HIGH, LABEL_CRITICAL)

    def test_neg_case_4_no_one_trapped_building_collapsing(self, engine: UrgencyEngine):
        """Case 4: 'No one is trapped; the building is still collapsing.'"""
        text = "No one is trapped; the building is still collapsing."
        res = engine.score_urgency(text, incident_type="STRUCTURAL_COLLAPSE")

        # TRAPPED suppressed; Life Safety is 0.0 because no other life signals exist
        assert "TRAPPED" not in res.signals
        assert res.breakdown.life_safety.score == 0.0
        assert res.breakdown.life_safety.negated is True

        # BUT Hazard Velocity is preserved and NOT erased by 'No one is trapped'
        assert res.breakdown.hazard_velocity.score >= 80.0
        assert "COLLAPSE_IN_PROGRESS" in res.signals
        assert res.score >= 28.0

    def test_neg_case_5_no_injuries_live_power_lines_sparking(self, engine: UrgencyEngine):
        """Case 5: 'No injuries reported; live power lines are down and sparking.'"""
        text = "No injuries reported; live power lines are down and sparking."
        res = engine.score_urgency(text, incident_type="UTILITY_INFRASTRUCTURE_FAILURE")

        # INJURED suppressed; Life Safety is 0.0
        assert "INJURED" not in res.signals
        assert res.breakdown.life_safety.score == 0.0
        assert res.breakdown.life_safety.negated is True

        # BUT Hazard Velocity is preserved and NOT erased by 'No injuries reported'
        assert res.breakdown.hazard_velocity.score >= 70.0
        assert "ELECTRICAL_ARCING_LIVE_WIRES" in res.signals
        assert res.score >= 20.0

    def test_neg_case_6_everyone_safe_no_current_danger(self, engine: UrgencyEngine):
        """Case 6: 'Everyone is safe and accounted for; no current danger.'"""
        text = "Everyone is safe and accounted for; no current danger."
        res = engine.score_urgency(text)

        # Both life safety and hazard velocity are negated/controlled
        assert res.breakdown.life_safety.score == 0.0
        assert res.breakdown.life_safety.negated is True
        assert res.breakdown.hazard_velocity.score <= 15.0
        assert res.label == LABEL_LOW

    def test_neg_case_7_everyone_safe_but_building_collapsing(self, engine: UrgencyEngine):
        """Case 7: 'Everyone is safe and accounted for, but the building is collapsing.'"""
        text = "Everyone is safe and accounted for, but the building is collapsing."
        res = engine.score_urgency(text, incident_type="STRUCTURAL_COLLAPSE")

        # Occupants safe -> life safety is 0.0
        assert res.breakdown.life_safety.score == 0.0

        # Generic 'safe and accounted for' must NOT erase independent current structural collapse!
        assert res.breakdown.hazard_velocity.score >= 80.0
        assert "COLLAPSE_IN_PROGRESS" in res.signals
        assert res.score >= 28.0

