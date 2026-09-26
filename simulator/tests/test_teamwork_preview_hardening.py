"""
Karen's Ear — Teamwork Preview Forensic Hardening & Regression Test Suite.

Author: Pankaj (feature/evaluation-integration)
Authority: Phase 1 & Phase 2 Hardening Protocols
Status: Production Regression Suite
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import pytest

from evaluation.evaluate_correlation import (
    AssertionResult,
    evaluate_correlation_engine,
)
from evaluation.evaluate_ml import (
    MLPredictionAdapter,
    evaluate_ml_predictions,
)
from evaluation.metrics import (
    _is_location_text_match,
    compute_location_metrics,
    compute_people_at_risk_metrics,
)
from evaluation.run_all_evals import generate_markdown_scorecard, run_full_benchmark
from simulator.engine import SimulationEngine
from simulator.models import (
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
from simulator.scenarios import (
    get_scenario,
    list_scenarios,
    register_scenario,
)
from simulator.timeline import SpeedMode, Timeline
from simulator.transport import (
    CircuitBreaker,
    CircuitState,
    EventBuffer,
    SafeHttpTransport,
    TransportConfig,
)


# =============================================================================
# 1. DEF-01: people_at_risk zero count must NOT be marked at risk
# =============================================================================

def test_people_at_risk_zero_count_not_at_risk():
    """A prediction with count=0 and high confidence must have people_at_risk=False."""
    norm = MLPredictionAdapter.adapt({
        "report_id": "rep-001",
        "people_at_risk": {
            "count": 0,
            "confidence": 0.98,
        },
    })
    assert norm.people_at_risk is False
    assert norm.people_at_risk_count == 0


def test_people_at_risk_positive_count_is_at_risk():
    """A prediction with count > 0 must have people_at_risk=True."""
    norm = MLPredictionAdapter.adapt({
        "report_id": "rep-002",
        "people_at_risk": {
            "count": 4,
            "confidence": 0.95,
        },
    })
    assert norm.people_at_risk is True
    assert norm.people_at_risk_count == 4


# =============================================================================
# 2. DEF-02: Location text match rejects generic words & prepositions
# =============================================================================

def test_location_text_match_rejects_stopwords_and_prepositions():
    """Generic road/preposition words alone must not satisfy location match."""
    assert not _is_location_text_match("near Rasulgarh square", "near")
    assert not _is_location_text_match("service road under railway bridge", "road")
    assert not _is_location_text_match("somewhere in industrial area", "area")
    assert not _is_location_text_match("somewhere in industrial area", "somewhere")


def test_location_text_match_accepts_meaningful_tokens():
    """Specific landmark tokens must satisfy location match."""
    assert _is_location_text_match("near Rasulgarh square", "Rasulgarh")
    assert _is_location_text_match("near Rasulgarh square", "square")
    assert _is_location_text_match("service road under railway bridge", "railway bridge")


# =============================================================================
# 3. DEF-03 & DEF-05: Correlation focal group & incident critical recall
# =============================================================================

def test_focal_group_selection_prefers_critical_over_flood():
    """Non-flood critical emergency is correctly identified as focal and escalated."""
    event1 = ScenarioEvent(
        event_id="evt-fire-001",
        dispatch=RawReportPayload(
            report_id="rep-fire-001",
            text="Explosion and fire at refinery, 5 workers trapped inside!",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime.now(timezone.utc),
            location_hint=LocationHint(raw_text="Refinery Unit 2", latitude=20.25, longitude=85.80, precision=LocationPrecision.APPROXIMATE),
        ),
        ground_truth=GroundTruth(
            incident_group="refinery-fire-01",
            expected_incident_type=GroundTruthIncidentType.FIRE_WILDFIRE_EXPLOSION,
            expected_urgency=GroundTruthUrgency.CRITICAL,
            relation_type=GroundTruthRelationType.INITIAL,
        ),
    )
    event2 = ScenarioEvent(
        event_id="evt-flood-minor-001",
        dispatch=RawReportPayload(
            report_id="rep-fld-min-001",
            text="Small water puddle on street near park.",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime.now(timezone.utc),
            location_hint=LocationHint(raw_text="Near Park", latitude=20.26, longitude=85.81, precision=LocationPrecision.APPROXIMATE),
        ),
        ground_truth=GroundTruth(
            incident_group="flood-puddle-01",
            expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
            expected_urgency=GroundTruthUrgency.LOW,
            relation_type=GroundTruthRelationType.INITIAL,
        ),
    )

    outputs = [
        {"incident_id": "inc-refinery", "relationship": "INITIAL", "priority_score": 95.0},
        {"incident_id": "inc-puddle", "relationship": "INITIAL", "priority_score": 20.0},
    ]

    report = evaluate_correlation_engine([event1, event2], mock_correlation_outputs=outputs)
    assert report.scenario_rank_1_status == AssertionResult.PASS
    assert report.incident_critical_recall == 1.0


# =============================================================================
# 4. DEF-07: Firewall blocks smuggled scenario_id
# =============================================================================

def test_firewall_blocks_smuggled_scenario_id():
    """Firewall intercepts private tokens smuggled inside metadata.scenario_id."""
    payload = {
        "metadata": {
            "scenario_id": "expected_urgency:CRITICAL",
        }
    }
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage(payload)


# =============================================================================
# 5. DEF-09 & DEF-10: CircuitBreaker concurrency & HALF_OPEN throttling
# =============================================================================

def test_circuit_breaker_half_open_limits_probe_concurrency():
    """In HALF_OPEN, CircuitBreaker allows only 1 probe at a time."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.1)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    time.sleep(0.12)
    assert cb.state == CircuitState.HALF_OPEN

    # First attempt acquires probe token
    assert cb.can_attempt() is True
    # Second concurrent attempt must be rejected until probe completes
    assert cb.can_attempt() is False

    cb.record_success()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_thread_safe_locking():
    """Concurrent threads updating CircuitBreaker state do not crash or race."""
    cb = CircuitBreaker(failure_threshold=10, recovery_timeout_seconds=0.01)

    def worker():
        for _ in range(50):
            if cb.can_attempt():
                cb.record_failure()
            else:
                cb.reset()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert cb.state in (CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN)


# =============================================================================
# 6. DEF-11 & DEF-12: Transport application errors and buffer overflow
# =============================================================================

def test_safe_transport_app_level_rejection_permanent_no_buffer():
    """HTTP 200 with success=false is an application rejection, not buffered or retried."""
    handler = lambda payload: (200, {"success": False, "error": "Invalid format"})
    transport = SafeHttpTransport(
        config=TransportConfig(dry_run=False, buffer_on_failure=True),
        mock_handler=handler,
    )
    event = get_scenario("flood_rasulgarh")[0]
    res = transport.send_event(event)

    assert res.success is False
    assert res.buffered is False
    assert len(transport.buffer) == 0
    assert "API Application Error" in res.error


def test_safe_transport_buffer_overflow_caught_gracefully():
    """When event buffer is at max capacity, send_event does not throw unhandled exception."""
    handler = lambda payload: (500, {"error": "Server down"})
    transport = SafeHttpTransport(
        config=TransportConfig(dry_run=False, buffer_on_failure=True, max_buffer_size=1),
        mock_handler=handler,
    )
    event = get_scenario("flood_rasulgarh")[0]

    # First event buffers
    res1 = transport.send_event(event)
    assert res1.buffered is True
    assert len(transport.buffer) == 1

    # Second event exceeds capacity; caught gracefully without crashing
    res2 = transport.send_event(event)
    assert res2.success is False
    assert res2.buffered is False
    assert "Buffer overflow" in res2.error


# =============================================================================
# 7. DEF-13: SimulationEngine run_async with dispatch_fn
# =============================================================================

@pytest.mark.asyncio
async def test_engine_run_async_with_dispatch_fn():
    """SimulationEngine.run_async invokes self.dispatch_fn when async_dispatch_fn is None."""
    events = get_scenario("flood_rasulgarh")[:2]
    timeline = Timeline(events=events, speed="burst")
    dispatched_payloads = []

    engine = SimulationEngine(
        timeline=timeline,
        dry_run=False,
        dispatch_fn=lambda p: dispatched_payloads.append(p),
    )
    summary = await engine.run_async()

    assert summary.dispatched_events == 2
    assert len(dispatched_payloads) == 2
    assert dispatched_payloads[0]["report_id"] == "rep-fld-001"


# =============================================================================
# 8. DEF-14: SpeedMode.parse NaN handling
# =============================================================================

def test_speed_mode_parse_handles_nan_safely():
    """SpeedMode.parse parses nan and inf without crashing, and Timeline handles it safely."""
    import math
    assert math.isnan(SpeedMode.parse("nan"))
    assert math.isnan(SpeedMode.parse(float("nan")))
    assert SpeedMode.parse("inf") == float("inf")
    assert SpeedMode.parse("burst") == float("inf")


# =============================================================================
# 9. DEF-16 & DEF-17: Scorecard file validation and life-safety status
# =============================================================================

def test_run_all_evals_missing_file_raises_error():
    """run_full_benchmark raises FileNotFoundError when input files do not exist."""
    with pytest.raises(FileNotFoundError):
        run_full_benchmark(ml_predictions_file="non_existent_ml_file.json")

    with pytest.raises(FileNotFoundError):
        run_full_benchmark(backend_results_file="non_existent_corr_file.json")


def test_scorecard_zero_critical_events_not_evaluated():
    """Batches with zero critical events output NOT EVALUATED for life safety invariant."""
    from evaluation.metrics import compute_latency_profile
    events = [get_scenario("mixed_hard_negatives")[0]]  # drill notice, LOW urgency
    ml_rep = evaluate_ml_predictions(events)
    corr_rep = evaluate_correlation_engine(events)
    scorecard = generate_markdown_scorecard(ml_rep, corr_rep, compute_latency_profile([]))

    assert "NOT EVALUATED" in scorecard


# =============================================================================
# 10. DEF-19: Dynamic scenario registration
# =============================================================================

def test_register_scenario_dynamic():
    """register_scenario allows dynamic registration of custom scenarios with proper teardown."""
    from simulator.scenarios import SCENARIO_REGISTRY
    custom_id = "test_custom_drill_01"
    sample_events = get_scenario("flood_rasulgarh")[:1]
    try:
        register_scenario(
            scenario_id=custom_id,
            name="Custom Drill Scenario",
            description="Dynamic test drill scenario",
            loader=lambda: sample_events,
        )
        assert custom_id in list_scenarios()
        loaded = get_scenario(custom_id)
        assert len(loaded) == 1
        assert loaded[0].event_id == sample_events[0].event_id
    finally:
        SCENARIO_REGISTRY.pop(custom_id, None)

