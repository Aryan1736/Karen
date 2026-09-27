"""
Karen's Ear — Adversarial Hardening & Forensic Verification Test Suite.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md, docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened Regression Suite

Covers:
1. NaN and Inf tie-handling in rankdata (preventing infinite loops).
2. Haversine floating-point domain boundary clamping.
3. Zero-denominator truthful reporting (None / NOT_EVALUATED vs fake 1.0).
4. SafeHttpTransport 422 unprocessable entity poison pill prevention.
5. SafeHttpTransport 429 rate limit / Retry-After handling.
6. Engine lifecycle guards (reentrancy, pause-before-run, reset).
7. Reflection & typing.get_type_hints() across all modules without NameError.
8. ML adapter adversarial input fuzzing (strings, NaNs, negative casualties, out-of-bounds coordinates).
9. Allowlist projection in ScenarioEvent.public_payload().
10. End-to-end CLI runner with external JSON result file ingestion.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import typing
from unittest.mock import MagicMock, patch

import pytest

from evaluation.evaluate_correlation import (
    AssertionResult,
    evaluate_correlation_engine,
)
from evaluation.evaluate_ml import (
    EvaluationMode,
    MLPredictionAdapter,
    evaluate_ml_predictions,
)
from evaluation.metrics import (
    compute_classification_report,
    compute_coverage_report,
    compute_dual_critical_recall,
    compute_fusion_accuracy,
    compute_latency_profile,
    compute_location_metrics,
    compute_people_at_risk_metrics,
    compute_spearman_rho,
    compute_urgency_alignment,
    haversine_distance_km,
    rankdata,
)
import evaluation
import evaluation.evaluate_correlation
import evaluation.evaluate_ml
import evaluation.metrics
import evaluation.run_all_evals
from evaluation.run_all_evals import main as run_all_evals_main, run_full_benchmark
import simulator.cli
import simulator.engine
from simulator.engine import EngineState, PlaybackSummary, SimulationEngine
import simulator.models
from simulator.models import (
    ExpectedQueueDirection,
    GroundTruth,
    GroundTruthIncidentType,
    GroundTruthRelationType,
    GroundTruthUrgency,
    LocationHint,
    LocationPrecision,
    RawReportPayload,
    ReportMetadata,
    ScenarioEvent,
)
import simulator.scenarios
import simulator.timeline
from simulator.timeline import Timeline
import simulator.transport
from simulator.transport import (
    CircuitBreaker,
    CircuitState,
    DryRunTransport,
    EventBuffer,
    SafeHttpTransport,
    TransportConfig,
)


# =============================================================================
# 1. NaN and Inf Tie Handling in rankdata (Infinite Loop Prevention)
# =============================================================================

def test_rankdata_with_nans_and_infinities():
    """Verifies rankdata groups NaNs and exits deterministically without looping forever."""
    # Test array containing multiple NaNs, identical numbers, and infinities
    data = [float("nan"), 10.0, float("nan"), 5.0, 10.0, float("inf"), float("nan")]
    ranks = rankdata(data)
    assert len(ranks) == len(data)
    # The smallest finite number 5.0 should have rank 1.0
    assert ranks[3] == 1.0
    # Tied values 10.0 at indices 1 and 4 should have avg rank 2.5
    assert ranks[1] == 2.5
    assert ranks[4] == 2.5
    # Infinity at index 5 should have rank 4.0
    assert ranks[5] == 4.0
    # NaNs should all share the average rank for tied elements at the end
    nan_ranks = [ranks[0], ranks[2], ranks[6]]
    assert nan_ranks[0] == nan_ranks[1] == nan_ranks[2]
    assert nan_ranks[0] == 6.0  # Ranks 5, 6, 7 averaged = 6.0


def test_spearman_rho_with_nans():
    """Spearman correlation does not crash or loop when rankings contain NaNs."""
    x = [1.0, 2.0, float("nan"), 4.0]
    y = [1.0, 2.0, 3.0, 4.0]
    rho = compute_spearman_rho(x, y)
    assert isinstance(rho, float)
    assert -1.0 <= rho <= 1.0


# =============================================================================
# 2. Haversine Floating-Point Domain Boundary Clamping
# =============================================================================

def test_haversine_antipodal_and_identical_boundaries():
    """Haversine distance handles antipodal and identical coordinates without math domain errors."""
    # Identical coordinates
    d_zero = haversine_distance_km(20.296, 85.824, 20.296, 85.824)
    assert d_zero == 0.0

    # Antipodal points: latitude 0, longitude 0 vs latitude 0, longitude 180
    d_antipodal = haversine_distance_km(0.0, 0.0, 0.0, 180.0)
    assert abs(d_antipodal - 20015.0) < 50.0  # ~20,015 km (half Earth circumference)

    # Extreme latitudes
    d_poles = haversine_distance_km(90.0, 0.0, -90.0, 0.0)
    assert abs(d_poles - 20015.0) < 50.0


# =============================================================================
# 3. Truthful Zero-Denominator Handling
# =============================================================================

def test_zero_denominator_critical_recall_returns_none():
    """When zero critical reports/incidents exist, recall is truthfully None, not 1.0."""
    report_evals = [
        {"report_id": "rep-1", "true_urgency": "LOW", "pred_urgency": "LOW"},
        {"report_id": "rep-2", "true_urgency": "MEDIUM", "pred_urgency": "MEDIUM"},
    ]
    incident_evals = [
        {"incident_group": "inc-1", "true_urgency": "HIGH", "pred_urgency": "HIGH"},
    ]
    dual = compute_dual_critical_recall(report_evals, incident_evals)
    assert dual.report_critical_recall is None
    assert dual.incident_critical_recall is None
    d = dual.to_dict()
    assert d["report_critical_recall"] is None
    assert d["incident_critical_recall"] is None


def test_zero_denominator_urgency_and_clustering():
    """Empty urgency or fusion sequences yield truthful None or base reports without DivisionByZero."""
    align = compute_urgency_alignment([], [])
    assert align.mae is None
    assert align.high_urgency_recall is None

    fus = compute_fusion_accuracy(["single"], ["single"])
    assert fus.pairwise_precision == 1.0
    assert fus.total_pairs == 0


def test_people_at_risk_metrics_robustness():
    """Casualty metrics compute life-safety recall and casualty count MAE accurately."""
    gt_at_risk = [True, True, False, False]
    pred_at_risk = [True, False, False, True]
    gt_counts = [4, 2, 0, 0]
    pred_counts = [4, 0, 0, 1]

    rep = compute_people_at_risk_metrics(gt_at_risk, pred_at_risk, gt_counts, pred_counts)
    assert rep.binary_accuracy == 0.5
    assert rep.binary_recall == 0.5  # 1 of 2 true risks identified
    assert rep.binary_precision == 0.5  # 1 of 2 predicted risks correct
    assert rep.count_mae == 0.75  # (|4-4| + |2-0| + |0-0| + |0-1|) / 4 = 3/4 = 0.75
    assert rep.exact_count_match_rate == 0.5  # 2 of 4 exactly match (index 0 and 2)


# =============================================================================
# 4. SafeHttpTransport 422 Permanent Error Bypass
# =============================================================================

def test_safe_transport_422_unrecoverable_not_buffered():
    """A 422 Unprocessable Entity error does not trip circuit breaker and is not buffered."""
    def mock_422(payload):
        return 422, {"success": False, "error": {"code": "VALIDATION_FAILED"}}

    config = TransportConfig(endpoint="http://testserver/api/v1/reports", max_retries=1, dry_run=False)
    transport = SafeHttpTransport(config, mock_handler=mock_422)

    event = ScenarioEvent(
        event_id="evt-422",
        delay_seconds=0.0,
        dispatch=RawReportPayload(
            report_id="rep-422",
            text="Invalid report schema test",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
        ),
        ground_truth=GroundTruth(incident_group="test-422"),
    )

    res = transport.send_event(event)

    assert res.success is False
    assert res.status_code == 422
    # Verify circuit breaker was NOT tripped
    assert transport.circuit_breaker.state == CircuitState.CLOSED
    # Verify event was NOT placed in the FIFO buffer (no poison pill lockup)
    assert len(transport.buffer) == 0
    assert transport.get_metrics()["failed_dispatches"] == 1


# =============================================================================
# 5. SafeHttpTransport 429 Throttle & Rate Limit Handling
# =============================================================================

def test_safe_transport_429_retries_with_backoff():
    """A 429 Too Many Requests triggers retry and succeeds when backend recovers."""
    attempts = 0

    def mock_429_then_201(payload):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return 429, {"retry_after": 0.01}
        return 201, {"success": True, "report_id": "rep-429"}

    config = TransportConfig(endpoint="http://testserver/api/v1/reports", max_retries=2, backoff_factor=0.01, dry_run=False)
    transport = SafeHttpTransport(config, mock_handler=mock_429_then_201)

    event = ScenarioEvent(
        event_id="evt-429",
        delay_seconds=0.0,
        dispatch=RawReportPayload(
            report_id="rep-429",
            text="Rate limited report",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
        ),
        ground_truth=GroundTruth(incident_group="test-429"),
    )

    res = transport.send_event(event)

    assert res.success is True
    assert res.status_code == 201
    assert res.retries == 1
    assert len(transport.buffer) == 0


# =============================================================================
# 6. Engine Lifecycle Guards, Reentrancy, and Reset
# =============================================================================

def test_engine_lifecycle_reentrancy_and_reset():
    """Engine prevents reentrancy, manages state transitions, and resets cleanly."""
    event = ScenarioEvent(
        event_id="evt-life-001",
        delay_seconds=0.0,
        dispatch=RawReportPayload(
            report_id="rep-life-001",
            text="Lifecycle test report",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
        ),
        ground_truth=GroundTruth(incident_group="life-test"),
    )

    timeline = Timeline([event], speed=100.0)
    engine = SimulationEngine(timeline=timeline, transport=DryRunTransport())

    assert engine.state == EngineState.IDLE
    summary1 = engine.run()
    assert summary1.events_dispatched == 1
    assert engine.state == EngineState.COMPLETED

    # Running completed engine without reset raises RuntimeError
    with pytest.raises(RuntimeError, match="COMPLETED"):
        engine.run()

    # Reset engine and run again
    engine.reset()
    assert engine.state == EngineState.IDLE
    summary2 = engine.run()
    assert summary2.events_dispatched == 1
    assert engine.state == EngineState.COMPLETED


# =============================================================================
# 7. Reflection & typing.get_type_hints Across All Modules
# =============================================================================

def test_reflection_and_type_hints_across_all_modules():
    """Guarantees zero NameError or unresolved forward references during typing reflection."""
    modules = [
        simulator.models,
        simulator.timeline,
        simulator.transport,
        simulator.engine,
        simulator.cli,
        evaluation.metrics,
        evaluation.evaluate_ml,
        evaluation.evaluate_correlation,
        evaluation.run_all_evals,
    ]

    for mod in modules:
        hints = typing.get_type_hints(mod)
        assert isinstance(hints, dict)

    # Specific check on simulator.cli.main
    main_hints = typing.get_type_hints(simulator.cli.main)
    assert "args" in main_hints


# =============================================================================
# 8. ML Adapter Adversarial Input Fuzzing
# =============================================================================

def test_ml_adapter_fuzzing_resilience():
    """Adapter robustly handles malicious or unparseable inputs without unhandled exceptions."""
    # 1. Non-numeric confidence strings
    bad_conf = {
        "report_id": "rep-bad-1",
        "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": "high"},
    }
    pred1 = MLPredictionAdapter.adapt(bad_conf)
    assert pred1.is_valid is False
    assert "Invalid incident_type confidence" in pred1.validation_error

    # 2. Out-of-bounds confidence (1.5)
    bad_conf_bound = {
        "report_id": "rep-bad-2",
        "urgency": {"label": "CRITICAL", "confidence": 1.5},
    }
    pred2 = MLPredictionAdapter.adapt(bad_conf_bound)
    assert pred2.is_valid is False
    assert "Invalid urgency confidence" in pred2.validation_error

    # 3. Negative casualty count
    bad_count = {
        "report_id": "rep-bad-3",
        "people_at_risk": {"count": -4},
    }
    pred3 = MLPredictionAdapter.adapt(bad_count)
    assert pred3.is_valid is False
    assert "Invalid people_at_risk count" in pred3.validation_error

    # 4. Incomplete coordinate pair
    bad_coords = {
        "report_id": "rep-bad-4",
        "location": {"text": "market", "latitude": 20.29, "longitude": None},
    }
    pred4 = MLPredictionAdapter.adapt(bad_coords)
    assert pred4.is_valid is False
    assert "Incomplete coordinate pair" in pred4.validation_error

    # 5. Out of bounds latitude (120.0)
    bad_lat = {
        "report_id": "rep-bad-5",
        "location": {"text": "market", "latitude": 120.0, "longitude": 85.0},
    }
    pred5 = MLPredictionAdapter.adapt(bad_lat)
    assert pred5.is_valid is False
    assert "Latitude out of bounds" in pred5.validation_error


# =============================================================================
# 9. Allowlist Public Payload Egress
# =============================================================================

def test_scenario_event_allowlist_public_payload():
    """Event public payload contains only approved metadata fields and strictly filters GT."""
    event = ScenarioEvent(
        event_id="evt-allow-001",
        delay_seconds=0.0,
        dispatch=RawReportPayload(
            report_id="rep-allow-001",
            text="Allowlist test text",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
            metadata=ReportMetadata(
                scenario_id="flood_sim",
                event_id="evt-allow-001",
                reporter_id="sim-source-001",
                channel="citizen_call",
            ),
        ),
        ground_truth=GroundTruth(
            incident_group="secret-group",
            expected_urgency=GroundTruthUrgency.CRITICAL,
            notes="Secret evaluator notes",
        ),
    )

    payload = event.public_payload()
    assert payload["report_id"] == "rep-allow-001"
    assert "ground_truth" not in payload
    assert "incident_group" not in payload
    assert "expected_urgency" not in payload

    meta = payload["metadata"]
    assert meta["scenario_id"] == "flood_sim"
    assert meta["event_id"] == "evt-allow-001"
    assert meta["reporter_id"] == "sim-source-001"
    assert "notes" not in meta
    assert "expected_urgency" not in meta


# =============================================================================
# 10. End-to-End CLI Benchmark Runner with External Files
# =============================================================================

def test_run_all_evals_cli_with_external_files(tmp_path: Path):
    """CLI runner correctly ingests external JSON prediction files and writes reports."""
    ml_file = tmp_path / "mock_ml.json"
    corr_file = tmp_path / "mock_corr.json"
    lat_file = tmp_path / "latencies.json"

    # Minimal dummy prediction file
    ml_data = [
        {
            "report_id": "rep-fld-001",
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.9},
            "urgency": {"label": "LOW", "confidence": 0.8},
            "location": {"text": "Rasulgarh", "latitude": 20.296, "longitude": 85.824},
            "people_at_risk": {"count": 0},
            "required_response": [],
        }
    ]
    with open(ml_file, "w", encoding="utf-8") as f:
        json.dump(ml_data, f)

    with open(corr_file, "w", encoding="utf-8") as f:
        json.dump([{"incident_id": "inc-flood", "relationship": "INITIAL", "priority_score": 50.0, "rank": 1}], f)

    with open(lat_file, "w", encoding="utf-8") as f:
        json.dump([12.5, 18.2, 14.9], f)

    ret = run_all_evals_main([
        "--output-dir", str(tmp_path),
        "--ml-predictions", str(ml_file),
        "--backend-results", str(corr_file),
        "--latency-results", str(lat_file),
        "--quiet",
    ])
    assert ret == 0

    json_report = tmp_path / "evaluation_scorecard.json"
    md_report = tmp_path / "evaluation_scorecard.md"
    assert json_report.exists()
    assert md_report.exists()

    with open(json_report, "r", encoding="utf-8") as f:
        rep_dict = json.load(f)
    assert rep_dict["is_real_system_result"] is True
    assert rep_dict["latency_profile"]["is_measured"] is True
    assert rep_dict["latency_profile"]["sample_count"] == 3


# =============================================================================
# 11. Anti-Leakage Adversarial Attack Vectors
# =============================================================================

def test_anti_leakage_adversarial_vectors():
    """Verifies that all 6 attack vectors from Section 9 fail to leak private ground truth."""
    gt = GroundTruth(
        incident_group="secret-bbsr-cluster-42",
        expected_urgency=GroundTruthUrgency.CRITICAL,
        expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
        expected_people_at_risk=True,
        expected_people_count=7,
        notes="Classified operator notes not for broadcast",
    )
    meta = ReportMetadata(
        scenario_id="flood_rasulgarh",
        event_id="evt-sec-001",
    )
    dispatch = RawReportPayload(
        report_id="rep-sec-001",
        text="Water reaching dangerous levels near the market",
        source="simulator",
        is_synthetic=True,
        reported_at=datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc),
        metadata=meta,
    )
    event = ScenarioEvent(
        event_id="evt-sec-001",
        delay_seconds=0.0,
        dispatch=dispatch,
        ground_truth=gt,
    )

    # Attack Vector 1: String representation of dispatch
    disp_str = str(event.dispatch)
    for forbidden in ["secret-bbsr-cluster-42", "Classified operator notes", "expected_urgency"]:
        assert forbidden not in disp_str

    # Attack Vector 2: Serialization of dispatch
    dumped_json = event.dispatch.model_dump_json()
    for forbidden in ["secret-bbsr-cluster-42", "Classified operator notes", "expected_urgency", "incident_group"]:
        assert forbidden not in dumped_json

    # Attack Vector 3: Public payload egress projection
    pub_payload = event.public_payload()
    assert "ground_truth" not in pub_payload
    assert "incident_group" not in pub_payload
    for forbidden in ["secret-bbsr-cluster-42", "Classified operator notes"]:
        assert forbidden not in str(pub_payload)

    # Attack Vector 4: Metadata injection attempt
    injected_meta = {
        "scenario_id": "flood",
        "expected_urgency": "CRITICAL",
    }
    with pytest.raises(Exception):
        simulator.models.verify_no_ground_truth_leakage(injected_meta)

    # Attack Vector 5: Recursive firewall catches nested list / dict injection
    nested_attack = {
        "metadata": {
            "safe_key": "ok",
            "nested_list": [{"harmless": 1}, {"incident_group": "leak"}],
        }
    }
    with pytest.raises(simulator.models.GroundTruthLeakageError):
        simulator.models.verify_no_ground_truth_leakage(nested_attack)

    # Attack Vector 6: Normalized key variations (spaces, underscores, case folding)
    obfuscated_attack = {"E_X_P_E_C_T_E_D_U_R_G_E_N_C_Y": "CRITICAL"}
    with pytest.raises(simulator.models.GroundTruthLeakageError):
        simulator.models.verify_no_ground_truth_leakage(obfuscated_attack)


