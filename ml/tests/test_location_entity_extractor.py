"""
Karen's Ear — Comprehensive Unit & Integration Tests for Location & Entity Extraction.

Covers Feature 5 requirements, architectural invariants, and all 26 prompt scenarios:
1. "Three people trapped inside a bus near Rasulgarh flyover."
2. "Fire near Rasulgarh flyover." (lat/lon null)
3. "Fire at Patia." (location extracted)
4. "Crash on NH16 near Patia." (route/location entities)
5. "Fire behind the railway station." (facility entity)
6. "Smoke from the transformer beside the school." (infrastructure/facility)
7. "Building 42 is on fire." (reject 42)
8. "Room 204 is filled with smoke." (reject 204)
9. "Call 112 immediately." (no fabricated location)
10. Famous/known location name: coordinates MUST remain null
11. Approximate marker: precision = "approximate"
12. Exact textual marker: precision = "exact"
13. Multiple locations: origin and secondary spread preserved
14. No location: "Three people are trapped inside a bus." -> location text null, bus is VEHICLE
15. Multiple entity types in one sentence
16. Lowercase/uppercase variation
17. Punctuation variation
18. Empty input handling
19. Malformed input handling
20. NER model unavailable / missing weights
21. Deterministic fallback behavior
22. Confidence score bounds [0.0, 1.0]
23. Entity type validity against allowed domain types
24. Canonical schema validation (jsonschema validation against incident_output.json)
25. Privacy-safe logging (no raw text leaked)
26. Coordinate hallucination regression (ensures coordinates NEVER populated from memory)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import jsonschema
import pytest

from ml.config import MLConfig, get_ml_config
from ml.extraction.location_entity_extractor import (
    EntityMention,
    GazetteerConfig,
    LocationEntityExtractor,
    LocationEntityResult,
    LocationPrediction,
    extract_location_and_entities,
)
from ml.extraction.people_risk_extractor import extract_people_at_risk
from ml.preprocessing.text_cleaner import TextCleaner
from ml.tests.fixtures.ner_benchmark import NER_BENCHMARK_DATASET


# Path to canonical incident output JSON schema
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "incident_output.json"


@pytest.fixture(scope="module")
def canonical_schema() -> dict:
    """Loads the canonical incident output JSON schema."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def extractor() -> LocationEntityExtractor:
    """Provides a freshly instantiated LocationEntityExtractor."""
    return LocationEntityExtractor()


# ==============================================================================
# Prompt Core Scenarios 1 - 14
# ==============================================================================

class TestCoreScenarios:
    """Tests covering primary prompt requirements 1 through 14."""

    def test_01_three_people_trapped_bus_rasulgarh_flyover(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Three people trapped inside a bus near Rasulgarh flyover.'
        Requires:
        - location.text contains 'Rasulgarh flyover'
        - bus is VEHICLE
        - coordinates remain null
        """
        text = "Three people trapped inside a bus near Rasulgarh flyover."
        res = extractor.extract(text, report_id="test_01")

        assert res.location.text is not None
        assert "Rasulgarh flyover" in res.location.text
        assert res.location.latitude is None
        assert res.location.longitude is None
        assert res.location.precision == "approximate"
        assert res.location.confidence is not None
        assert 0.80 <= res.location.confidence <= 1.0

        entity_types = {e.text.lower(): e.type for e in res.entities}
        assert "bus" in entity_types
        assert entity_types["bus"] == "VEHICLE"

    def test_02_fire_near_rasulgarh_flyover(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Fire near Rasulgarh flyover.'
        Requires location extracted and lat/lon strictly null.
        """
        text = "Fire near Rasulgarh flyover."
        res = extractor.extract(text)

        assert res.location.text == "Rasulgarh flyover"
        assert res.location.latitude is None
        assert res.location.longitude is None
        assert res.location.precision == "approximate"
        assert res.location.confidence is not None

    def test_03_fire_at_patia(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Fire at Patia.'
        Requires location 'Patia' extracted with exact precision.
        """
        text = "Fire at Patia."
        res = extractor.extract(text)

        assert res.location.text == "Patia"
        assert res.location.precision == "exact"
        assert res.location.latitude is None
        assert res.location.longitude is None

    def test_04_crash_on_nh16_near_patia(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Crash on NH16 near Patia.'
        Requires route/location entities extracted appropriately.
        """
        text = "Crash on NH16 near Patia."
        res = extractor.extract(text)

        assert res.location.text is not None
        assert "NH16" in res.location.text
        assert "Patia" in res.location.text
        assert res.location.precision == "approximate"

        entities_dict = {e.text.upper(): e.type for e in res.entities}
        assert "NH16" in entities_dict
        assert entities_dict["NH16"] == "ROAD"
        assert any(e.type == "LOCATION" and "PATIA" in e.text.upper() for e in res.entities)

    def test_05_fire_behind_railway_station(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Fire behind the railway station.'
        Requires location and facility entity.
        """
        text = "Fire reported behind the railway station."
        res = extractor.extract(text)

        assert res.location.text == "railway station"
        assert res.location.precision == "approximate"
        assert any(e.text.lower() == "railway station" and e.type == "FACILITY" for e in res.entities)

    def test_06_smoke_from_transformer_beside_school(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Smoke coming from the transformer beside the school.'
        Requires infrastructure (transformer) and facility (school) entities.
        """
        text = "Smoke coming from the transformer beside the school."
        res = extractor.extract(text)

        assert res.location.text is not None
        assert "school" in res.location.text.lower() or "transformer" in res.location.text.lower()
        entity_types = {e.text.lower(): e.type for e in res.entities}
        assert "transformer" in entity_types
        assert entity_types["transformer"] == "INFRASTRUCTURE"
        assert "school" in entity_types
        assert entity_types["school"] == "FACILITY"

    def test_07_building_42_is_on_fire(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Building 42 is on fire.'
        Negative guard: do NOT extract '42' as a location.
        """
        text = "Building 42 is on fire."
        res = extractor.extract(text)

        assert res.location.text is None
        assert res.location.precision == "unknown"
        assert res.location.confidence is None
        assert not any(e.text == "42" for e in res.entities)

    def test_08_room_204_filled_with_smoke(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Room 204 is filled with smoke.'
        Negative guard: do NOT treat '204' as a location.
        """
        text = "Room 204 is filled with smoke."
        res = extractor.extract(text)

        assert res.location.text is None
        assert res.location.precision == "unknown"
        assert res.location.confidence is None
        assert not any(e.text == "204" for e in res.entities)

    def test_09_call_112_immediately(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Call 112 immediately.'
        Negative guard: do NOT treat '112' as a location.
        """
        text = "Call 112 immediately."
        res = extractor.extract(text)

        assert res.location.text is None
        assert res.location.precision == "unknown"
        assert not any(e.text == "112" for e in res.entities)

    def test_10_famous_location_coordinates_remain_null(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Rasulgarh flyover is blocked.'
        Hard invariant: coordinates MUST remain null even for famous locations.
        """
        text = "Rasulgarh flyover is blocked."
        res = extractor.extract(text)

        assert res.location.text is not None
        assert "Rasulgarh flyover" in res.location.text
        assert res.location.latitude is None
        assert res.location.longitude is None

    def test_11_approximate_marker_precision(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'near Rasulgarh flyover'
        Requires precision = 'approximate'.
        """
        text = "Accident near Rasulgarh flyover."
        res = extractor.extract(text)

        assert res.location.precision == "approximate"

    def test_12_exact_textual_marker_precision(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'at Rasulgarh flyover'
        Requires precision = 'exact'.
        """
        text = "Accident at Rasulgarh flyover."
        res = extractor.extract(text)

        assert res.location.precision == "exact"

    def test_13_multiple_locations_preservation(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Fire started near Patia and spread toward Rasulgarh.'
        Requires meaningful locations are not silently lost:
        - Primary incident location is Patia
        - Rasulgarh is preserved in secondary_locations and entities
        """
        text = "Fire started near Patia and spread toward Rasulgarh."
        res = extractor.extract(text)

        assert res.location.text == "Patia"
        assert res.location.precision == "approximate"
        assert any(e.text.lower() == "rasulgarh" and e.type == "LOCATION" for e in res.entities)
        assert any("rasulgarh" in s.lower() for s in res.secondary_locations)

    def test_14_no_location_inside_bus(self, extractor: LocationEntityExtractor) -> None:
        """
        Input: 'Three people are trapped inside a bus.'
        Requires:
        - location.text is strictly null
        - bus is extracted as VEHICLE
        """
        text = "Three people are trapped inside a bus."
        res = extractor.extract(text)

        assert res.location.text is None
        assert res.location.precision == "unknown"
        assert res.location.confidence is None
        assert any(e.text.lower() == "bus" and e.type == "VEHICLE" for e in res.entities)


# ==============================================================================
# Robustness, Edge Cases & Operational Invariants 15 - 26
# ==============================================================================

class TestRobustnessAndInvariants:
    """Tests covering items 15 through 26."""

    def test_15_multiple_entity_types_in_one_sentence(self, extractor: LocationEntityExtractor) -> None:
        """Input with vehicle, infrastructure, facility, and road entities."""
        text = "An ambulance and a tanker collided on NH16 near Kalinga Hospital building."
        res = extractor.extract(text)

        entity_types = {e.type for e in res.entities}
        assert "VEHICLE" in entity_types
        assert "ROAD" in entity_types
        assert "FACILITY" in entity_types or "INFRASTRUCTURE" in entity_types

    def test_16_lowercase_uppercase_variation(self, extractor: LocationEntityExtractor) -> None:
        """Verifies case insensitivity for entity matching and location extraction."""
        text_upper = "ACCIDENT NEAR RASULGARH FLYOVER INVOLVING A BUS."
        text_lower = "accident near rasulgarh flyover involving a bus."

        res_upper = extractor.extract(text_upper)
        res_lower = extractor.extract(text_lower)

        assert res_upper.location.text is not None
        assert res_lower.location.text is not None
        assert res_upper.location.precision == res_lower.location.precision == "approximate"
        assert any(e.type == "VEHICLE" for e in res_upper.entities)
        assert any(e.type == "VEHICLE" for e in res_lower.entities)

    def test_17_punctuation_variation(self, extractor: LocationEntityExtractor) -> None:
        """Handles exclamation marks, ellipses, and commas cleanly."""
        text = "HELP!!! Fire near Patia, hurry... spreading fast!!!"
        res = extractor.extract(text)

        assert res.location.text == "Patia"
        assert res.location.precision == "approximate"
        assert res.location.latitude is None

    def test_18_empty_input(self, extractor: LocationEntityExtractor) -> None:
        """Empty or whitespace input must degrade safely with status PARTIAL."""
        res_empty = extractor.extract("")
        res_spaces = extractor.extract("     \n\t  ")

        assert res_empty.location.text is None
        assert res_empty.location.precision == "unknown"
        assert res_empty.processing_status == "PARTIAL"
        assert len(res_empty.warnings) > 0

        assert res_spaces.location.text is None
        assert res_spaces.location.precision == "unknown"

    def test_19_malformed_input(self, extractor: LocationEntityExtractor) -> None:
        """Very short or symbol-only inputs should not throw unhandled exceptions."""
        res_symbols = extractor.extract("@#$%^&*()_+=-")
        assert res_symbols.location.text is None
        assert res_symbols.location.precision == "unknown"

    def test_20_ner_model_unavailable(self) -> None:
        """When an optional NER model cannot be loaded, pipeline logs warning and continues."""
        config = MLConfig(ner_model_name="nonexistent/fake-ner-model-xyz")
        extractor = LocationEntityExtractor(config=config)

        res = extractor.extract("Fire near Rasulgarh flyover.")
        assert res.location.text == "Rasulgarh flyover"
        assert res.processing_status == "SUCCESS"

    def test_21_deterministic_fallback(self) -> None:
        """Explicitly tests purely deterministic fallback when NER is disabled or returns empty."""
        config = MLConfig(ner_model_name=None)
        extractor = LocationEntityExtractor(config=config)

        res = extractor.extract("Crash on NH16 near Patia.")
        assert res.location.text is not None
        assert "NH16" in res.location.text
        assert any(e.type == "ROAD" for e in res.entities)

    def test_22_confidence_bounds(self, extractor: LocationEntityExtractor) -> None:
        """All confidence scores must reside strictly in [0.0, 1.0]."""
        for sample in NER_BENCHMARK_DATASET:
            res = extractor.extract(sample.text)
            if res.location.confidence is not None:
                assert 0.0 <= res.location.confidence <= 1.0, f"Location confidence out of bounds: {res.location.confidence}"
            for ent in res.entities:
                if ent.confidence is not None:
                    assert 0.0 <= ent.confidence <= 1.0, f"Entity confidence out of bounds: {ent.confidence}"

    def test_23_entity_type_validity(self, extractor: LocationEntityExtractor) -> None:
        """Validates that extracted entity types belong to the recognized taxonomy."""
        allowed_types = {
            "LOCATION", "VEHICLE", "INFRASTRUCTURE", "FACILITY",
            "ROAD", "LANDMARK", "PERSON", "ORGANIZATION", "HAZARD",
        }
        for sample in NER_BENCHMARK_DATASET:
            res = extractor.extract(sample.text)
            for ent in res.entities:
                assert ent.type in allowed_types, f"Invalid entity type: {ent.type} in sample {sample.sample_id}"

    def test_24_canonical_schema_validation(
        self,
        extractor: LocationEntityExtractor,
        canonical_schema: dict,
    ) -> None:
        """
        Validates that extracted location and entities seamlessly integrate into
        the canonical machine-readable ML contract (ml/schemas/incident_output.json).
        """
        text = "Three people trapped inside a bus near Rasulgarh flyover."
        res = extractor.extract(text, report_id="rep-schema-01")

        # Assemble a minimal complete payload matching the schema
        payload = {
            "report_id": "rep-schema-01",
            "model_version": "all-MiniLM-L6-v2+heuristic-v1",
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.90},
            "urgency": {"label": "CRITICAL", "confidence": 0.85},
            "location": res.location.to_canonical_dict(),
            "people_at_risk": {"count": 3, "confidence": 0.92},
            "required_response": [{"type": "SEARCH_AND_RESCUE", "confidence": 0.90}],
            "entities": [ent.to_canonical_dict() for ent in res.entities],
            "processing_status": res.processing_status,
            "warnings": res.warnings,
        }

        # Should validate without raising jsonschema.ValidationError
        jsonschema.validate(instance=payload, schema=canonical_schema)

    def test_25_privacy_safe_logging(self, extractor: LocationEntityExtractor) -> None:
        """Verifies that structured logger does not log unredacted citizen dispatch text."""
        with patch.object(extractor.logger, "info") as mock_info:
            extractor.extract("Private citizen trapped near Rasulgarh flyover.", report_id="rep-priv-01")
            mock_info.assert_called()
            # Inspect extra arguments passed to logger
            _, kwargs = mock_info.call_args
            extra = kwargs.get("extra", {})
            # Ensure raw text is not a key in extra
            assert "raw_text" not in extra
            assert "text" not in extra

    def test_26_coordinate_hallucination_regression(self, extractor: LocationEntityExtractor) -> None:
        """
        Hard invariant: Ensure NO test can pass by returning known coordinates from memory.
        Even for iconic or mapped landmarks, lat/lon must be None.
        """
        iconic_locations = [
            "Fire at Rasulgarh flyover.",
            "Waterlogging at Patia square.",
            "Accident on Master Canteen Road.",
            "Disaster near Khandagiri caves.",
            "Emergency at Baramunda bus stand.",
            "Flooding inside Cuttack Medical College.",
        ]

        for dispatch in iconic_locations:
            res = extractor.extract(dispatch)
            assert res.location.latitude is None, f"Hallucinated latitude for '{dispatch}': {res.location.latitude}"
            assert res.location.longitude is None, f"Hallucinated longitude for '{dispatch}': {res.location.longitude}"


# ==============================================================================
# Feature 4 + Feature 5 Integration Tests
# ==============================================================================

class TestFeatureIntegration:
    """Verifies seamless coexistence of Feature 4 (People-at-Risk) and Feature 5 (Location & Entity)."""

    def test_coexistence_three_people_trapped_bus_rasulgarh(self) -> None:
        """
        Input: 'Three people trapped inside a bus near Rasulgarh flyover.'
        Feature 4: count = 3, confidence = 0.92, signals include TRAPPED
        Feature 5: location.text = 'Rasulgarh flyover', bus = VEHICLE, Rasulgarh flyover = LOCATION
        """
        text = "Three people trapped inside a bus near Rasulgarh flyover."

        risk_res = extract_people_at_risk(text, report_id="rep-combo-01")
        loc_res = extract_location_and_entities(text, report_id="rep-combo-01")

        # Feature 4 invariants
        assert risk_res.count == 3
        assert "TRAPPED" in risk_res.signals

        # Feature 5 invariants
        assert loc_res.location.text is not None
        assert "Rasulgarh flyover" in loc_res.location.text
        assert loc_res.location.latitude is None
        assert loc_res.location.longitude is None

        entity_types = {e.text.lower(): e.type for e in loc_res.entities}
        assert "bus" in entity_types
        assert entity_types["bus"] == "VEHICLE"

    def test_component_result_generation(self, extractor: LocationEntityExtractor) -> None:
        """Verifies that to_component_result() emits a valid ComponentResult object."""
        text = "Two trucks collided on the highway near Patia."
        res = extractor.extract(text, report_id="rep-comp-01")

        comp = res.to_component_result()
        assert comp.component == "location_and_entities"
        assert comp.status == "SUCCESS"
        assert "location" in comp.data
        assert "entities" in comp.data
        assert comp.data["location"]["latitude"] is None
        assert comp.data["location"]["longitude"] is None


# ==============================================================================
# Gazetteer Extension Tests
# ==============================================================================

class TestGazetteerExtension:
    """Verifies that operators can extend the gazetteer dynamically without modifying code."""

    def test_custom_gazetteer_extension(self) -> None:
        """Extends gazetteer with custom local town and vehicle names."""
        custom_gaz = GazetteerConfig.default().extend(
            vehicles=["hovercraft", "skidoo"],
            local_names=["jatni", "khurda road"],
        )

        extractor = LocationEntityExtractor(gazetteer=custom_gaz)

        text = "A hovercraft was spotted near Jatni."
        res = extractor.extract(text)

        assert res.location.text is not None
        assert "Jatni" in res.location.text or "jatni" in res.location.text.lower()
        entity_types = {e.text.lower(): e.type for e in res.entities}
        assert "hovercraft" in entity_types
        assert entity_types["hovercraft"] == "VEHICLE"


# ==============================================================================
# Benchmark Dataset Verification Test
# ==============================================================================

class TestBenchmarkDatasetRegression:
    """Runs the extractor over the entire 30-sample curated benchmark dataset."""

    def test_benchmark_dataset_accuracy_and_rejection(self, extractor: LocationEntityExtractor) -> None:
        """
        Validates high-level expectations on all 30 curated benchmark samples:
        - 10 negative samples produce location text = None and precision = 'unknown'
        - Positive samples extract expected locations without coordinate hallucination
        """
        for sample in NER_BENCHMARK_DATASET:
            res = extractor.extract(sample.text)

            # Coordinate invariant on all samples
            assert res.location.latitude is None
            assert res.location.longitude is None

            if sample.is_negative:
                assert res.location.text is None, f"Expected None for negative sample {sample.sample_id}, got: '{res.location.text}'"
                assert res.location.precision == "unknown"
            else:
                assert res.location.text is not None, f"Expected location for sample {sample.sample_id}, got None"
                assert res.location.precision in ("exact", "approximate")
                # Expected location should overlap with extracted location text
                exp_clean = sample.expected_location.lower()
                got_clean = res.location.text.lower()
                assert exp_clean in got_clean or got_clean in exp_clean, (
                    f"Mismatch in sample {sample.sample_id}: expected '{sample.expected_location}', got '{res.location.text}'"
                )
