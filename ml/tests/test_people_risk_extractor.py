"""
Karen's Ear — Feature 4 People-at-Risk Extraction Tests.

Validates:
- Explicit and contextual people count extraction (digits, number words, compound words)
- Hard no-hallucination policy (qualitative quantities NEVER produce numeric counts)
- Qualitative risk signals detection (TRAPPED, INJURED, MISSING, UNCONSCIOUS, DROWNING, CHILDREN, ELDERLY, PATIENTS, MULTIPLE_PEOPLE)
- Rejection of unrelated numbers (building, room, floor, highway, time, phone/emergency numbers)
- Deterministic, explainable confidence ranking (explicit > approximate > hedged)
- Principled aggregation (disjoint demographics summed vs non-disjoint preserved without blind summation)
- Schema contract compliance (canonical {count, confidence}, ComponentResult, entities)
- Error handling on empty/malformed inputs
- Determinism across repeated executions
- Privacy-safe logging without sensitive dispatch text leakage
"""

import pytest

from ml.config import ComponentResult
from ml.exceptions import MLInputError
from ml.extraction import (
    PeopleRiskExtractor,
    PeopleRiskResult,
    RiskEvidence,
    extract_people_at_risk,
)
from ml.preprocessing import TextCleaner, preprocess_report


# ==============================================================================
# 1. Minimum Mandatory Tests Codified in Specification
# ==============================================================================


def test_req_1_digits_people_trapped():
    """1. '3 people trapped' => count: 3"""
    res = extract_people_at_risk("3 people trapped")
    assert res.count == 3
    assert res.confidence is not None
    assert res.confidence >= 0.90
    assert "TRAPPED" in res.signals


def test_req_2_number_word_children():
    """2. 'five children are inside' => count: 5"""
    res = extract_people_at_risk("five children are inside")
    assert res.count == 5
    assert res.confidence is not None
    assert res.confidence >= 0.90
    assert "CHILDREN" in res.signals


def test_req_3_family_of_numeric():
    """3. 'family of 4' => count: 4"""
    res = extract_people_at_risk("family of 4")
    assert res.count == 4
    assert res.confidence is not None
    assert res.confidence >= 0.90


def test_req_3b_family_of_word():
    """3b. 'family of four' => count: 4"""
    res = extract_people_at_risk("family of four")
    assert res.count == 4
    assert res.confidence is not None


def test_req_4_passengers_injured():
    """4. '20 passengers injured' => count: 20"""
    res = extract_people_at_risk("20 passengers injured")
    assert res.count == 20
    assert res.confidence is not None
    assert "INJURED" in res.signals


def test_req_5_two_workers_missing():
    """5. 'two workers missing' => count: 2"""
    res = extract_people_at_risk("two workers missing")
    assert res.count == 2
    assert res.confidence is not None
    assert "MISSING" in res.signals


def test_req_6_one_person_unconscious():
    """6. '1 person unconscious' => count: 1"""
    res = extract_people_at_risk("1 person unconscious")
    assert res.count == 1
    assert res.confidence is not None
    assert "UNCONSCIOUS" in res.signals


def test_req_7_multiple_people_trapped():
    """7. 'multiple people trapped' => null + MULTIPLE_PEOPLE + TRAPPED"""
    res = extract_people_at_risk("multiple people trapped")
    assert res.count is None
    assert res.confidence is None
    assert "MULTIPLE_PEOPLE" in res.signals
    assert "TRAPPED" in res.signals


def test_req_8_several_people_injured():
    """8. 'several people injured' => null + qualitative signal + INJURED"""
    res = extract_people_at_risk("several people injured")
    assert res.count is None
    assert res.confidence is None
    assert "MULTIPLE_PEOPLE" in res.signals
    assert "INJURED" in res.signals


def test_req_9_many_passengers_inside():
    """9. 'many passengers inside' => count: null"""
    res = extract_people_at_risk("many passengers inside")
    assert res.count is None
    assert res.confidence is None
    assert "MULTIPLE_PEOPLE" in res.signals


def test_req_10_children_trapped_inside():
    """10. 'children are trapped inside' => null + CHILDREN + TRAPPED"""
    res = extract_people_at_risk("children are trapped inside")
    assert res.count is None
    assert res.confidence is None
    assert "CHILDREN" in res.signals
    assert "TRAPPED" in res.signals


def test_req_11_elderly_people_trapped():
    """11. 'elderly people are trapped' => null + ELDERLY + TRAPPED"""
    res = extract_people_at_risk("elderly people are trapped")
    assert res.count is None
    assert res.confidence is None
    assert "ELDERLY" in res.signals
    assert "TRAPPED" in res.signals


def test_req_12_patients_inside():
    """12. 'patients are inside' => null + PATIENTS"""
    res = extract_people_at_risk("patients are inside")
    assert res.count is None
    assert res.confidence is None
    assert "PATIENTS" in res.signals


def test_req_13_people_in_building_number():
    """13. '3 people in building 42' => count 3, NOT 42"""
    res = extract_people_at_risk("3 people in building 42")
    assert res.count == 3


def test_req_14_building_alone_on_fire():
    """14. 'Building 42 is on fire' => no people count"""
    res = extract_people_at_risk("Building 42 is on fire")
    assert res.count is None
    assert res.confidence is None


def test_req_15_call_emergency_number():
    """15. 'Call 112 immediately' => no people count"""
    res = extract_people_at_risk("Call 112 immediately")
    assert res.count is None
    assert res.confidence is None


def test_req_16_time_and_people_count():
    """16. 'At 8 PM, 3 people were trapped' => count 3, NOT 8"""
    res = extract_people_at_risk("At 8 PM, 3 people were trapped")
    assert res.count == 3
    assert "TRAPPED" in res.signals


def test_req_17_approximate_count():
    """17. 'approximately 8 people are trapped' => 8 with reduced confidence"""
    res_direct = extract_people_at_risk("8 people are trapped")
    res_approx = extract_people_at_risk("approximately 8 people are trapped")

    assert res_approx.count == 8
    assert res_approx.confidence is not None
    assert res_direct.confidence is not None
    assert res_approx.confidence < res_direct.confidence
    assert res_approx.confidence == 0.75
    assert "TRAPPED" in res_approx.signals


def test_req_18_bound_count():
    """18. 'at least 6 people injured' => 6"""
    res = extract_people_at_risk("at least 6 people injured")
    assert res.count == 6
    assert res.confidence is not None
    assert res.confidence == 0.80
    assert "INJURED" in res.signals


def test_req_19_conservative_hedged_count():
    """19. 'maybe five people' => conservative handling (5 with reduced confidence)"""
    res = extract_people_at_risk("maybe five people")
    assert res.count == 5
    assert res.confidence is not None
    assert res.confidence <= 0.65


def test_req_20_aggregation_disjoint_demographics():
    """20. '3 children and 2 adults are trapped' => test aggregation behavior (3 + 2 = 5)"""
    res = extract_people_at_risk("3 children and 2 adults are trapped")
    assert res.count == 5
    assert res.confidence is not None
    assert "CHILDREN" in res.signals
    assert "TRAPPED" in res.signals


def test_req_21_non_blind_aggregation():
    """
    21. '5 passengers injured and 2 missing' => test non-blind aggregation.
    Must NOT blindly sum to 7. Preserves defensible maximum count (5).
    """
    res = extract_people_at_risk("5 passengers injured and 2 missing")
    assert res.count == 5
    assert res.count != 7
    assert len(res.warnings) > 0
    assert "non-disjoint" in res.warnings[0].lower()
    assert "INJURED" in res.signals
    assert "MISSING" in res.signals


def test_req_22_empty_whitespace_input():
    """22. Empty/whitespace input raises MLInputError."""
    with pytest.raises(MLInputError):
        extract_people_at_risk("")

    with pytest.raises(MLInputError):
        extract_people_at_risk("   \n\t  ")


def test_req_23_malformed_input():
    """23. Malformed non-string input raises MLInputError."""
    with pytest.raises(MLInputError):
        extract_people_at_risk(None)  # type: ignore

    with pytest.raises(MLInputError):
        extract_people_at_risk(12345)  # type: ignore


def test_req_24_no_people_references():
    """24. 'Severe flooding on the highway, road completely blocked' => count: null, confidence: null"""
    res = extract_people_at_risk("Severe flooding on the highway, road completely blocked")
    assert res.count is None
    assert res.confidence is None
    assert len(res.signals) == 0


def test_req_25_mixed_numeric_and_qualitative():
    """25. Mixed numeric + qualitative signals preserves numeric count and qualitative signals."""
    res = extract_people_at_risk("3 people trapped and several others injured")
    assert res.count == 3
    assert res.confidence is not None
    assert "MULTIPLE_PEOPLE" in res.signals
    assert "TRAPPED" in res.signals
    assert "INJURED" in res.signals


# ==============================================================================
# 2. Hard No-Hallucination Invariant Tests
# ==============================================================================


@pytest.mark.parametrize(
    "phrase",
    [
        "multiple people",
        "several people",
        "many people",
        "numerous people",
        "a group of people",
        "crowd",
        "large crowd",
        "dozens of people",
        "lots of people",
        "family",
        "children",
        "passengers",
        "patients",
        "residents",
    ],
)
def test_no_hallucination_on_qualitative_phrases(phrase: str):
    """Verify that qualitative quantities and bare group nouns never produce fabricated counts."""
    res = extract_people_at_risk(f"Report: {phrase} in danger")
    assert res.count is None
    assert res.confidence is None


def test_no_hallucination_building_fire_no_people():
    """Large building fire at night with no people mentioned produces count=null."""
    res = extract_people_at_risk("Large commercial building fire at night with heavy smoke")
    assert res.count is None
    assert res.confidence is None


# ==============================================================================
# 3. Unrelated Number Rejection Tests
# ==============================================================================


def test_rejection_floor_number():
    """'Floor 5 has smoke' => count is null, 5 is rejected."""
    res = extract_people_at_risk("Floor 5 has smoke and alarms are sounding")
    assert res.count is None
    assert res.confidence is None


def test_rejection_room_number():
    """'3 people in room 204' => count is 3, NOT 204."""
    res = extract_people_at_risk("3 people in room 204")
    assert res.count == 3


def test_rejection_call_911():
    """'Call 911 immediately' => count is null."""
    res = extract_people_at_risk("Call 911 immediately")
    assert res.count is None
    assert res.confidence is None


def test_rejection_dial_108():
    """'Dial 108 for ambulance' => count is null."""
    res = extract_people_at_risk("Dial 108 for ambulance dispatch")
    assert res.count is None
    assert res.confidence is None


def test_rejection_highway_and_mile_marker():
    """Highway numbers and mile markers are not people counts."""
    res = extract_people_at_risk("Accident on Highway 101 near exit 24")
    assert res.count is None
    assert res.confidence is None


def test_rejection_distances_and_measurements():
    """Distances (e.g. 500 meters) and durations (e.g. 2 hours) are not people counts."""
    res = extract_people_at_risk("Flood water 2 meters deep for 4 hours")
    assert res.count is None
    assert res.confidence is None


# ==============================================================================
# 4. Confidence Ranking & Calibration Hierarchy
# ==============================================================================


def test_confidence_hierarchy_explicit_vs_approx_vs_hedged():
    """
    Explicit ('3 people trapped') > Approximate ('around 3 people trapped') > Hedged ('maybe 3 people trapped').
    """
    res_explicit = extract_people_at_risk("3 people trapped")
    res_approx = extract_people_at_risk("around 3 people trapped")
    res_hedged = extract_people_at_risk("maybe 3 people trapped")

    assert res_explicit.count == 3
    assert res_approx.count == 3
    assert res_hedged.count == 3

    assert res_explicit.confidence is not None
    assert res_approx.confidence is not None
    assert res_hedged.confidence is not None

    assert res_explicit.confidence > res_approx.confidence
    assert res_approx.confidence > res_hedged.confidence


def test_confidence_null_when_count_null():
    """When count is null, confidence must strictly be null."""
    res = extract_people_at_risk("Water rising fast near the bridge")
    assert res.count is None
    assert res.confidence is None


# ==============================================================================
# 5. Compound Number Words & Number Parsing
# ==============================================================================


def test_compound_number_words_hyphenated():
    """'twenty-five passengers injured' => count: 25"""
    res = extract_people_at_risk("twenty-five passengers injured")
    assert res.count == 25
    assert "INJURED" in res.signals


def test_compound_number_words_spaced():
    """'twenty five passengers injured' => count: 25"""
    res = extract_people_at_risk("twenty five passengers injured")
    assert res.count == 25


def test_large_count_hundred():
    """'one hundred passengers stranded' => count: 100"""
    res = extract_people_at_risk("one hundred passengers stranded")
    assert res.count == 100
    assert "TRAPPED" in res.signals


def test_large_count_hundred_compound():
    """'one hundred and five victims trapped' => count: 105"""
    res = extract_people_at_risk("one hundred and five victims trapped")
    assert res.count == 105


# ==============================================================================
# 6. Explicit Total Stated Over Subgroups
# ==============================================================================


def test_explicit_total_stated_preferred():
    """'Total of 10 people trapped, 3 are injured' => count: 10 (explicit total preferred)"""
    res = extract_people_at_risk("Total of 10 people trapped, 3 are injured")
    assert res.count == 10
    assert "TRAPPED" in res.signals
    assert "INJURED" in res.signals


# ==============================================================================
# 7. Additional Qualitative Indicators (DROWNING, UNCONSCIOUS)
# ==============================================================================


def test_drowning_qualitative_signal():
    """Drowning words detected as DROWNING signal."""
    res = extract_people_at_risk("People are drowning in the flood water, completely submerged")
    assert "DROWNING" in res.signals
    assert res.count is None


def test_unconscious_qualitative_signal():
    """Unconscious words detected as UNCONSCIOUS signal."""
    res = extract_people_at_risk("Victim is not responding and has no pulse")
    assert "UNCONSCIOUS" in res.signals


# ==============================================================================
# 8. Schema & Contract Integration
# ==============================================================================


def test_to_canonical_dict():
    """to_canonical_dict() strictly returns {'count': ..., 'confidence': ...}."""
    res = extract_people_at_risk("4 people trapped inside")
    canonical = res.to_canonical_dict()
    assert canonical == {"count": 4, "confidence": res.confidence}

    res_none = extract_people_at_risk("No one is inside")
    assert res_none.to_canonical_dict() == {"count": None, "confidence": None}


def test_to_component_result():
    """to_component_result() emits standardized ComponentResult."""
    res = extract_people_at_risk("3 workers missing")
    comp = res.to_component_result()
    assert isinstance(comp, ComponentResult)
    assert comp.component == "people_at_risk"
    assert comp.status == "SUCCESS"
    assert comp.data["people_at_risk"]["count"] == 3
    assert comp.confidence == res.confidence


def test_to_entities():
    """to_entities() produces valid entity tokens."""
    res = extract_people_at_risk("3 children trapped")
    entities = res.to_entities()
    assert len(entities) >= 2
    types = [e["type"] for e in entities]
    assert "VICTIM" in types
    assert "CHILDREN" in types or "TRAPPED" in types


def test_preprocessed_text_input_compatibility():
    """Accepts PreprocessedText object from Feature 2 TextCleaner."""
    cleaner = TextCleaner()
    preprocessed = cleaner.clean("   5 occupants trapped inside   ")
    res = extract_people_at_risk(preprocessed)
    assert res.count == 5
    assert "TRAPPED" in res.signals


def test_determinism_across_executions():
    """Extractor produces strictly deterministic output across repeated executions."""
    text = "Approximately 12 passengers trapped in overturned bus, 4 injured"
    res1 = extract_people_at_risk(text)
    res2 = extract_people_at_risk(text)

    assert res1.count == res2.count
    assert res1.confidence == res2.confidence
    assert res1.signals == res2.signals
    assert len(res1.evidence) == len(res2.evidence)


# ==============================================================================
# 9. Additional Prompt & Realistic Emergency Dispatch Cases
# ==============================================================================


def test_realistic_there_are_twelve_people_in_building():
    """'there are 12 people in the building' => count: 12"""
    res = extract_people_at_risk("there are 12 people in the building")
    assert res.count == 12
    assert res.confidence is not None
    assert res.confidence >= 0.90


def test_realistic_around_ten_passengers_missing():
    """'around ten passengers are missing' => count: 10 with approximation confidence"""
    res = extract_people_at_risk("around ten passengers are missing")
    assert res.count == 10
    assert res.confidence == 0.75
    assert "MISSING" in res.signals


def test_realistic_might_be_five_people_inside():
    """'there might be 5 people inside' => count: 5 with hedged confidence"""
    res = extract_people_at_risk("there might be 5 people inside")
    assert res.count == 5
    assert res.confidence == 0.60


def test_realistic_family_of_five_trapped_in_car():
    """'family of 5 trapped in car' => count: 5, TRAPPED"""
    res = extract_people_at_risk("family of 5 trapped in car")
    assert res.count == 5
    assert "TRAPPED" in res.signals


def test_realistic_dozens_passengers_injured_no_count():
    """'dozens of passengers injured' => count: null, MULTIPLE_PEOPLE, INJURED"""
    res = extract_people_at_risk("dozens of passengers injured")
    assert res.count is None
    assert res.confidence is None
    assert "MULTIPLE_PEOPLE" in res.signals
    assert "INJURED" in res.signals


def test_realistic_group_of_people_trapped():
    """'a group of people trapped on roof' => count: null, MULTIPLE_PEOPLE, TRAPPED"""
    res = extract_people_at_risk("a group of people trapped on roof")
    assert res.count is None
    assert res.confidence is None
    assert "MULTIPLE_PEOPLE" in res.signals
    assert "TRAPPED" in res.signals


def test_realistic_two_unconscious_victims():
    """'two unconscious victims' => count: 2, UNCONSCIOUS"""
    res = extract_people_at_risk("two unconscious victims")
    assert res.count == 2
    assert "UNCONSCIOUS" in res.signals


def test_realistic_three_drowning_children():
    """'three drowning children' => count: 3, DROWNING, CHILDREN"""
    res = extract_people_at_risk("three drowning children")
    assert res.count == 3
    assert "DROWNING" in res.signals
    assert "CHILDREN" in res.signals


def test_realistic_four_elderly_residents():
    """'four elderly residents' => count: 4, ELDERLY"""
    res = extract_people_at_risk("four elderly residents")
    assert res.count == 4
    assert "ELDERLY" in res.signals


def test_realistic_reportedly_five_missing():
    """'5 people were reportedly trapped' => count: 5, hedged confidence"""
    res = extract_people_at_risk("5 people were reportedly trapped")
    assert res.count == 5
    assert res.confidence == 0.65
    assert "TRAPPED" in res.signals


# ==============================================================================
# 10. Canonical JSON Schema Compliance
# ==============================================================================


def test_canonical_schema_validation():
    """Validates that PeopleRiskResult.to_canonical_dict() strictly validates against ml/schemas/incident_output.json."""
    import json
    from pathlib import Path
    import jsonschema

    schema_path = Path("ml/schemas/incident_output.json")
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # Construct canonical output payload with extracted people_at_risk
    res = extract_people_at_risk("3 people trapped in elevator")
    payload = {
        "report_id": "rep-test-001",
        "model_version": "all-MiniLM-L6-v2+heuristic-v1",
        "incident_type": {
            "label": "STRUCTURAL_COLLAPSE",
            "confidence": 0.90,
        },
        "urgency": {
            "label": "HIGH",
            "confidence": 0.85,
        },
        "location": {
            "text": "building elevator",
            "latitude": None,
            "longitude": None,
            "precision": "unknown",
            "confidence": 0.70,
        },
        "people_at_risk": res.to_canonical_dict(),
        "required_response": [
            {"type": "SEARCH_AND_RESCUE", "confidence": 0.90}
        ],
        "entities": res.to_entities(),
        "processing_status": "SUCCESS",
        "warnings": [],
    }

    # Should validate without any jsonschema.ValidationError
    jsonschema.validate(instance=payload, schema=schema)

    # Test also with null count
    res_null = extract_people_at_risk("Flooding on highway")
    payload["people_at_risk"] = res_null.to_canonical_dict()
    jsonschema.validate(instance=payload, schema=schema)


# ==============================================================================
# 11. Privacy Observability Test
# ==============================================================================


def test_privacy_logging_no_raw_text_leak(caplog):
    """Verifies that extractor logger does not leak raw citizen distress text into logs."""
    import logging

    distress_text = "SECRET_DISTRESS_TEXT: My husband is bleeding and dying inside room 101"
    with caplog.at_level(logging.INFO, logger="karen.ml.extraction.people_risk"):
        extract_people_at_risk(distress_text, report_id="rep-privacy-123")

    for record in caplog.records:
        assert distress_text not in record.message
        assert "SECRET_DISTRESS_TEXT" not in record.message

