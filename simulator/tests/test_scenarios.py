"""
Karen's Ear — Phase 2 Test Suite: Golden Disaster Scenarios.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md, docs/data-schema.md, architecture/simulation.md
Status: Phase 2 — Golden Disaster Scenarios

Tests:
  TEST 1: Scenario registry discovery and listing
  TEST 2: Unknown scenario raises KeyError
  TEST 3: Event ID uniqueness across all registered scenarios
  TEST 4: Report ID uniqueness across all registered scenarios
  TEST 5: Complete RawReport contract compliance for all scenario dispatches
  TEST 6: Zero Ground-Truth leakage across every public payload
  TEST 7: Spatiotemporal clustering and relationship distribution in flood_rasulgarh
  TEST 8: Adversarial hard negatives and review flag coverage in mixed_hard_negatives
  TEST 9: Unlocated coordinate preservation (ADR-009)
  TEST 10: Scenario replay determinism (bit-for-bit identical on reload)
"""

import pytest

from simulator.models import (
    GroundTruthRelationType,
    GroundTruthUrgency,
    LocationPrecision,
)
from simulator.scenarios import (
    FLOOD_ID,
    HARD_NEG_ID,
    get_scenario,
    list_scenarios,
)


def test_scenario_registry_discovery():
    """Registry lists registered scenarios including flood_rasulgarh and mixed_hard_negatives."""
    scenarios = list_scenarios()
    assert FLOOD_ID in scenarios
    assert HARD_NEG_ID in scenarios
    assert len(scenarios) >= 2


def test_unknown_scenario_raises_key_error():
    """Attempting to load an unregistered scenario raises KeyError with helpful message."""
    with pytest.raises(KeyError) as exc_info:
        get_scenario("non_existent_scenario_123")
    assert "non_existent_scenario_123" in str(exc_info.value)


def test_event_id_uniqueness():
    """All scenario events must have unique event_ids across the entire scenario catalog."""
    seen_event_ids = set()
    for scenario_id in list_scenarios():
        events = get_scenario(scenario_id)
        for event in events:
            assert event.event_id not in seen_event_ids, f"Collision detected for event_id: '{event.event_id}'"
            seen_event_ids.add(event.event_id)
            assert len(event.event_id.strip()) > 0


def test_report_id_uniqueness():
    """All scenario dispatches must have unique report_ids across the entire scenario catalog."""
    seen_report_ids = set()
    for scenario_id in list_scenarios():
        events = get_scenario(scenario_id)
        for event in events:
            report_id = event.dispatch.report_id
            assert report_id not in seen_report_ids, f"Collision detected for report_id: '{report_id}'"
            seen_report_ids.add(report_id)


def test_public_dispatch_contract_compliance():
    """Every dispatch in every scenario must strictly satisfy the canonical RawReport contract."""
    for scenario_id in list_scenarios():
        events = get_scenario(scenario_id)
        for event in events:
            dispatch = event.dispatch
            # Source and synthetic invariants
            assert dispatch.source == "simulator"
            assert dispatch.is_synthetic is True
            # Text length bounds
            assert 3 <= len(dispatch.text) <= 4000
            # Timezone-aware timestamp
            assert dispatch.reported_at.tzinfo is not None
            # Location bounds if coords are present
            if dispatch.location_hint is not None:
                if dispatch.location_hint.latitude is not None:
                    assert -90.0 <= dispatch.location_hint.latitude <= 90.0
                if dispatch.location_hint.longitude is not None:
                    assert -180.0 <= dispatch.location_hint.longitude <= 180.0
                assert dispatch.location_hint.precision in LocationPrecision


def test_zero_ground_truth_leakage_across_all_scenarios():
    """
    Architectural Leak Prevention:
    Verify for EVERY event in EVERY scenario that event.public_payload()
    contains zero GroundTruth keys.
    """
    forbidden_keys = [
        "ground_truth",
        "incident_group",
        "expected_incident_type",
        "expected_urgency",
        "expected_people_at_risk",
        "expected_people_count",
        "relation_type",
        "expected_direction",
        "expected_needs_review",
        "notes",
    ]

    for scenario_id in list_scenarios():
        events = get_scenario(scenario_id)
        for event in events:
            public_dict = event.public_payload()
            # Must contain standard RawReport fields
            assert "report_id" in public_dict
            assert "text" in public_dict
            assert public_dict["is_synthetic"] is True
            assert public_dict["source"] == "simulator"
            assert "reported_at" in public_dict

            # Must NOT contain any evaluator ground truth keys
            for key in forbidden_keys:
                assert key not in public_dict, (
                    f"Ground-truth leakage detected in event '{event.event_id}' "
                    f"of scenario '{scenario_id}': key '{key}' found in public payload!"
                )


def test_flood_rasulgarh_clustering_and_corroboration():
    """flood_rasulgarh must cover spatiotemporal clusters, corroboration, and duplicates."""
    events = get_scenario(FLOOD_ID)
    assert len(events) == 15

    # Check relation types present
    relation_types = {e.ground_truth.relation_type for e in events}
    assert GroundTruthRelationType.INITIAL in relation_types
    assert GroundTruthRelationType.CORROBORATING in relation_types
    assert GroundTruthRelationType.DUPLICATE in relation_types
    assert GroundTruthRelationType.RELATED in relation_types
    assert GroundTruthRelationType.NOISE in relation_types
    assert GroundTruthRelationType.UNCERTAIN in relation_types

    # Trapped persons event verification
    critical_events = [e for e in events if e.ground_truth.expected_urgency == GroundTruthUrgency.CRITICAL]
    assert len(critical_events) >= 5

    # Check that corroborating events reference same incident cluster
    cluster_ids = {e.ground_truth.incident_group for e in events if e.ground_truth.incident_group is not None}
    assert "bbsr-flood-rasulgarh-01" in cluster_ids


def test_mixed_hard_negatives_coverage():
    """mixed_hard_negatives must contain adversarial tests, slang, and review flags."""
    events = get_scenario(HARD_NEG_ID)
    assert len(events) == 12

    # Needs review flags
    review_events = [e for e in events if e.ground_truth.expected_needs_review is True]
    assert len(review_events) >= 4  # Fire drill, WhatsApp rumor, prank, unlocated chemical

    # Slang test: 'murder' and 'dying laughing' must not have casualties
    slang_event = next(e for e in events if e.event_id == "evt-hn-002")
    assert slang_event.ground_truth.expected_people_at_risk is False
    assert slang_event.ground_truth.expected_people_count == 0
    assert slang_event.ground_truth.expected_urgency == GroundTruthUrgency.LOW


def test_unlocated_hazard_preserves_null_coordinates():
    """Unlocated hazards must preserve null coordinates and unknown precision without hallucination."""
    events = get_scenario(HARD_NEG_ID)
    unlocated_event = next(e for e in events if e.event_id == "evt-hn-012")

    loc = unlocated_event.dispatch.location_hint
    assert loc is not None
    assert loc.latitude is None
    assert loc.longitude is None
    assert loc.precision == LocationPrecision.UNKNOWN


def test_scenario_replay_determinism():
    """Loading scenarios repeatedly must yield bit-for-bit identical payloads and delays."""
    run_1 = [e.model_dump() for e in get_scenario(FLOOD_ID)]
    run_2 = [e.model_dump() for e in get_scenario(FLOOD_ID)]
    assert run_1 == run_2

    hn_1 = [e.model_dump() for e in get_scenario(HARD_NEG_ID)]
    hn_2 = [e.model_dump() for e in get_scenario(HARD_NEG_ID)]
    assert hn_1 == hn_2
