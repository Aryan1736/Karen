"""
Karen's Ear — Deep Repair, Hardening & Adversarial Verification Test Suite.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md, docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened Adversarial Test Suite

Verifies:
  1. LocationHint coordinate-precision invariants and bounds.
  2. ScenarioEvent event_id and dispatch.metadata.event_id cross-field consistency.
  3. Recursive Ground-Truth Leakage Firewall across deeply nested structures.
  4. EventBuffer explicit BufferOverflowError (zero silent dropping).
  5. EventBuffer partial flush failure FIFO re-buffering preservation.
  6. MLPredictionAdapter parsing of Aryan's ml/schemas/incident_output.json.
  7. Invalid predictions decrement coverage_rate and increment invalid_predictions count.
  8. Spearman's rho standard average-rank tie handling.
  9. Tri-state assertion semantics (PASS, FAIL, NOT_EVALUATED) and strict Rank #1 tie breaking.
 10. Location evaluation: coordinate hallucination detection and distance error.
 11. Latency profiling: truthful unmeasured state (no fake numbers).
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from evaluation.evaluate_correlation import (
    AssertionResult,
    evaluate_correlation_engine,
)
from evaluation.evaluate_ml import (
    EvaluationMode,
    LocationEvalMode,
    MLPredictionAdapter,
    NormalizedMLPrediction,
    evaluate_ml_predictions,
)
from evaluation.metrics import (
    compute_latency_profile,
    compute_location_metrics,
    compute_spearman_rho,
    rankdata,
)
from simulator.models import (
    ExpectedQueueDirection,
    FORBIDDEN_GROUND_TRUTH_KEYS,
    GroundTruth,
    GroundTruthIncidentType,
    GroundTruthLeakageError,
    GroundTruthRelationType,
    GroundTruthUrgency,
    LocationHint,
    LocationPrecision,
    RawReportPayload,
    ReportMetadata,
    ScenarioEvent,
    verify_no_ground_truth_leakage,
)
from simulator.transport import (
    BufferOverflowError,
    CircuitBreaker,
    CircuitState,
    DryRunTransport,
    EventBuffer,
    SafeHttpTransport,
    TransportConfig,
    prepare_payload,
)


# =============================================================================
# 1. LocationHint Invariants & Bounds
# =============================================================================

def test_location_hint_both_coordinates_or_neither():
    """Latitude and Longitude must both be provided or both be null."""
    # Both present -> valid
    loc_both = LocationHint(
        raw_text="Rasulgarh",
        latitude=20.296,
        longitude=85.824,
        precision=LocationPrecision.APPROXIMATE,
    )
    assert loc_both.latitude == 20.296
    assert loc_both.longitude == 85.824

    # Both null -> valid
    loc_null = LocationHint(
        raw_text="Industrial Area",
        latitude=None,
        longitude=None,
        precision=LocationPrecision.UNKNOWN,
    )
    assert loc_null.latitude is None
    assert loc_null.longitude is None

    # One present, one null -> must fail
    with pytest.raises(ValidationError, match="Incomplete coordinate pair"):
        LocationHint(
            raw_text="Faulty Coord",
            latitude=20.296,
            longitude=None,
            precision=LocationPrecision.APPROXIMATE,
        )

    with pytest.raises(ValidationError, match="Incomplete coordinate pair"):
        LocationHint(
            raw_text="Faulty Coord",
            latitude=None,
            longitude=85.824,
            precision=LocationPrecision.APPROXIMATE,
        )


def test_location_hint_unknown_precision_requires_null_coordinates():
    """When precision is UNKNOWN, coordinates MUST be null (ADR-009)."""
    with pytest.raises(ValidationError, match="Unknown precision requires null coordinates"):
        LocationHint(
            raw_text="Somewhere in city",
            latitude=20.296,
            longitude=85.824,
            precision=LocationPrecision.UNKNOWN,
        )


def test_location_hint_exact_precision_requires_coordinates():
    """When precision is EXACT, coordinates cannot be null."""
    with pytest.raises(ValidationError, match="Exact precision requires non-null latitude and longitude"):
        LocationHint(
            raw_text="123 Exact Street",
            latitude=None,
            longitude=None,
            precision=LocationPrecision.EXACT,
        )


def test_location_hint_coordinate_bounds():
    """Latitude must be in [-90, 90] and longitude in [-180, 180]."""
    with pytest.raises(ValidationError):
        LocationHint(
            raw_text="Out of bounds",
            latitude=95.0,  # Invalid
            longitude=85.0,
            precision=LocationPrecision.APPROXIMATE,
        )

    with pytest.raises(ValidationError):
        LocationHint(
            raw_text="Out of bounds",
            latitude=20.0,
            longitude=-185.0,  # Invalid
            precision=LocationPrecision.APPROXIMATE,
        )


# =============================================================================
# 2. ScenarioEvent Event ID Cross-Field Consistency
# =============================================================================

def test_scenario_event_id_mismatch_raises_validation_error():
    """ScenarioEvent.event_id must strictly match dispatch.metadata.event_id."""
    dispatch = RawReportPayload(
        report_id="rep-chk-001",
        text="Water rising on bridge",
        source="simulator",
        is_synthetic=True,
        reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
        metadata=ReportMetadata(
            scenario_id="flood_test",
            event_id="evt-expected-001",
        ),
    )
    gt = GroundTruth(incident_group="test-inc")

    # Mismatched event_id -> must fail
    with pytest.raises(ValidationError, match="ScenarioEvent.event_id mismatch"):
        ScenarioEvent(
            event_id="evt-differing-002",
            delay_seconds=0.0,
            dispatch=dispatch,
            ground_truth=gt,
        )

    # Matched event_id -> succeeds
    ev = ScenarioEvent(
        event_id="evt-expected-001",
        delay_seconds=0.0,
        dispatch=dispatch,
        ground_truth=gt,
    )
    assert ev.event_id == "evt-expected-001"


# =============================================================================
# 3. Recursive Ground-Truth Leakage Firewall
# =============================================================================

def test_recursive_leakage_firewall_catches_nested_attacks():
    """Firewall catches forbidden ground-truth keys nested at arbitrary depths."""
    # Clean dictionary
    clean = {
        "report_id": "rep-001",
        "metadata": {
            "scenario_id": "flood_rasulgarh",
            "caller_id": "sim-caller-001",
            "extra": {"nested_clean": True},
        },
    }
    verify_no_ground_truth_leakage(clean)  # Must not raise

    # Nested attack 1: deep in metadata dictionary
    attack_1 = {
        "report_id": "rep-001",
        "metadata": {
            "debug": {
                "expected_urgency": "CRITICAL",
            },
        },
    }
    with pytest.raises(GroundTruthLeakageError, match="LEAKAGE VIOLATION at '\\$.metadata.debug.expected_urgency'"):
        verify_no_ground_truth_leakage(attack_1)

    # Nested attack 2: inside a list of dictionaries
    attack_2 = {
        "report_id": "rep-001",
        "tags": [
            {"name": "rain"},
            {"incident_group": "bbsr-flood-01"},
        ],
    }
    with pytest.raises(GroundTruthLeakageError, match="LEAKAGE VIOLATION at '\\$.tags\\[1\\].incident_group'"):
        verify_no_ground_truth_leakage(attack_2)

    # Nested attack 3: expected_* prefix anywhere
    attack_3 = {"custom_field": {"expected_people_count": 5}}
    with pytest.raises(GroundTruthLeakageError, match="private ground-truth key 'expected_people_count' detected"):
        verify_no_ground_truth_leakage(attack_3)


# =============================================================================
# 4. Zero-Data-Loss Event Buffer Invariants
# =============================================================================

def test_event_buffer_overflow_error():
    """EventBuffer raises BufferOverflowError on exceeding max_capacity (no silent drop)."""
    buf = EventBuffer(max_capacity=3)
    dispatch = RawReportPayload(
        report_id="rep-buf-001",
        text="Flood hazard",
        source="simulator",
        is_synthetic=True,
        reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
        metadata=ReportMetadata(scenario_id="sim", event_id="evt-buf-001"),
    )
    ev = ScenarioEvent(
        event_id="evt-buf-001",
        delay_seconds=0.0,
        dispatch=dispatch,
        ground_truth=GroundTruth(),
    )

    buf.append(ev)
    buf.append(ev)
    buf.append(ev)
    assert len(buf) == 3

    # 4th append exceeds capacity -> must raise BufferOverflowError
    with pytest.raises(BufferOverflowError, match="Refusing to silently drop emergency disaster report"):
        buf.append(ev)


def test_safe_transport_partial_flush_failure_rebuffers_in_fifo_order():
    """
    When flushing a buffer with [ev0, ev1, ev2, ev3] and ev1 fails:
    Unsent events [ev1, ev2, ev3] remain in the buffer in exact FIFO order.
    """
    def make_event(num: int) -> ScenarioEvent:
        return ScenarioEvent(
            event_id=f"evt-flush-{num}",
            delay_seconds=0.0,
            dispatch=RawReportPayload(
                report_id=f"rep-flush-{num}",
                text=f"Report {num}",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
                metadata=ReportMetadata(scenario_id="sim", event_id=f"evt-flush-{num}"),
            ),
            ground_truth=GroundTruth(),
        )

    ev0 = make_event(0)
    ev1 = make_event(1)
    ev2 = make_event(2)
    ev3 = make_event(3)

    # Mock server that succeeds for ev0, but fails on ev1
    def mock_server(payload):
        if payload["report_id"] == "rep-flush-0":
            return 201, {"status": "ACCEPTED"}
        raise ConnectionError("Server went down on event 1")

    transport = SafeHttpTransport(
        config=TransportConfig(dry_run=False, max_retries=0, buffer_on_failure=True),
        mock_handler=mock_server,
    )

    # Pre-populate buffer with 4 events
    transport.buffer.append(ev0)
    transport.buffer.append(ev1)
    transport.buffer.append(ev2)
    transport.buffer.append(ev3)
    assert len(transport.buffer) == 4

    # Flush buffer
    results = transport.flush_buffer()

    # ev0 succeeded, ev1 failed
    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False

    # Remaining in buffer: ev1, ev2, ev3 in exact original order!
    buffered_events = transport.get_buffered_events()
    assert len(buffered_events) == 3
    assert buffered_events[0].event_id == "evt-flush-1"
    assert buffered_events[1].event_id == "evt-flush-2"
    assert buffered_events[2].event_id == "evt-flush-3"


# =============================================================================
# 5. ML Adapter & Coverage Rate Auditing
# =============================================================================

def test_ml_adapter_parses_canonical_aryan_schema():
    """Adapter correctly extracts nested structures from ml/schemas/incident_output.json."""
    aryan_output = {
        "report_id": "rep-ary-001",
        "model_version": "gemini-flash-crisis-v1",
        "incident_type": {
            "label": "FLOOD_FLASH_FLOOD",
            "confidence": 0.94,
        },
        "urgency": {
            "label": "CRITICAL",
            "confidence": 0.98,
        },
        "location": {
            "text": "Rasulgarh underpass",
            "latitude": 20.2960,
            "longitude": 85.8245,
            "precision": "approximate",
            "confidence": 0.89,
        },
        "people_at_risk": {
            "count": 4,
            "confidence": 0.92,
        },
        "required_response": [
            {"type": "SEARCH_AND_RESCUE", "confidence": 0.96},
            {"type": "MEDICAL_EMS", "confidence": 0.85},
        ],
        "entities": [],
        "processing_status": "COMPLETED",
        "warnings": [],
    }

    norm = MLPredictionAdapter.adapt(aryan_output)
    assert norm.is_valid is True
    assert norm.incident_type == "FLOOD_FLASH_FLOOD"
    assert norm.incident_type_confidence == 0.94
    assert norm.urgency == "CRITICAL"
    assert norm.urgency_confidence == 0.98
    assert norm.people_at_risk_count == 4
    assert norm.location_text == "Rasulgarh underpass"
    assert norm.latitude == 20.2960
    assert norm.longitude == 85.8245
    assert norm.precision == "approximate"
    assert norm.required_response_types == ["SEARCH_AND_RESCUE", "MEDICAL_EMS"]


def test_ml_adapter_handles_invalid_inputs_and_penalizes_coverage():
    """Invalid outputs are flagged and properly decrement coverage_rate."""
    events = [
        ScenarioEvent(
            event_id="evt-cov-001",
            delay_seconds=0.0,
            dispatch=RawReportPayload(
                report_id="rep-cov-001",
                text="Fire alarm",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
                metadata=ReportMetadata(scenario_id="sim", event_id="evt-cov-001"),
            ),
            ground_truth=GroundTruth(expected_incident_type=GroundTruthIncidentType.FIRE_WILDFIRE_EXPLOSION),
        ),
        ScenarioEvent(
            event_id="evt-cov-002",
            delay_seconds=0.0,
            dispatch=RawReportPayload(
                report_id="rep-cov-002",
                text="Another report",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
                metadata=ReportMetadata(scenario_id="sim", event_id="evt-cov-002"),
            ),
            ground_truth=GroundTruth(expected_incident_type=GroundTruthIncidentType.FIRE_WILDFIRE_EXPLOSION),
        ),
    ]

    # Predictor returning garbage on event 2
    def bad_predictor(text):
        if "Another" in text:
            return "This is a string not a dict"  # Breach
        return {
            "incident_type": {"label": "FIRE_WILDFIRE_EXPLOSION", "confidence": 0.9},
            "urgency": {"label": "LOW", "confidence": 0.8},
        }

    report = evaluate_ml_predictions(events, predict_fn=bad_predictor)
    assert report.total_samples == 2
    assert report.coverage.valid_predictions == 1
    assert report.coverage.invalid_predictions == 1
    assert report.coverage.coverage_rate == 0.5
    assert len(report.coverage.invalid_reasons) == 1
    assert "Prediction is not a dictionary" in report.coverage.invalid_reasons[0]


# =============================================================================
# 6. Spearman's Rho Average-Rank Tie Handling
# =============================================================================

def test_spearman_rho_with_tied_ranks():
    """Ranks with ties must be assigned fractional/average ranks."""
    # Data with ties: [10, 20, 20, 40] -> ranks [1.0, 2.5, 2.5, 4.0]
    ranks = rankdata([10, 20, 20, 40])
    assert ranks == [1.0, 2.5, 2.5, 4.0]

    # All identical -> all get average rank
    identical_ranks = rankdata([5, 5, 5])
    assert identical_ranks == [2.0, 2.0, 2.0]

    # Perfectly correlated with ties
    rho_perfect = compute_spearman_rho([10, 20, 20, 40], [10, 20, 20, 40])
    assert rho_perfect == 1.0

    # Inverted with ties
    rho_inverted = compute_spearman_rho([10, 20, 20, 40], [40, 20, 20, 10])
    assert rho_inverted == -1.0


# =============================================================================
# 7. Tri-State Assertions & Strict Rank #1 Tie Breaking
# =============================================================================

def test_tri_state_assertions_and_strict_tie_breaking():
    """Rank #1 assertion detects ties and returns AssertionResult.FAIL under strict mode."""
    events = [
        ScenarioEvent(
            event_id="evt-tie-001",
            delay_seconds=0.0,
            dispatch=RawReportPayload(
                report_id="rep-tie-001",
                text="Trapped van flood",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
                metadata=ReportMetadata(scenario_id="flood_sim", event_id="evt-tie-001"),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-01",
                expected_urgency=GroundTruthUrgency.CRITICAL,
            ),
        ),
        ScenarioEvent(
            event_id="evt-tie-002",
            delay_seconds=0.0,
            dispatch=RawReportPayload(
                report_id="rep-tie-002",
                text="Chemical spill other incident",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
                metadata=ReportMetadata(scenario_id="flood_sim", event_id="evt-tie-002"),
            ),
            ground_truth=GroundTruth(
                incident_group="other-chemical-01",
                expected_urgency=GroundTruthUrgency.CRITICAL,
            ),
        ),
    ]

    # Both incidents given equal top score: 95.0
    mock_tied_stream = [
        {"incident_id": "inc-flood", "relationship": "INITIAL", "priority_score": 95.0, "rank": 1},
        {"incident_id": "inc-chem", "relationship": "INITIAL", "priority_score": 95.0, "rank": 1},
    ]

    # Strict mode: tie means trapped van did NOT strictly achieve Rank #1 alone
    rep_strict = evaluate_correlation_engine(
        events,
        mock_correlation_outputs=mock_tied_stream,
        strict_rank_1_no_ties=True,
    )
    assert rep_strict.rank_1_tie_detected is True
    assert rep_strict.scenario_rank_1_status == AssertionResult.FAIL

    # When flood van is strictly higher
    mock_clean_win = [
        {"incident_id": "inc-flood", "relationship": "INITIAL", "priority_score": 98.0, "rank": 1},
        {"incident_id": "inc-chem", "relationship": "INITIAL", "priority_score": 80.0, "rank": 2},
    ]
    rep_win = evaluate_correlation_engine(
        events,
        mock_correlation_outputs=mock_clean_win,
        strict_rank_1_no_ties=True,
    )
    assert rep_win.rank_1_tie_detected is False
    assert rep_win.scenario_rank_1_status == AssertionResult.PASS


# =============================================================================
# 8. Location Coordinate Hallucination Detection
# =============================================================================

def test_location_metrics_coordinate_hallucination():
    """Detects when an unlocated report receives hallucinated coordinates."""
    true_locs = [
        {"raw_text": "near Rasulgarh", "latitude": 20.296, "longitude": 85.824},
        {"raw_text": "somewhere in industrial area", "latitude": None, "longitude": None},  # Unlocated
    ]

    # Model hallucinates coordinates for report 2!
    pred_locs = [
        {"text": "Rasulgarh", "latitude": 20.296, "longitude": 85.824},
        {"text": "industrial area", "latitude": 20.300, "longitude": 85.800},  # HALLUCINATION
    ]

    loc_rep = compute_location_metrics(true_locs, pred_locs)
    assert loc_rep.total_unlocated_reports == 1
    assert loc_rep.hallucinated_coordinate_count == 1
    assert loc_rep.coordinate_hallucination_rate == 1.0


# =============================================================================
# 9. Latency Profile Unmeasured State
# =============================================================================

def test_latency_profile_unmeasured():
    """Empty latencies result in is_measured=False, not fabricated mock numbers."""
    prof = compute_latency_profile([])
    assert prof.is_measured is False
    assert prof.sample_count == 0
    d = prof.to_dict()
    assert d["p50_ms"] is None
    assert d["p95_ms"] is None
    assert d["is_measured"] is False
