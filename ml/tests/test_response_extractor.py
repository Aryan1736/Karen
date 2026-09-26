"""
Karen's Ear — Required-Response Extractor Comprehensive Test Suite.

Covers Feature 6 requirements, architectural invariants, and all 21+ prompt verification items:
1. Each of the five canonical categories individually.
2. All 6 mandatory multi-label examples.
3. Negative keyword examples (avoiding naive keyword false positives).
4. Explicit negation patterns.
5. Uncertainty handling and confidence reduction.
6. Empty input handling.
7. Malformed input handling.
8. No-response / general input handling (producing []).
9. Confidence bounds [0.0, 1.0].
10. Independent confidence per label.
11. Duplicate label prevention.
12. Deterministic canonical output ordering.
13. Canonical schema validation (against ml/schemas/incident_output.json).
14. Privacy-safe structured logging (no raw distress text leaked).
15. Feature 4 (People-at-Risk) interaction (no response inferred from count alone).
16. Feature 5 (Location & Entity) interaction (no response inferred from location alone).
17. Feature 3 (Incident Classification) interaction.
18. No forced category behavior.
19. Mixed evidence (3-label scenario).
20. Conflicting / multi-hazard evidence.
21. Multi-label exact-set evaluation and benchmark execution.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import jsonschema
import pytest

from ml.config import (
    CANONICAL_RESPONSE_TYPES,
    ComponentResult,
    MLConfig,
    get_ml_config,
)
from ml.exceptions import MLInferenceError, MLInputError
from ml.extraction.location_entity_extractor import extract_location_and_entities
from ml.extraction.people_risk_extractor import extract_people_at_risk
from ml.logging_utils import MLJsonFormatter
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner
from ml.response.evaluator import MultiLabelEvaluationReport, ResponseEvaluator
from ml.response.response_extractor import (
    RequiredResponseExtractor,
    ResponseEvidence,
    ResponseExtractionResult,
    ResponseNeed,
    extract_required_response,
)
from ml.response.taxonomy import (
    RESPONSE_TAXONOMY_CATALOG,
    ResponseCategoryDefinition,
    get_response_definition,
    is_canonical_response_type,
)
from ml.tests.fixtures.response_benchmark import (
    RESPONSE_BENCHMARK_DATASET,
    ResponseBenchmarkSample,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "incident_output.json"


@pytest.fixture(scope="module")
def canonical_schema() -> dict:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def extractor() -> RequiredResponseExtractor:
    return RequiredResponseExtractor()


# ==============================================================================
# 1. Individual Canonical Categories
# ==============================================================================

class TestCanonicalCategoriesIndividual:
    """Verifies that each of the five canonical categories is extracted accurately."""

    def test_search_and_rescue_individual(self, extractor: RequiredResponseExtractor):
        text = "Four people are trapped under rubble following the roof collapse."
        res = extractor.extract(text)
        types = [r.type for r in res.responses]
        assert types == ["SEARCH_AND_RESCUE"]
        assert res.responses[0].confidence is not None
        assert res.responses[0].confidence >= 0.85

    def test_medical_ems_individual(self, extractor: RequiredResponseExtractor):
        text = "Three people are bleeding heavily and need immediate medical attention."
        res = extractor.extract(text)
        types = [r.type for r in res.responses]
        assert types == ["MEDICAL_EMS"]
        assert res.responses[0].confidence is not None
        assert res.responses[0].confidence >= 0.85

    def test_fire_hazmat_individual(self, extractor: RequiredResponseExtractor):
        text = "The commercial warehouse is on fire with flames shooting from the roof."
        res = extractor.extract(text)
        types = [r.type for r in res.responses]
        assert types == ["FIRE_HAZMAT"]
        assert res.responses[0].confidence is not None
        assert res.responses[0].confidence >= 0.85

    def test_police_security_individual(self, extractor: RequiredResponseExtractor):
        text = "Armed person inside the shopping center threatening shoppers with a firearm."
        res = extractor.extract(text)
        types = [r.type for r in res.responses]
        assert types == ["POLICE_SECURITY"]
        assert res.responses[0].confidence is not None
        assert res.responses[0].confidence >= 0.85

    def test_public_works_utility_individual(self, extractor: RequiredResponseExtractor):
        text = "Downed power lines have fallen across the road sparking dangerously."
        res = extractor.extract(text)
        types = [r.type for r in res.responses]
        assert types == ["PUBLIC_WORKS_UTILITY"]
        assert res.responses[0].confidence is not None
        assert res.responses[0].confidence >= 0.85


# ==============================================================================
# 2. Mandatory Multi-Label Examples
# ==============================================================================

class TestMandatoryMultiLabelExamples:
    """Verifies all mandatory multi-label scenarios specified in the prompt."""

    def test_mandatory_1_trapped_and_bleeding(self, extractor: RequiredResponseExtractor):
        """'People trapped under rubble and three are bleeding.' => SEARCH_AND_RESCUE + MEDICAL_EMS"""
        text = "People trapped under rubble and three are bleeding."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert types == {"SEARCH_AND_RESCUE", "MEDICAL_EMS"}

    def test_mandatory_2_trapped_burning_building(self, extractor: RequiredResponseExtractor):
        """'Three people trapped inside a burning building.' => SEARCH_AND_RESCUE + FIRE_HAZMAT"""
        text = "Three people trapped inside a burning building."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert types == {"SEARCH_AND_RESCUE", "FIRE_HAZMAT"}

    def test_mandatory_3_armed_person_injured_mall(self, extractor: RequiredResponseExtractor):
        """'Armed person injured two people inside the mall.' => POLICE_SECURITY + MEDICAL_EMS"""
        text = "Armed person injured two people inside the mall."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert types == {"POLICE_SECURITY", "MEDICAL_EMS"}

    def test_mandatory_4_power_lines_driver_trapped(self, extractor: RequiredResponseExtractor):
        """'Power lines have fallen across the road and a driver is trapped in the car.' => PUBLIC_WORKS_UTILITY + SEARCH_AND_RESCUE"""
        text = "Power lines have fallen across the road and a driver is trapped in the car."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert types == {"PUBLIC_WORKS_UTILITY", "SEARCH_AND_RESCUE"}

    def test_mandatory_5_chemical_explosion_workers_injured(self, extractor: RequiredResponseExtractor):
        """'Chemical explosion injured several workers.' => FIRE_HAZMAT + MEDICAL_EMS"""
        text = "Chemical explosion injured several workers."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert types == {"FIRE_HAZMAT", "MEDICAL_EMS"}

    def test_mandatory_6_gas_leak_no_injuries(self, extractor: RequiredResponseExtractor):
        """'Gas leak reported near a school, no injuries.' => FIRE_HAZMAT (no MEDICAL_EMS)"""
        text = "Gas leak reported near a school, no injuries."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert types == {"FIRE_HAZMAT"}
        assert "MEDICAL_EMS" not in types


# ==============================================================================
# 3. Mandatory Negative Tests (Avoiding Naive Keyword Matching)
# ==============================================================================

class TestMandatoryNegativeExamples:
    """Verifies that presence of emergency vocabulary in non-emergency context does NOT trigger response."""

    def test_negative_no_one_injured(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("No one is injured.")
        assert res.responses == []

    def test_negative_no_fire_cooking_smoke(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("No fire, only smoke from cooking.")
        assert res.responses == []

    def test_negative_police_station_nearby(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("Police station is nearby.")
        assert res.responses == []

    def test_negative_hospital_nearby(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("Hospital is nearby.")
        assert res.responses == []

    def test_negative_fire_truck_parked(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("Fire truck is parked outside.")
        assert res.responses == []

    def test_negative_power_restored_yesterday(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("Power was restored yesterday.")
        assert res.responses == []

    def test_negative_no_weapons_seen(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("No weapons seen.")
        assert res.responses == []

    def test_negative_fire_extinguisher_available(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("Fire extinguisher is available in the building.")
        assert res.responses == []

    def test_negative_trapped_in_video_game(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("People are trapped in a video game.")
        assert res.responses == []


# ==============================================================================
# 4. Negation Handling
# ==============================================================================

class TestNegationHandling:
    """Verifies explicit negation suppresses only the negated category without suppressing other categories."""

    def test_negation_suppresses_medical_in_multiclause(self, extractor: RequiredResponseExtractor):
        text = "Two vehicles collided on highway, no injuries reported."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert "MEDICAL_EMS" not in types

    def test_negation_suppresses_fire_when_other_present(self, extractor: RequiredResponseExtractor):
        text = "Downed power lines on the road, no fire reported."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert "PUBLIC_WORKS_UTILITY" in types
        assert "FIRE_HAZMAT" not in types

    def test_negation_suppresses_search_rescue(self, extractor: RequiredResponseExtractor):
        text = "Building collapsed but nobody is trapped inside."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert "SEARCH_AND_RESCUE" not in types


# ==============================================================================
# 5. Uncertainty Handling & Relative Confidence
# ==============================================================================

class TestUncertaintyHandling:
    """Verifies that uncertainty markers appropriately reduce confidence scores."""

    def test_fire_explicit_vs_uncertain(self, extractor: RequiredResponseExtractor):
        explicit_res = extractor.extract("Building is on fire.")
        uncertain_res = extractor.extract("Possible fire near building.")

        assert any(r.type == "FIRE_HAZMAT" for r in explicit_res.responses)
        assert any(r.type == "FIRE_HAZMAT" for r in uncertain_res.responses)

        exp_conf = next(r.confidence for r in explicit_res.responses if r.type == "FIRE_HAZMAT")
        unc_conf = next(r.confidence for r in uncertain_res.responses if r.type == "FIRE_HAZMAT")

        assert exp_conf is not None and unc_conf is not None
        assert exp_conf > unc_conf
        assert unc_conf >= 0.50

    def test_medical_explicit_vs_uncertain(self, extractor: RequiredResponseExtractor):
        explicit_res = extractor.extract("Three people are bleeding.")
        uncertain_res = extractor.extract("People may be injured.")

        assert any(r.type == "MEDICAL_EMS" for r in explicit_res.responses)
        assert any(r.type == "MEDICAL_EMS" for r in uncertain_res.responses)

        exp_conf = next(r.confidence for r in explicit_res.responses if r.type == "MEDICAL_EMS")
        unc_conf = next(r.confidence for r in uncertain_res.responses if r.type == "MEDICAL_EMS")

        assert exp_conf is not None and unc_conf is not None
        assert exp_conf > unc_conf
        assert unc_conf >= 0.50

    def test_rescue_uncertain_someone_might_be_trapped(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("Someone might be trapped under the stairs.")
        types = [r.type for r in res.responses]
        assert "SEARCH_AND_RESCUE" in types
        conf = next(r.confidence for r in res.responses if r.type == "SEARCH_AND_RESCUE")
        assert conf is not None
        assert 0.50 <= conf < 0.85


# ==============================================================================
# 6. Empty and Malformed Inputs
# ==============================================================================

class TestEmptyAndMalformedInputs:
    """Verifies resilience and graceful degradation on invalid or unparseable inputs."""

    def test_empty_string_returns_empty_and_partial(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("")
        assert res.responses == []
        assert res.processing_status == "PARTIAL"
        assert len(res.warnings) > 0

    def test_whitespace_string_returns_empty_and_partial(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("   \n\t   ")
        assert res.responses == []
        assert res.processing_status == "PARTIAL"
        assert len(res.warnings) > 0

    def test_non_string_type_raises_ml_input_error(self, extractor: RequiredResponseExtractor):
        with pytest.raises(MLInputError, match="Input text must be str or PreprocessedText"):
            extractor.extract(12345)  # type: ignore

    def test_symbols_only_malformed_input(self, extractor: RequiredResponseExtractor):
        res = extractor.extract("!@#$%^&*()_+=-~`")
        assert res.responses == []
        assert res.processing_status in ("SUCCESS", "PARTIAL")


# ==============================================================================
# 7. No-Response / General Reports
# ==============================================================================

class TestNoResponseGeneralReports:
    """Verifies that non-emergency or general text legitimately returns an empty array []."""

    @pytest.mark.parametrize(
        "general_text",
        [
            "Traffic is slow today.",
            "Heavy rain reported.",
            "Road is wet.",
            "There is noise near the market.",
            "Clear blue skies in the morning.",
            "Meeting scheduled for 3 PM.",
        ],
    )
    def test_no_forced_category_on_general_text(self, extractor: RequiredResponseExtractor, general_text: str):
        res = extractor.extract(general_text)
        assert res.responses == []
        assert res.processing_status == "SUCCESS"


# ==============================================================================
# 8. Confidence Invariants & Independence
# ==============================================================================

class TestConfidenceInvariants:
    """Verifies bounded [0.0, 1.0] confidence and independent scoring per label."""

    def test_all_benchmark_confidence_bounded(self, extractor: RequiredResponseExtractor):
        for sample in RESPONSE_BENCHMARK_DATASET:
            res = extractor.extract(sample.text)
            for r in res.responses:
                assert r.confidence is not None
                assert 0.0 <= r.confidence <= 1.0, f"Confidence out of bounds for {sample.id}: {r.confidence}"

    def test_independent_confidence_multi_label(self, extractor: RequiredResponseExtractor):
        """In multi-label reports, categories must have independent confidence scores."""
        text = "Possible chemical leak reported and three people are severely bleeding."
        res = extractor.extract(text)
        types = {r.type: r.confidence for r in res.responses}

        assert "FIRE_HAZMAT" in types
        assert "MEDICAL_EMS" in types
        # Medical is explicit/strong; fire is hedged ("possible")
        assert types["MEDICAL_EMS"] > types["FIRE_HAZMAT"]


# ==============================================================================
# 9. Duplicate Prevention & Deterministic Canonical Ordering
# ==============================================================================

class TestOrderingAndDuplicates:
    """Verifies that results contain no duplicates and are deterministically ordered."""

    def test_no_duplicate_response_types(self, extractor: RequiredResponseExtractor):
        text = "Building on fire with flames visible and heavy smoke from another fire in the back."
        res = extractor.extract(text)
        types = [r.type for r in res.responses]
        assert len(types) == len(set(types)), "Duplicate response types emitted"

    def test_deterministic_canonical_ordering(self, extractor: RequiredResponseExtractor):
        """Outputs must be sorted strictly in CANONICAL_RESPONSE_TYPES index order."""
        text = "High-voltage power lines down, building on fire, three people injured, driver trapped."
        res = extractor.extract(text)
        indices = [CANONICAL_RESPONSE_TYPES.index(r.type) for r in res.responses]
        assert indices == sorted(indices), "Responses are not canonically sorted"

    def test_stability_across_repeated_runs(self, extractor: RequiredResponseExtractor):
        text = "Chemical explosion injured three workers and power lines are down."
        first = extractor.extract(text)
        for _ in range(5):
            repeated = extractor.extract(text)
            assert [r.type for r in repeated.responses] == [r.type for r in first.responses]
            assert [r.confidence for r in repeated.responses] == [r.confidence for r in first.responses]


# ==============================================================================
# 10. Canonical Schema Validation
# ==============================================================================

class TestCanonicalSchemaValidation:
    """Validates that RequiredResponseExtractor output conforms to incident_output.json."""

    def test_schema_compliance_multi_label(
        self,
        extractor: RequiredResponseExtractor,
        canonical_schema: dict,
    ):
        res = extractor.extract("People trapped under rubble and three are bleeding.")
        canonical_list = res.to_canonical_list()

        # Build full mock incident output payload
        payload = {
            "report_id": "rep-test-schema-01",
            "model_version": "all-MiniLM-L6-v2+heuristic-v1",
            "incident_type": {
                "label": "STRUCTURAL_COLLAPSE",
                "confidence": 0.90,
            },
            "urgency": {
                "label": "CRITICAL",
                "confidence": 0.95,
            },
            "location": {
                "text": "market",
                "latitude": None,
                "longitude": None,
                "precision": "unknown",
                "confidence": 0.80,
            },
            "people_at_risk": {
                "count": 3,
                "confidence": 0.92,
            },
            "required_response": canonical_list,
            "entities": [],
            "processing_status": "SUCCESS",
            "warnings": [],
        }

        # Must not raise jsonschema.ValidationError
        jsonschema.validate(instance=payload, schema=canonical_schema)

    def test_schema_compliance_empty_list(
        self,
        extractor: RequiredResponseExtractor,
        canonical_schema: dict,
    ):
        res = extractor.extract("Traffic is slow today.")
        payload = {
            "report_id": "rep-test-schema-02",
            "model_version": "all-MiniLM-L6-v2+heuristic-v1",
            "incident_type": {"label": None, "confidence": None},
            "urgency": {"label": "LOW", "confidence": 0.80},
            "location": {"text": None, "latitude": None, "longitude": None, "precision": "unknown", "confidence": None},
            "people_at_risk": {"count": None, "confidence": None},
            "required_response": res.to_canonical_list(),
            "entities": [],
            "processing_status": "SUCCESS",
            "warnings": [],
        }
        jsonschema.validate(instance=payload, schema=canonical_schema)


# ==============================================================================
# 11. Privacy-Safe Logging Observability
# ==============================================================================

class TestPrivacyLogging:
    """Verifies that extractor logger does not leak raw citizen distress text into logs."""

    def test_privacy_logging_no_raw_text_leak(self, extractor: RequiredResponseExtractor, caplog):
        distress_text = "SECRET_DISTRESS_TEXT: My brother is trapped under rubble and bleeding severely"
        with caplog.at_level(logging.INFO, logger="karen.ml.response"):
            extractor.extract(distress_text, report_id="rep-privacy-resp-01")

        for record in caplog.records:
            assert distress_text not in record.message
            assert "SECRET_DISTRESS_TEXT" not in record.message


# ==============================================================================
# 12. Feature Interactions (Features 3, 4, and 5)
# ==============================================================================

class TestFeatureInteractions:
    """Verifies decoupling and proper interaction with Features 3, 4, and 5."""

    def test_feature_4_count_alone_does_not_infer_response(self, extractor: RequiredResponseExtractor):
        """'20 people are inside the stadium.' -> count: 20, but required_response must be []"""
        text = "20 people are inside the stadium enjoying the concert."
        risk_res = extract_people_at_risk(text)
        resp_res = extractor.extract(text, people_at_risk_count=risk_res.count)

        assert risk_res.count == 20
        assert resp_res.responses == []

    def test_feature_4_count_with_trapped_infers_sar(self, extractor: RequiredResponseExtractor):
        """'20 people are trapped inside the stadium.' -> count: 20, SEARCH_AND_RESCUE"""
        text = "20 people are trapped inside the stadium."
        risk_res = extract_people_at_risk(text)
        resp_res = extractor.extract(text, people_at_risk_count=risk_res.count)

        assert risk_res.count == 20
        assert any(r.type == "SEARCH_AND_RESCUE" for r in resp_res.responses)

    def test_feature_4_count_with_injured_infers_medical(self, extractor: RequiredResponseExtractor):
        """'20 people are injured inside the stadium.' -> count: 20, MEDICAL_EMS"""
        text = "20 people are injured inside the stadium."
        risk_res = extract_people_at_risk(text)
        resp_res = extractor.extract(text, people_at_risk_count=risk_res.count)

        assert risk_res.count == 20
        assert any(r.type == "MEDICAL_EMS" for r in resp_res.responses)

    def test_feature_5_location_alone_does_not_infer_response(self, extractor: RequiredResponseExtractor):
        """'near Rasulgarh flyover' -> location extracted, but required_response must be []"""
        text = "Near Rasulgarh flyover."
        loc_res = extract_location_and_entities(text)
        resp_res = extractor.extract(text)

        assert loc_res.location.text is not None
        assert "Rasulgarh flyover" in loc_res.location.text
        assert resp_res.responses == []

    def test_feature_5_vehicle_and_facility_mentions_do_not_infer_response(self, extractor: RequiredResponseExtractor):
        """Static ambulance or fire station mentions do not infer response."""
        res_amb = extractor.extract("Ambulance parked outside the mall.")
        res_fire = extractor.extract("Fire station nearby on Janpath road.")

        assert res_amb.responses == []
        assert res_fire.responses == []

    def test_feature_3_incident_type_corroboration_does_not_force_label(self, extractor: RequiredResponseExtractor):
        """Incident type alone without text evidence does not force a response label."""
        text = "Clear weather observed in the evening."
        res = extractor.extract(text, incident_type="FIRE_WILDFIRE_EXPLOSION")
        assert res.responses == []


# ==============================================================================
# 13. Mixed & Complex Multi-Hazard Scenarios
# ==============================================================================

class TestComplexScenarios:
    """Verifies mixed 3-label scenarios and multi-hazard evidence."""

    def test_three_label_rescue_medical_fire(self, extractor: RequiredResponseExtractor):
        text = "Three people trapped inside a burning building, two injured."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert types == {"SEARCH_AND_RESCUE", "MEDICAL_EMS", "FIRE_HAZMAT"}

    def test_three_label_security_fire_medical(self, extractor: RequiredResponseExtractor):
        text = "Armed attacker set fire to the store and shot two patrons."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert types == {"MEDICAL_EMS", "FIRE_HAZMAT", "POLICE_SECURITY"}

    def test_transformer_exploded_and_power_lines_down(self, extractor: RequiredResponseExtractor):
        text = "Transformer exploded and power lines are down across the street."
        res = extractor.extract(text)
        types = set(r.type for r in res.responses)
        assert "PUBLIC_WORKS_UTILITY" in types
        assert "FIRE_HAZMAT" in types

    def test_component_result_generation(self, extractor: RequiredResponseExtractor):
        text = "Chemical explosion injured several workers."
        res = extractor.extract(text, report_id="rep-comp-01")
        comp = res.to_component_result()

        assert isinstance(comp, ComponentResult)
        assert comp.component == "required_response"
        assert comp.status == "SUCCESS"
        assert "required_response" in comp.data
        assert len(comp.data["required_response"]) == 2
        assert comp.confidence is not None


# ==============================================================================
# 14. Benchmark Evaluation & Exact-Set Verification
# ==============================================================================

class TestBenchmarkEvaluation:
    """Runs the 51-sample benchmark suite and verifies exact-set and multi-label metrics."""

    def test_benchmark_exact_set_and_metrics(self):
        evaluator = ResponseEvaluator()
        report: MultiLabelEvaluationReport = evaluator.evaluate(RESPONSE_BENCHMARK_DATASET)

        assert report.total_samples == 51
        assert report.leakage_check_passed is True

        # High benchmark performance expected on curated engineering test fixture
        assert report.exact_set_matches >= 49, f"Exact set matches: {report.exact_set_matches}/51"
        assert report.exact_set_match_rate >= 0.95, f"Exact set match rate: {report.exact_set_match_rate}"
        assert report.micro_precision >= 0.95, f"Micro precision: {report.micro_precision}"
        assert report.micro_recall >= 0.95, f"Micro recall: {report.micro_recall}"
        assert report.micro_f1 >= 0.95, f"Micro F1: {report.micro_f1}"
        assert report.false_positive_rate == 0.0, f"False positive rate: {report.false_positive_rate}"

        # Latency target (< 10 ms CPU per inference)
        assert report.average_latency_ms < 5.0, f"Average latency too high: {report.average_latency_ms} ms"

        # Every canonical category must have F1 >= 0.90
        for cat in CANONICAL_RESPONSE_TYPES:
            cat_m = report.per_category[cat]
            assert cat_m.f1 >= 0.90, f"Category {cat} F1 too low: {cat_m.f1}"
