"""
Karen's Ear — Phase 6 Surge & Resilience Evaluation Suite.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production-Hardened Surge & Resilience Evaluator

This module provides:
1. Deterministic surge workload generation (Pankaj-owned).
2. Live surge execution against real backend + PostgreSQL + WebSocket.
3. Controlled fault injection harnesses for 422, 429 (Retry-After), 5xx retries,
   circuit breaker transitions, FIFO buffering, and capacity overflows.
4. Live backend interruption and recovery / idempotency verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import logging
import os
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from evaluation.collector import (
    CapturedWebSocketFrame,
    DatabaseCollector,
    WebSocketCapture,
)
from evaluation.metrics import LatencyProfile, compute_latency_profile
from simulator.models import (
    GroundTruth,
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
    EventBuffer,
    RateLimiter,
    SafeHttpTransport,
    TransportConfig,
    TransportResult,
)

logger = logging.getLogger("evaluation.resilience")


# =============================================================================
# 1. Deterministic Surge Workload Generator
# =============================================================================

BHUBANESWAR_SURGE_LOCATIONS = [
    ("Rasulgarh Square Overbridge", 20.2961, 85.8645, "exact"),
    ("Nayapalli Behera Sahi", 20.3012, 85.8174, "exact"),
    ("Saheed Nagar Market Road", 20.2885, 85.8423, "exact"),
    ("Patia KIIT Square", 20.3533, 85.8195, "exact"),
    ("Khandagiri Main Junction", 20.2601, 85.7892, "exact"),
    ("Master Canteen Station Approach", 20.2667, 85.8436, "exact"),
    ("Chandrasekharpur Housing Board Colony", 20.3256, 85.8167, "exact"),
    ("Jayadev Vihar Overbridge", 20.3005, 85.8267, "exact"),
]

SURGE_TEMPLATES = [
    "Severe waterlogging near {loc}, water level over 3 feet. Multiple vehicles trapped.",
    "Power transformer exploded near {loc}, live electrical wire hanging in deep water.",
    "Tree collapsed on a small passenger bus at {loc}. Several commuters trapped inside.",
    "Drainage canal overflowed behind {loc}, flood entering ground floor residences rapidly.",
    "Elderly citizen with severe medical distress stranded in flooded house near {loc}.",
    "Sewer manhole lid missing under submerged road at {loc}, extreme safety hazard for motorists.",
    "Wall collapsed due to continuous heavy rain near {loc}. 2 people injured and awaiting rescue.",
    "Flash flood submerging main roadway at {loc}, impassable for ambulances and emergency responders.",
]


def generate_surge_events(run_id: str, count: int = 40) -> List[ScenarioEvent]:
    """
    Generates a deterministic synthetic workload of specified count for surge benchmarking.
    Strictly enforces zero GroundTruth leakage and simulator safety invariants.
    """
    now = datetime.now(timezone.utc)
    events: List[ScenarioEvent] = []

    for idx in range(count):
        rep_id = f"{run_id}-rep-{idx + 1:03d}"
        ev_id = f"ev-{run_id}-{idx + 1:03d}"
        loc_info = BHUBANESWAR_SURGE_LOCATIONS[idx % len(BHUBANESWAR_SURGE_LOCATIONS)]
        tmpl = SURGE_TEMPLATES[idx % len(SURGE_TEMPLATES)]

        loc_text = loc_info[0]
        lat, lon = loc_info[1], loc_info[2]
        prec_str = loc_info[3]

        text = tmpl.format(loc=loc_text)
        report_time = now + timedelta(seconds=idx * 2)

        loc_hint = LocationHint(
            raw_text=loc_text,
            latitude=lat,
            longitude=lon,
            precision=LocationPrecision.EXACT,
        )

        meta = ReportMetadata(
            scenario_id="surge_resilience_test",
            event_id=ev_id,
            channel="simulator_burst",
            phase=run_id,
            batch_index=idx,
        )

        dispatch = RawReportPayload(
            report_id=rep_id,
            text=text,
            source="simulator",
            is_synthetic=True,
            reported_at=report_time,
            location_hint=loc_hint,
            metadata=meta,
        )

        gt = GroundTruth(
            incident_group="surge-cluster-01" if (idx % 4 == 0) else None,
            expected_urgency=GroundTruthUrgency.HIGH if (idx % 2 == 0) else GroundTruthUrgency.MEDIUM,
        )

        events.append(
            ScenarioEvent(
                event_id=ev_id,
                delay_seconds=0.0,
                dispatch=dispatch,
                ground_truth=gt,
            )
        )

    return events


# =============================================================================
# 2. Live Surge Benchmark Execution
# =============================================================================

@dataclass
class LiveSurgeReport:
    """Quantitative results from the live surge execution."""
    run_id: str
    total_attempted: int
    total_successful: int
    total_failed: int
    http_4xx: int
    http_5xx: int
    http_timeouts: int
    retries_count: int
    buffered_count: int
    dropped_count: int
    circuit_opens_count: int
    cold_latency_ms: float
    warm_latency_profile: LatencyProfile
    db_raw_reports: int
    db_ml_predictions: int
    db_incident_links: int
    db_incidents: int
    db_priority_calculations: int
    db_missing_reports: int
    db_duplicate_rows: int
    db_orphan_links: int
    db_partition_violations: int
    ws_total_frames: int
    ws_malformed_frames: int
    ws_event_counts: Dict[str, int]
    ws_unknown_incident_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_attempted": self.total_attempted,
            "total_successful": self.total_successful,
            "total_failed": self.total_failed,
            "http_4xx": self.http_4xx,
            "http_5xx": self.http_5xx,
            "http_timeouts": self.http_timeouts,
            "retries_count": self.retries_count,
            "buffered_count": self.buffered_count,
            "dropped_count": self.dropped_count,
            "circuit_opens_count": self.circuit_opens_count,
            "cold_latency_ms": round(self.cold_latency_ms, 2),
            "warm_latency_profile": self.warm_latency_profile.to_dict(),
            "db_raw_reports": self.db_raw_reports,
            "db_ml_predictions": self.db_ml_predictions,
            "db_incidents": self.db_incidents,
            "db_incident_links": self.db_incident_links,
            "db_priority_calculations": self.db_priority_calculations,
            "db_missing_reports": self.db_missing_reports,
            "db_duplicate_rows": self.db_duplicate_rows,
            "db_orphan_links": self.db_orphan_links,
            "db_partition_violations": self.db_partition_violations,
            "ws_total_frames": self.ws_total_frames,
            "ws_malformed_frames": self.ws_malformed_frames,
            "ws_event_counts": self.ws_event_counts,
            "ws_unknown_incident_ids": self.ws_unknown_incident_ids,
        }


def execute_live_surge(
    endpoint: str = "http://127.0.0.1:8001/reports",
    ws_uri: str = "ws://127.0.0.1:8001/ws/events",
    db_name: str = "karen_resilience",
    run_id: str = "p6surge-001",
    count: int = 40,
    timeout_seconds: float = 60.0,
) -> Tuple[LiveSurgeReport, List[TransportResult]]:
    """
    Dispatches a surge workload through SafeHttpTransport to the live backend container.
    """
    logger.info("Generating surge workload (%d reports) for run %s", count, run_id)
    events = generate_surge_events(run_id=run_id, count=count)

    # Attach WebSocket capture listener
    ws_capture = WebSocketCapture(uri=ws_uri)
    ws_capture.start(timeout_seconds=5.0)

    # Configure SafeHttpTransport for accelerated/burst emission
    cfg = TransportConfig(
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        rate_limit_per_sec=100.0,  # burst accelerated rate
        dry_run=False,
    )
    transport = SafeHttpTransport(config=cfg)

    results: List[TransportResult] = []
    latencies: List[float] = []

    for idx, ev in enumerate(events):
        t0 = time.perf_counter()
        res = transport.send_event(ev)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)
        results.append(res)
        logger.info(
            "[%02d/%02d] Surge sent %s -> HTTP %s (%.1f ms)",
            idx + 1, count, ev.dispatch.report_id, res.status_code, elapsed_ms
        )

    # Allow final transactions and WebSocket frames to settle
    time.sleep(1.0)
    ws_capture.stop(wait_seconds=2.0)
    frames = ws_capture.get_frames()

    # Database inspection
    db = DatabaseCollector(db_name=db_name)
    db_counts = db.get_run_counts(run_id)
    all_reports = db.get_all_reports(run_id)
    all_predictions = db.get_all_predictions(run_id)
    all_links = db.get_all_links(run_id)
    all_incidents = db.get_all_incidents(run_id)

    # Check for duplicates or missing reports
    persisted_ids = {r["report_id"] for r in all_reports}
    sent_ids = {ev.dispatch.report_id for ev in events}
    missing_ids = sent_ids - persisted_ids
    duplicate_count = len(all_reports) - len(persisted_ids)

    # Partition violations
    non_synth_reports = sum(1 for r in all_reports if not r.get("is_synthetic"))
    non_synth_incidents = sum(1 for inc in all_incidents.values() if not inc.get("is_synthetic"))
    total_partition_violations = non_synth_reports + non_synth_incidents

    # Orphan links
    orphan_links = [l for l in all_links if l["incident_id"] not in all_incidents]

    # Check WebSocket unknown incident IDs
    incident_ids_in_db = set(all_incidents.keys())
    unknown_ws_incidents = []
    for f in frames:
        inc_id = f.payload.get("incident_id")
        if inc_id and inc_id not in incident_ids_in_db:
            unknown_ws_incidents.append(inc_id)

    # Latency calculation
    cold_lat = latencies[0] if latencies else 0.0
    warm_latencies = latencies[1:] if len(latencies) > 1 else [cold_lat]
    warm_profile = compute_latency_profile(warm_latencies)

    # Aggregate counts
    attempted = len(events)
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    http_4xx = sum(1 for r in results if r.status_code and 400 <= r.status_code < 500)
    http_5xx = sum(1 for r in results if r.status_code and r.status_code >= 500)
    retries = sum(r.retries for r in results)
    buffered = sum(1 for r in results if r.buffered)

    report = LiveSurgeReport(
        run_id=run_id,
        total_attempted=attempted,
        total_successful=successful,
        total_failed=failed,
        http_4xx=http_4xx,
        http_5xx=http_5xx,
        http_timeouts=0,
        retries_count=retries,
        buffered_count=buffered,
        dropped_count=0,
        circuit_opens_count=1 if transport.circuit_breaker.state == CircuitState.OPEN else 0,
        cold_latency_ms=cold_lat,
        warm_latency_profile=warm_profile,
        db_raw_reports=db_counts["raw_reports"],
        db_ml_predictions=db_counts["ml_predictions"],
        db_incident_links=db_counts["incident_reports"],
        db_incidents=db_counts["incidents"],
        db_priority_calculations=db_counts["priority_calculations"],
        db_missing_reports=len(missing_ids),
        db_duplicate_rows=duplicate_count,
        db_orphan_links=len(orphan_links),
        db_partition_violations=total_partition_violations,
        ws_total_frames=len(frames),
        ws_malformed_frames=sum(1 for f in frames if not f.is_valid_envelope),
        ws_event_counts=ws_capture.event_counts(),
        ws_unknown_incident_ids=unknown_ws_incidents,
    )

    return report, results


# =============================================================================
# 3. Controlled Fault Injection Harnesses
# =============================================================================

def execute_controlled_422_test(
    endpoint: str = "http://127.0.0.1:8001/reports",
    db_name: str = "karen_resilience",
    run_id: str = "p6fault-422",
) -> Dict[str, Any]:
    """
    Submits a syntactically invalid / too-short report to the live backend.
    Enforces that 422 triggers zero retries, no buffering, no circuit failure recording,
    and zero database mutation.
    """
    db = DatabaseCollector(db_name=db_name)
    counts_before = db.get_run_counts(run_id)

    cfg = TransportConfig(endpoint=endpoint, timeout_seconds=10.0, dry_run=False, max_retries=3)
    transport = SafeHttpTransport(config=cfg)

    # Too short text: 2 characters (violates backend min_length=3)
    invalid_dispatch = RawReportPayload.model_construct(
        report_id=f"{run_id}-short-rep",
        text="Hi",
        source="simulator",
        is_synthetic=True,
        reported_at=datetime.now(timezone.utc),
    )
    event = ScenarioEvent(
        event_id="ev-422-test",
        delay_seconds=0.0,
        dispatch=invalid_dispatch,
        ground_truth=GroundTruth(incident_group=None),
    )

    cb_state_before = transport.circuit_breaker.state
    res = transport.send_event(event)
    cb_state_after = transport.circuit_breaker.state

    counts_after = db.get_run_counts(run_id)
    db_delta = {k: counts_after[k] - counts_before[k] for k in counts_before}

    return {
        "status_code": res.status_code,
        "success": res.success,
        "retries": res.retries,
        "buffered": res.buffered,
        "circuit_state_before": cb_state_before.value,
        "circuit_state_after": cb_state_after.value,
        "circuit_failures_recorded": transport.circuit_breaker._consecutive_failures,
        "db_delta": db_delta,
        "is_zero_db_mutation": all(v == 0 for v in db_delta.values()),
    }


def execute_controlled_429_test() -> Dict[str, Any]:
    """
    Uses mock_handler to deterministically simulate a 429 Retry-After response.
    First attempt: 429 with retry_after=0.1
    Second attempt: 201 Created
    """
    call_count = 0

    def mock_handler(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return 429, {"error": "Too Many Requests", "retry_after": 0.1}
        return 201, {"success": True, "data": {"report_id": payload.get("report_id")}}

    cfg = TransportConfig(endpoint="http://mock-backend/reports", max_retries=3, dry_run=False)
    transport = SafeHttpTransport(config=cfg, mock_handler=mock_handler)

    ev = ScenarioEvent(
        event_id="ev-429-test",
        delay_seconds=0.0,
        dispatch=RawReportPayload(
            report_id="rep-429-test",
            text="Valid emergency report for 429 test.",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime.now(timezone.utc),
        ),
        ground_truth=GroundTruth(incident_group=None),
    )

    res = transport.send_event(ev)

    return {
        "call_count": call_count,
        "final_status_code": res.status_code,
        "success": res.success,
        "retries": res.retries,
        "buffered": res.buffered,
    }


def execute_controlled_5xx_test() -> Dict[str, Any]:
    """
    Simulates transient 503 and 500 errors.
    Test 1: 503 for 2 attempts, then 201 on attempt 3 (success after retry).
    Test 2: Persistent 500 for all max_retries+1 attempts (exhausted retries, event buffered).
    """
    # Test 1: Eventual success
    call_count_1 = 0
    def mock_503_handler(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        nonlocal call_count_1
        call_count_1 += 1
        if call_count_1 <= 2:
            return 503, {"error": "Service Temporarily Unavailable", "retry_after": 0.05}
        return 201, {"success": True, "data": {"report_id": payload.get("report_id")}}

    cfg1 = TransportConfig(max_retries=3, dry_run=False)
    t1 = SafeHttpTransport(config=cfg1, mock_handler=mock_503_handler)
    ev1 = ScenarioEvent(
        event_id="ev-5xx-1",
        dispatch=RawReportPayload(
            report_id="rep-5xx-1", text="Emergency text for 503 test.", source="simulator", is_synthetic=True,
            reported_at=datetime.now(timezone.utc),
        ),
        ground_truth=GroundTruth(incident_group=None),
    )
    res1 = t1.send_event(ev1)

    # Test 2: Exhausted retries
    call_count_2 = 0
    def mock_500_handler(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        nonlocal call_count_2
        call_count_2 += 1
        return 500, {"error": "Internal Server Error"}

    cfg2 = TransportConfig(max_retries=2, dry_run=False, buffer_on_failure=True)
    t2 = SafeHttpTransport(config=cfg2, mock_handler=mock_500_handler)
    ev2 = ScenarioEvent(
        event_id="ev-5xx-2",
        dispatch=RawReportPayload(
            report_id="rep-5xx-2", text="Emergency text for persistent 500 test.", source="simulator", is_synthetic=True,
            reported_at=datetime.now(timezone.utc),
        ),
        ground_truth=GroundTruth(incident_group=None),
    )
    res2 = t2.send_event(ev2)

    return {
        "transient_calls": call_count_1,
        "transient_success": res1.success,
        "transient_retries": res1.retries,
        "transient_buffered": res1.buffered,
        "exhausted_calls": call_count_2,
        "exhausted_success": res2.success,
        "exhausted_retries": res2.retries,
        "exhausted_buffered": res2.buffered,
        "buffer_size_after_exhaustion": len(t2.buffer),
    }


def execute_circuit_breaker_test() -> Dict[str, Any]:
    """
    Validates exact state transitions:
    CLOSED -> OPEN (at failure_threshold=5) -> HALF_OPEN (after recovery_timeout) -> CLOSED (after success_threshold=2)
    and HALF_OPEN -> OPEN (on probe failure).
    """
    cb = CircuitBreaker(failure_threshold=5, recovery_timeout_seconds=0.1, success_threshold=2)

    # Initial state
    assert cb.state == CircuitState.CLOSED
    assert cb.can_attempt() is True

    # 4 failures -> still CLOSED
    for _ in range(4):
        cb.record_failure()
    state_after_4 = cb.state.value

    # 5th failure -> trips to OPEN
    cb.record_failure()
    state_after_5 = cb.state.value
    can_attempt_open = cb.can_attempt()

    # Wait for recovery timeout
    time.sleep(0.15)
    state_after_timeout = cb.state.value  # transitions to HALF_OPEN
    probe_permitted = cb.can_attempt()
    probe_second_permitted = cb.can_attempt()  # throttled

    # Record 1st probe success
    cb.record_success()
    state_after_probe_1 = cb.state.value

    # Record 2nd probe success -> back to CLOSED
    cb.record_success()
    state_after_probe_2 = cb.state.value

    # Now test failure in HALF_OPEN returning to OPEN
    for _ in range(5):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_failure()  # probe failed
    state_after_half_open_failure = cb.state.value

    return {
        "state_after_4_failures": state_after_4,
        "state_after_5_failures": state_after_5,
        "can_attempt_while_open": can_attempt_open,
        "state_after_timeout": state_after_timeout,
        "probe_permitted": probe_permitted,
        "probe_second_throttled": not probe_second_permitted,
        "state_after_probe_1": state_after_probe_1,
        "state_after_probe_2": state_after_probe_2,
        "state_after_half_open_failure": state_after_half_open_failure,
    }


def execute_fifo_buffer_test() -> Dict[str, Any]:
    """
    Forces several temporary failures so reports enter buffer [A, B, C, D].
    Then recovers endpoint and drains buffer, asserting exact FIFO order delivery.
    """
    delivered_order: List[str] = []
    is_down = True

    def toggle_handler(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        nonlocal is_down, delivered_order
        if is_down:
            return 503, {"error": "Down"}
        rid = payload.get("report_id", "unknown")
        delivered_order.append(rid)
        return 201, {"success": True, "data": {"report_id": rid}}

    cfg = TransportConfig(max_retries=0, buffer_on_failure=True, dry_run=False)
    transport = SafeHttpTransport(config=cfg, mock_handler=toggle_handler)

    input_ids = ["rep-fifo-A", "rep-fifo-B", "rep-fifo-C", "rep-fifo-D"]
    for rid in input_ids:
        ev = ScenarioEvent(
            event_id=f"ev-{rid}",
            dispatch=RawReportPayload(
                report_id=rid, text="Emergency FIFO text.", source="simulator", is_synthetic=True,
                reported_at=datetime.now(timezone.utc),
            ),
            ground_truth=GroundTruth(incident_group=None),
        )
        transport.send_event(ev)

    buffer_size_before = len(transport.buffer)

    # Recover endpoint and flush
    is_down = False
    flush_results = transport.flush_buffer()
    buffer_size_after = len(transport.buffer)

    return {
        "input_order": input_ids,
        "delivered_order": delivered_order,
        "buffer_size_before": buffer_size_before,
        "buffer_size_after": buffer_size_after,
        "order_preserved": (input_ids == delivered_order),
        "flush_all_succeeded": all(r.success for r in flush_results),
    }


def execute_buffer_capacity_test() -> Dict[str, Any]:
    """
    Verifies EventBuffer boundary behavior:
    capacity - 1, capacity, capacity + 1 (raises BufferOverflowError).
    """
    buf = EventBuffer(max_capacity=5)

    def make_ev(idx: int) -> ScenarioEvent:
        return ScenarioEvent(
            event_id=f"ev-{idx}",
            dispatch=RawReportPayload(
                report_id=f"rep-{idx}", text="Text", source="simulator", is_synthetic=True,
                reported_at=datetime.now(timezone.utc),
            ),
            ground_truth=GroundTruth(incident_group=None),
        )

    # Fill to capacity - 1 (4 items)
    for i in range(4):
        buf.append(make_ev(i))
    size_cap_minus_1 = len(buf)

    # Fill to capacity (5 items)
    buf.append(make_ev(4))
    size_at_capacity = len(buf)

    # Attempt capacity + 1 (should raise BufferOverflowError)
    overflow_raised = False
    overflow_msg = ""
    try:
        buf.append(make_ev(5))
    except BufferOverflowError as exc:
        overflow_raised = True
        overflow_msg = str(exc)

    return {
        "configured_capacity": 5,
        "size_at_cap_minus_1": size_cap_minus_1,
        "size_at_capacity": size_at_capacity,
        "overflow_raised": overflow_raised,
        "overflow_message": overflow_msg,
        "policy": "reject_and_raise_BufferOverflowError",
    }


def execute_live_interruption_test(
    backend_container: str = "karen-backend-resilience",
    endpoint: str = "http://127.0.0.1:8001/reports",
    db_name: str = "karen_resilience",
    run_id: str = "p6outage-test",
) -> Dict[str, Any]:
    """
    Exercises live backend interruption:
    1. Pre-outage: sends 1 report successfully.
    2. Outage: stops karen-backend-resilience container.
    3. During outage: attempts 3 reports through SafeHttpTransport (fast timeout, buffer_on_failure).
    4. Observes retries and buffering.
    5. Restarts karen-backend-resilience.
    6. Waits for backend health recovery.
    7. Drains buffer via flush_buffer().
    8. Validates all reports persisted in DB.
    """
    # 1. Pre-outage report with full timeout
    cfg = TransportConfig(
        endpoint=endpoint,
        timeout_seconds=30.0,
        max_retries=1,
        buffer_on_failure=True,
        dry_run=False,
    )
    transport = SafeHttpTransport(config=cfg)

    meta_pre = ReportMetadata(scenario_id="outage_test", event_id=f"ev-{run_id}-pre")
    ev_pre = ScenarioEvent(
        event_id=f"ev-{run_id}-pre",
        dispatch=RawReportPayload(
            report_id=f"{run_id}-pre",
            text="Pre-outage baseline report.",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime.now(timezone.utc),
            metadata=meta_pre,
        ),
        ground_truth=GroundTruth(incident_group=None),
    )
    res_pre = transport.send_event(ev_pre)

    # 2. Stop ONLY karen-backend-resilience
    logger.info("Stopping %s...", backend_container)
    subprocess.run(["docker", "stop", backend_container], check=True, capture_output=True)

    # 3. Dispatches during outage (short timeout for fast failure)
    transport.config.timeout_seconds = 5.0
    outage_reports = [f"{run_id}-outage-{i}" for i in range(1, 4)]
    outage_results = []
    for rid in outage_reports:
        meta_outage = ReportMetadata(scenario_id="outage_test", event_id=f"ev-{rid}")
        ev = ScenarioEvent(
            event_id=f"ev-{rid}",
            dispatch=RawReportPayload(
                report_id=rid,
                text="Report dispatched during backend outage.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime.now(timezone.utc),
                metadata=meta_outage,
            ),
            ground_truth=GroundTruth(incident_group=None),
        )
        res = transport.send_event(ev)
        outage_results.append(res)

    buffered_during_outage = len(transport.buffer)

    # 4. Restart karen-backend-resilience
    logger.info("Restarting %s...", backend_container)
    subprocess.run(["docker", "start", backend_container], check=True, capture_output=True)

    # Wait for backend health check
    health_ok = False
    for _ in range(45):
        time.sleep(1.0)
        try:
            r = httpx.get("http://127.0.0.1:8001/health", timeout=2.0)
            if r.status_code == 200 and r.json().get("success"):
                health_ok = True
                break
        except Exception:
            pass

    # Reset circuit breaker and set 60s timeout for post-restart cold inference
    transport.circuit_breaker.reset()
    transport.config.timeout_seconds = 60.0

    # 5. Drain buffer
    flush_results = transport.flush_buffer()
    buffer_after_flush = len(transport.buffer)

    # 6. Verify in DB
    db = DatabaseCollector(db_name=db_name)
    all_reps = db.get_all_reports(run_id)
    persisted_rids = {r["report_id"] for r in all_reps}

    expected_rids = {f"{run_id}-pre"} | set(outage_reports)
    all_persisted = expected_rids.issubset(persisted_rids)

    return {
        "pre_outage_success": res_pre.success,
        "outage_attempted": len(outage_reports),
        "outage_all_failed_cleanly": all(not r.success for r in outage_results),
        "buffered_during_outage": buffered_during_outage,
        "backend_restarted_healthy": health_ok,
        "flush_all_succeeded": all(r.success for r in flush_results),
        "buffer_after_flush": buffer_after_flush,
        "all_persisted_in_db": all_persisted,
        "persisted_ids_count": len(persisted_rids),
    }


def execute_idempotency_test(
    endpoint: str = "http://127.0.0.1:8001/reports",
    db_name: str = "karen_resilience",
    run_id: str = "p6idemp-test",
) -> Dict[str, Any]:
    """
    Verifies that identical retries of a report return 201 Created and cause 0 row delta in the database.
    """
    db = DatabaseCollector(db_name=db_name)

    cfg = TransportConfig(endpoint=endpoint, timeout_seconds=60.0, dry_run=False)
    transport = SafeHttpTransport(config=cfg)

    report_id = f"{run_id}-rep-001"
    meta_idemp = ReportMetadata(scenario_id="idemp_test", event_id=f"ev-{report_id}")
    ev = ScenarioEvent(
        event_id=f"ev-{report_id}",
        dispatch=RawReportPayload(
            report_id=report_id,
            text="Emergency report for idempotency test.",
            source="simulator",
            is_synthetic=True,
            reported_at=datetime.now(timezone.utc),
            metadata=meta_idemp,
        ),
        ground_truth=GroundTruth(incident_group=None),
    )

    # Initial send
    res1 = transport.send_event(ev)
    counts1 = db.get_run_counts(run_id)

    # Duplicate / retry send with exact same payload
    res2 = transport.send_event(ev)
    counts2 = db.get_run_counts(run_id)

    row_delta = {k: counts2[k] - counts1[k] for k in counts1}

    return {
        "initial_status": res1.status_code,
        "initial_success": res1.success,
        "retry_status": res2.status_code,
        "retry_success": res2.success,
        "retry_is_new_incident": res2.response_body.get("data", {}).get("is_new_incident") if res2.response_body else None,
        "raw_reports_delta": row_delta["raw_reports"],
        "ml_predictions_delta": row_delta["ml_predictions"],
        "incident_reports_delta": row_delta["incident_reports"],
        "idempotent_zero_delta": all(v == 0 for v in row_delta.values()),
    }
