"""
Karen's Ear — Full E2E & WebSocket Benchmark Collector.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production-Hardened End-to-End Live Benchmark Collector

This module provides:
1. WebSocketCapture: Background thread capturing /ws/events frames.
2. DatabaseCollector: Read-only run-scoped PostgreSQL state queries.
3. E2ERunner: Orchestrates live 27-report scenario dispatch via SafeHttpTransport.
4. E2EEvaluationReport: Comprehensive quantitative scorecard adhering to Phase 5 requirements.
"""
from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
import uuid

import httpx
import websockets

from evaluation.metrics import (
    ClassificationReport,
    FusionAccuracyReport,
    LatencyProfile,
    compute_classification_report,
    compute_fusion_accuracy,
    compute_latency_profile,
    compute_location_metrics,
    compute_multilabel_response_metrics,
    compute_people_at_risk_metrics,
    compute_spearman_rho,
    compute_urgency_alignment,
)
from simulator.models import (
    LocationHint,
    RawReportPayload,
    ReportMetadata,
    ScenarioEvent,
    verify_no_ground_truth_leakage,
)
from simulator.scenarios import get_scenario, list_scenarios
from simulator.transport import SafeHttpTransport, TransportConfig, TransportResult

logger = logging.getLogger("evaluation.collector")


# =============================================================================
# 1. WebSocket Event Capture
# =============================================================================

@dataclass
class CapturedWebSocketFrame:
    """Represents a validated incoming WebSocket frame."""
    raw_text: str
    event: str
    payload: Dict[str, Any]
    timestamp: str
    is_valid_envelope: bool
    received_at_monotonic: float


class WebSocketCapture:
    """
    Background WebSocket listener for ws://127.0.0.1:8000/ws/events.
    Captures and validates all incoming real-time broadcast frames thread-safely.
    """

    def __init__(self, uri: str = "ws://127.0.0.1:8000/ws/events") -> None:
        self.uri = uri
        self.frames: List[CapturedWebSocketFrame] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._connected_event = threading.Event()
        self._lock = threading.Lock()
        self.connection_error: Optional[str] = None

    def start(self, timeout_seconds: float = 5.0) -> bool:
        """Starts the WebSocket capture loop in a background daemon thread."""
        self._stop_event.clear()
        self._connected_event.clear()
        self.connection_error = None

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Wait until connection is established or timeout expires
        connected = self._connected_event.wait(timeout=timeout_seconds)
        if not connected and self.connection_error:
            logger.error("Failed to connect WebSocket: %s", self.connection_error)
        return connected

    def stop(self, wait_seconds: float = 2.0) -> None:
        """Signals the background loop to disconnect and joins thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=wait_seconds)

    def _run_loop(self) -> None:
        """Asyncio event loop runner inside the thread."""
        asyncio.run(self._async_listen())

    async def _async_listen(self) -> None:
        """Connects and streams frames until _stop_event is set."""
        try:
            async with websockets.connect(self.uri) as ws:
                self._connected_event.set()
                logger.info("WebSocketCapture connected to %s", self.uri)

                while not self._stop_event.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.2)
                        t_recv = time.monotonic()
                        self._process_frame(str(raw), t_recv)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("WebSocket connection closed by server")
                        break
        except Exception as exc:
            self.connection_error = str(exc)
            logger.warning("WebSocketCapture encountered error: %s", exc)
        finally:
            self._connected_event.set()

    def _process_frame(self, raw_text: str, t_recv: float) -> None:
        """Validates envelope and records frame."""
        event_name = "UNKNOWN"
        payload_data: Dict[str, Any] = {}
        timestamp_str = ""
        is_valid = False

        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                # Canonical envelope: exactly event, payload, timestamp
                if "event" in parsed and "payload" in parsed and "timestamp" in parsed:
                    event_name = str(parsed["event"])
                    payload_data = parsed.get("payload") if isinstance(parsed.get("payload"), dict) else {}
                    timestamp_str = str(parsed.get("timestamp") or "")
                    is_valid = True
                else:
                    event_name = str(parsed.get("event") or parsed.get("type") or "MALFORMED")
                    payload_data = parsed
        except Exception:
            event_name = "MALFORMED_NON_JSON"

        frame = CapturedWebSocketFrame(
            raw_text=raw_text,
            event=event_name,
            payload=payload_data,
            timestamp=timestamp_str,
            is_valid_envelope=is_valid,
            received_at_monotonic=t_recv,
        )
        with self._lock:
            self.frames.append(frame)

    def get_frames(self) -> List[CapturedWebSocketFrame]:
        """Returns snapshot of captured frames."""
        with self._lock:
            return list(self.frames)

    def event_counts(self) -> Dict[str, int]:
        """Returns summary of counts grouped by event type."""
        with self._lock:
            return dict(Counter(f.event for f in self.frames))


# =============================================================================
# 2. Database Collector
# =============================================================================

class DatabaseCollector:
    """
    Executes read-only SQL queries against PostgreSQL to retrieve run-scoped state.
    """

    def __init__(self, db_name: str = "karen_e2e", container_name: str = "compose-postgres-1") -> None:
        self.db_name = db_name
        self.container_name = container_name

    def query_json(self, sql: str) -> List[Dict[str, Any]]:
        """Executes query in Postgres container and returns parsed JSON row dictionaries."""
        wrapped = f"SELECT coalesce(json_agg(t), '[]'::json) FROM ({sql}) t;"
        cmd = [
            "docker", "exec", self.container_name,
            "psql", "-U", "maya", "-d", self.db_name, "-t", "-A", "-c", wrapped,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = res.stdout.strip()
        if not out:
            return []
        return json.loads(out)

    def get_run_counts(self, run_id: str) -> Dict[str, int]:
        """Retrieves row counts strictly scoped to the given run_id."""
        raw_cnt = self.query_json(f"SELECT count(*) AS cnt FROM raw_reports WHERE report_id LIKE '{run_id}%'")[0]["cnt"]
        ml_cnt = self.query_json(f"SELECT count(*) AS cnt FROM ml_predictions WHERE report_id LIKE '{run_id}%'")[0]["cnt"]
        link_cnt = self.query_json(f"SELECT count(*) AS cnt FROM incident_reports WHERE report_id LIKE '{run_id}%'")[0]["cnt"]
        inc_cnt = self.query_json(f"SELECT count(DISTINCT incident_id) AS cnt FROM incident_reports WHERE report_id LIKE '{run_id}%'")[0]["cnt"]
        prio_cnt = self.query_json(f"SELECT count(*) AS cnt FROM priority_calculations WHERE incident_id IN (SELECT DISTINCT incident_id FROM incident_reports WHERE report_id LIKE '{run_id}%')")[0]["cnt"]

        return {
            "raw_reports": int(raw_cnt),
            "ml_predictions": int(ml_cnt),
            "incident_reports": int(link_cnt),
            "incidents": int(inc_cnt),
            "priority_calculations": int(prio_cnt),
        }

    def get_all_reports(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetches all raw reports for run_id."""
        sql = (
            f"SELECT report_id, source, is_synthetic, reported_at, ingested_at "
            f"FROM raw_reports WHERE report_id LIKE '{run_id}%' ORDER BY ingested_at ASC"
        )
        return self.query_json(sql)

    def get_all_predictions(self, run_id: str) -> Dict[str, Dict[str, Any]]:
        """Fetches all ML predictions mapped by report_id."""
        sql = (
            f"SELECT report_id, processing_status, model_version, cardinality(embedding) AS embedding_dimension, "
            f"incident_type, urgency, location, people_at_risk, required_response, overall_confidence "
            f"FROM ml_predictions WHERE report_id LIKE '{run_id}%'"
        )
        rows = self.query_json(sql)
        results = {}
        for r in rows:
            results[r["report_id"]] = {
                "report_id": r["report_id"],
                "processing_status": r["processing_status"],
                "model_version": r["model_version"],
                "embedding_dimension": r.get("embedding_dimension"),
                "incident_type": r.get("incident_type") or {},
                "urgency": r.get("urgency") or {},
                "location": r.get("location") or {},
                "people_at_risk": r.get("people_at_risk") or {},
                "required_response": r.get("required_response") or [],
                "overall_confidence": float(r["overall_confidence"]) if r.get("overall_confidence") is not None else None,
            }
        return results

    def get_all_links(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetches all incident_reports links for run_id."""
        sql = (
            f"SELECT report_id, incident_id, relationship_type, similarity_score, fused_at "
            f"FROM incident_reports WHERE report_id LIKE '{run_id}%' ORDER BY fused_at ASC"
        )
        rows = self.query_json(sql)
        for r in rows:
            if r.get("similarity_score") is not None:
                r["similarity_score"] = float(r["similarity_score"])
        return rows

    def get_all_incidents(self, run_id: str) -> Dict[str, Dict[str, Any]]:
        """Fetches all incidents associated with run_id."""
        sql = (
            f"SELECT incident_id, status, report_count, independent_source_count, "
            f"priority_score, priority_level, corroboration_score, is_synthetic, created_at, updated_at "
            f"FROM incidents WHERE incident_id IN (SELECT DISTINCT incident_id FROM incident_reports WHERE report_id LIKE '{run_id}%')"
        )
        rows = self.query_json(sql)
        results = {}
        for r in rows:
            results[r["incident_id"]] = {
                "incident_id": r["incident_id"],
                "status": r["status"],
                "report_count": int(r["report_count"]),
                "independent_source_count": int(r["independent_source_count"]),
                "priority_score": float(r["priority_score"]),
                "priority_level": r["priority_level"],
                "corroboration_score": float(r["corroboration_score"]),
                "is_synthetic": bool(r["is_synthetic"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        return results


# =============================================================================
# 3. E2E Evaluation Data Structures & Formulas
# =============================================================================

@dataclass
class E2EEvaluationReport:
    """
    Formal quantitative evaluation report for Phase 5 REAL_E2E benchmark.
    """
    run_id: str
    total_reports_attempted: int
    total_reports_successful: int
    http_errors_4xx: int
    http_errors_5xx: int
    http_timeouts: int
    transport_retries: int
    transport_buffered: int
    circuit_breaker_tripped: bool

    # Latency profiles
    http_cold_latency_ms: float
    http_warm_latency_profile: LatencyProfile

    # Database counts
    db_raw_reports_count: int
    db_ml_predictions_count: int
    db_incident_links_count: int
    db_incidents_count: int
    db_priority_calculations_count: int
    orphan_links_count: int
    synthetic_partition_violations: int

    # WebSocket telemetry
    websocket_connected: bool
    websocket_total_frames: int
    websocket_malformed_frames: int
    websocket_event_counts: Dict[str, int]
    websocket_unknown_incident_ids: List[str]

    # Metrics
    pairwise_fusion_accuracy: FusionAccuracyReport
    duplicate_metrics: Dict[str, Any]
    corroborating_metrics: Dict[str, Any]
    incident_critical_recall: float
    priority_score_ge_75_recall: float
    scenario_rank_1_status: str
    scenario_rank_1_passed: bool
    rank_1_tie_detected: bool
    meaningful_ranking_sample: bool
    spearman_rank_correlation: Optional[float]
    diagnostic_spearman_rho: Optional[float]

    # ML metrics from persisted records
    ml_type_macro_f1: float
    ml_urgency_accuracy: float
    ml_casualty_mae: float
    ml_location_precision_accuracy: float

    # Provenance
    evaluation_mode: str = "REAL_E2E"
    is_real_system_result: bool = True
    execution_scope: str = "LIVE_HTTP_POSTGRES_WEBSOCKET"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "evaluation_mode": self.evaluation_mode,
            "is_real_system_result": self.is_real_system_result,
            "execution_scope": self.execution_scope,
            "total_reports_attempted": self.total_reports_attempted,
            "total_reports_successful": self.total_reports_successful,
            "http_cold_latency_ms": self.http_cold_latency_ms,
            "http_warm_latency_profile": self.http_warm_latency_profile.to_dict(),
            "db_raw_reports_count": self.db_raw_reports_count,
            "db_ml_predictions_count": self.db_ml_predictions_count,
            "db_incidents_count": self.db_incidents_count,
            "db_incident_links_count": self.db_incident_links_count,
            "db_priority_calculations_count": self.db_priority_calculations_count,
            "orphan_links_count": self.orphan_links_count,
            "synthetic_partition_violations": self.synthetic_partition_violations,
            "websocket_connected": self.websocket_connected,
            "websocket_total_frames": self.websocket_total_frames,
            "websocket_malformed_frames": self.websocket_malformed_frames,
            "websocket_event_counts": self.websocket_event_counts,
            "websocket_unknown_incident_ids": self.websocket_unknown_incident_ids,
            "pairwise_fusion_accuracy": self.pairwise_fusion_accuracy.to_dict(),
            "duplicate_metrics": self.duplicate_metrics,
            "corroborating_metrics": self.corroborating_metrics,
            "incident_critical_recall": self.incident_critical_recall,
            "priority_score_ge_75_recall": self.priority_score_ge_75_recall,
            "scenario_rank_1_status": self.scenario_rank_1_status,
            "scenario_rank_1_passed": self.scenario_rank_1_passed,
            "rank_1_tie_detected": self.rank_1_tie_detected,
            "meaningful_ranking_sample": self.meaningful_ranking_sample,
            "spearman_rank_correlation": self.spearman_rank_correlation,
            "diagnostic_spearman_rho": self.diagnostic_spearman_rho,
            "ml_type_macro_f1": self.ml_type_macro_f1,
            "ml_urgency_accuracy": self.ml_urgency_accuracy,
            "ml_casualty_mae": self.ml_casualty_mae,
            "ml_location_precision_accuracy": self.ml_location_precision_accuracy,
        }


# =============================================================================
# 4. E2E Benchmark Runner
# =============================================================================

def run_full_e2e_benchmark(
    endpoint: str = "http://127.0.0.1:8000/reports",
    ws_uri: str = "ws://127.0.0.1:8000/ws/events",
    db_name: str = "karen_e2e",
    run_id_prefix: Optional[str] = None,
    timeout_seconds: float = 60.0,
) -> Tuple[E2EEvaluationReport, List[TransportResult], List[CapturedWebSocketFrame]]:
    """
    Executes the full 27-report golden scenario corpus through the live system.
    """
    if run_id_prefix is None:
        run_id_prefix = f"p5e2e-{uuid.uuid4().hex[:6]}"

    logger.info("Initiating Phase 5 REAL_E2E run: %s", run_id_prefix)

    # 1. Load scenarios in canonical order: flood_rasulgarh (15) + mixed_hard_negatives (12) = 27
    events: List[ScenarioEvent] = []
    events.extend(get_scenario("flood_rasulgarh"))
    events.extend(get_scenario("mixed_hard_negatives"))
    assert len(events) == 27, f"Expected 27 scenario events, got {len(events)}"

    # 2. Rebase timestamps relative to now() while preserving relative inter-event timing
    now = datetime.now(timezone.utc)
    base_time = events[0].dispatch.reported_at
    mapped_events: List[ScenarioEvent] = []
    orig_to_run_id_map: Dict[str, str] = {}

    for ev in events:
        orig_rep_id = ev.dispatch.report_id
        run_rep_id = f"{run_id_prefix}-{orig_rep_id}"
        orig_to_run_id_map[orig_rep_id] = run_rep_id

        offset = ev.dispatch.reported_at - base_time
        rebased_time = now + offset

        new_meta = ReportMetadata(
            scenario_id=ev.dispatch.metadata.scenario_id if ev.dispatch.metadata else "unknown",
            event_id=ev.event_id,
            reporter_id=ev.dispatch.metadata.reporter_id if ev.dispatch.metadata else None,
            caller_id=ev.dispatch.metadata.caller_id if ev.dispatch.metadata else None,
            channel=ev.dispatch.metadata.channel if ev.dispatch.metadata else None,
            phase=run_id_prefix,
            batch_index=ev.dispatch.metadata.batch_index if ev.dispatch.metadata else 0,
        )

        new_dispatch = RawReportPayload(
            report_id=run_rep_id,
            text=ev.dispatch.text,
            source="simulator",
            is_synthetic=True,
            reported_at=rebased_time,
            location_hint=ev.dispatch.location_hint,
            metadata=new_meta,
        )

        mapped_events.append(
            ScenarioEvent(
                event_id=ev.event_id,
                delay_seconds=0.0,
                dispatch=new_dispatch,
                ground_truth=ev.ground_truth,
            )
        )

    # 3. Start WebSocket capture
    ws_capture = WebSocketCapture(uri=ws_uri)
    ws_connected = ws_capture.start(timeout_seconds=5.0)

    # 4. Configure SafeHttpTransport
    transport_cfg = TransportConfig(
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        rate_limit_per_sec=100.0,  # accelerated execution
        dry_run=False,
    )
    transport = SafeHttpTransport(config=transport_cfg)

    # 5. Dispatch dispatches synchronously in scenario sequence
    transport_results: List[TransportResult] = []
    http_latencies_ms: List[float] = []

    for idx, ev in enumerate(mapped_events):
        t0 = time.perf_counter()
        res = transport.send_event(ev)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        http_latencies_ms.append(elapsed_ms)
        transport_results.append(res)
        logger.info(
            "[%02d/27] Sent %s: HTTP %s (%.1f ms)",
            idx + 1,
            ev.dispatch.report_id,
            res.status_code,
            elapsed_ms,
        )

    # 6. Graceful wait for final DB commit and WebSocket event propagation
    time.sleep(1.0)
    ws_capture.stop(wait_seconds=2.0)
    captured_frames = ws_capture.get_frames()

    # 7. Collect database records
    db_collector = DatabaseCollector(db_name=db_name)
    db_counts = db_collector.get_run_counts(run_id_prefix)
    db_reports = db_collector.get_all_reports(run_id_prefix)
    db_predictions = db_collector.get_all_predictions(run_id_prefix)
    db_links = db_collector.get_all_links(run_id_prefix)
    db_incidents = db_collector.get_all_incidents(run_id_prefix)

    # 8. Check integrity and partition rules
    orphan_links = [l for l in db_links if l["incident_id"] not in db_incidents]
    synthetic_violations = [r for r in db_reports if not r["is_synthetic"]]
    synthetic_inc_violations = [inc for inc in db_incidents.values() if not inc["is_synthetic"]]
    total_synth_violations = len(synthetic_violations) + len(synthetic_inc_violations)

    # 9. Cross-layer consistency
    rest_incident_ids = set()
    for tr in transport_results:
        if tr.response_body and isinstance(tr.response_body.get("data"), dict):
            inc_id = tr.response_body["data"].get("incident_id")
            if inc_id:
                rest_incident_ids.add(inc_id)

    db_incident_ids = set(db_incidents.keys())
    ws_unknown_incident_ids = []
    for fr in captured_frames:
        if fr.payload and isinstance(fr.payload, dict):
            inc_id = fr.payload.get("incident_id")
            if inc_id and inc_id not in db_incident_ids:
                ws_unknown_incident_ids.append(inc_id)

    # 10. Quantitative metrics
    # Pairwise Clustering
    true_groups: List[str] = []
    pred_groups: List[str] = []
    link_map = {l["report_id"]: l["incident_id"] for l in db_links}

    dup_tp, dup_fp, dup_fn, dup_tn = 0, 0, 0, 0
    corrob_tp, corrob_fp, corrob_fn, corrob_tn = 0, 0, 0, 0

    for ev in mapped_events:
        gt = ev.ground_truth
        run_rep_id = ev.dispatch.report_id

        # Ground truth group handling: noise / unclustered => unique singleton
        if gt.incident_group is None:
            t_grp = f"singleton-{ev.event_id}"
        else:
            t_grp = gt.incident_group
        true_groups.append(t_grp)

        p_grp = link_map.get(run_rep_id, f"unfused-{run_rep_id}")
        pred_groups.append(p_grp)

        # Relationship evaluation
        link_rel = next((l["relationship_type"] for l in db_links if l["report_id"] == run_rep_id), "NONE")
        is_true_dup = (gt.relation_type and gt.relation_type.value == "DUPLICATE")
        is_pred_dup = (link_rel == "DUPLICATE")

        if is_true_dup and is_pred_dup:
            dup_tp += 1
        elif not is_true_dup and is_pred_dup:
            dup_fp += 1
        elif is_true_dup and not is_pred_dup:
            dup_fn += 1
        else:
            dup_tn += 1

        is_true_corrob = (gt.relation_type and gt.relation_type.value == "CORROBORATING")
        is_pred_corrob = (link_rel == "CORROBORATING")

        if is_true_corrob and is_pred_corrob:
            corrob_tp += 1
        elif not is_true_corrob and is_pred_corrob:
            corrob_fp += 1
        elif is_true_corrob and not is_pred_corrob:
            corrob_fn += 1
        else:
            corrob_tn += 1

    fusion_report = compute_fusion_accuracy(true_groups, pred_groups)

    dup_prec = round(dup_tp / (dup_tp + dup_fp), 4) if (dup_tp + dup_fp) > 0 else (1.0 if dup_tp == 0 and dup_fp == 0 else 0.0)
    dup_rec = round(dup_tp / (dup_tp + dup_fn), 4) if (dup_tp + dup_fn) > 0 else (1.0 if dup_tp == 0 and dup_fn == 0 else 0.0)
    dup_f1 = round(2 * dup_prec * dup_rec / (dup_prec + dup_rec), 4) if (dup_prec + dup_rec) > 0 else 0.0

    corrob_prec = round(corrob_tp / (corrob_tp + corrob_fp), 4) if (corrob_tp + corrob_fp) > 0 else (1.0 if corrob_tp == 0 and corrob_fp == 0 else 0.0)
    corrob_rec = round(corrob_tp / (corrob_tp + corrob_fn), 4) if (corrob_tp + corrob_fn) > 0 else (1.0 if corrob_tp == 0 and corrob_fn == 0 else 0.0)
    corrob_f1 = round(2 * corrob_prec * corrob_rec / (corrob_prec + corrob_rec), 4) if (corrob_prec + corrob_rec) > 0 else 0.0

    # 11. Priority & Critical Recall Evaluation
    group_true_urgency: Dict[str, str] = {}
    group_max_pred_score: Dict[str, float] = {}
    for ev in mapped_events:
        gt = ev.ground_truth
        run_rep_id = ev.dispatch.report_id
        t_grp = gt.incident_group if gt.incident_group else f"singleton-{ev.event_id}"
        if gt.expected_urgency:
            group_true_urgency[t_grp] = gt.expected_urgency.value
        p_grp = link_map.get(run_rep_id)
        sc = db_incidents.get(p_grp, {}).get("priority_score", 0.0) if p_grp else 0.0
        group_max_pred_score[t_grp] = max(group_max_pred_score.get(t_grp, 0.0), sc)

    # Find focal incident: highest report count or associated with flood_rasulgarh
    focal_inc_id = None
    max_rc = 0
    for inc_id, inc_data in db_incidents.items():
        if inc_data["report_count"] > max_rc:
            max_rc = inc_data["report_count"]
            focal_inc_id = inc_id

    focal_score = db_incidents[focal_inc_id]["priority_score"] if focal_inc_id else 0.0

    # Incident critical recall requires score >= 80.0
    # There is 1 ground truth critical emergency in golden scenario
    inc_crit_recall = 1.0 if focal_score >= 80.0 else 0.0
    prio_ge_75_recall = 1.0 if focal_score >= 75.0 else 0.0

    # Rank 1 strict assertion
    all_scores = [inc["priority_score"] for inc_id, inc in db_incidents.items() if inc_id != focal_inc_id]
    next_highest = max(all_scores) if all_scores else 0.0
    is_rank_1 = focal_score > next_highest
    has_tie = any(abs(s - focal_score) < 0.01 for s in all_scores)

    rank_1_status = "PASS" if is_rank_1 and not has_tie else "FAIL"

    # Spearman correlation: exactly 1 multi-report incident in golden scenario => meaningful_ranking_sample = False
    gt_cluster_sizes = Counter(true_groups)
    multi_report_gt_incidents = [
        grp for grp, count in gt_cluster_sizes.items()
        if count >= 2 and not grp.startswith("singleton-")
    ]
    meaningful_ranking = (len(multi_report_gt_incidents) >= 2)

    sorted_groups = sorted(group_true_urgency.keys())
    urgency_weights = {"CRITICAL": 4.0, "HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}
    true_urg_values = [urgency_weights.get(group_true_urgency[g], 1.0) for g in sorted_groups]
    pred_score_values = [group_max_pred_score.get(g, 0.0) for g in sorted_groups]

    diagnostic_rho = compute_spearman_rho(true_urg_values, pred_score_values) if len(sorted_groups) >= 2 else None
    if diagnostic_rho is not None:
        diagnostic_rho = round(diagnostic_rho, 4)
    spearman_rho = diagnostic_rho if meaningful_ranking else None
    diag_spearman = diagnostic_rho

    # 12. Latency profile
    cold_lat = http_latencies_ms[0] if http_latencies_ms else 0.0
    warm_latencies = http_latencies_ms[1:] if len(http_latencies_ms) > 1 else [cold_lat]
    warm_profile = compute_latency_profile(warm_latencies)

    # 13. ML Metrics from persisted predictions
    true_types = []
    pred_types = []
    true_urgencies = []
    pred_urgencies = []
    true_people = []
    pred_people = []
    true_loc_prec = []
    pred_loc_prec = []

    for ev in mapped_events:
        gt = ev.ground_truth
        run_rep_id = ev.dispatch.report_id
        pred_rec = db_predictions.get(run_rep_id, {})

        if gt.expected_incident_type:
            true_types.append(gt.expected_incident_type.value)
            p_type = pred_rec.get("incident_type", {}).get("label") or "UNKNOWN"
            pred_types.append(p_type)

        if gt.expected_urgency:
            true_urgencies.append(gt.expected_urgency.value)
            p_urg = pred_rec.get("urgency", {}).get("label") or "LOW"
            pred_urgencies.append(p_urg)

        true_people.append(gt.expected_people_count)
        p_risk = pred_rec.get("people_at_risk", {}).get("count")
        pred_people.append(p_risk)

        true_loc_prec.append(ev.dispatch.location_hint.precision.value if ev.dispatch.location_hint else "unknown")
        pred_loc_prec.append(pred_rec.get("location", {}).get("precision") or "unknown")

    type_clf = compute_classification_report(true_types, pred_types) if true_types else None
    type_macro_f1 = type_clf.macro_f1 if type_clf else 0.0

    urg_metrics = compute_urgency_alignment(true_urgencies, pred_urgencies) if true_urgencies else None
    urg_acc = round(sum(1 for t, p in zip(true_urgencies, pred_urgencies) if t == p) / len(true_urgencies), 4) if true_urgencies else 0.0

    risk_metrics = compute_people_at_risk_metrics(
        gt_at_risk=[bool(c and c > 0) for c in true_people],
        pred_at_risk=[bool(c and c > 0) for c in pred_people],
        gt_counts=true_people,
        pred_counts=pred_people,
    ) if true_people else None
    casualty_mae = risk_metrics.count_mae if (risk_metrics and risk_metrics.count_mae is not None) else 0.0

    loc_correct = sum(1 for t, p in zip(true_loc_prec, pred_loc_prec) if t == p)
    loc_prec_acc = round(loc_correct / len(true_loc_prec), 4) if true_loc_prec else 0.0

    # Build final report
    report = E2EEvaluationReport(
        run_id=run_id_prefix,
        total_reports_attempted=len(mapped_events),
        total_reports_successful=sum(1 for r in transport_results if r.success),
        http_errors_4xx=sum(1 for r in transport_results if r.status_code and 400 <= r.status_code < 500),
        http_errors_5xx=sum(1 for r in transport_results if r.status_code and r.status_code >= 500),
        http_timeouts=0,
        transport_retries=sum(r.retries for r in transport_results),
        transport_buffered=sum(1 for r in transport_results if r.buffered),
        circuit_breaker_tripped=transport.circuit_breaker.state.value != "CLOSED",
        http_cold_latency_ms=round(cold_lat, 2),
        http_warm_latency_profile=warm_profile,
        db_raw_reports_count=db_counts["raw_reports"],
        db_ml_predictions_count=db_counts["ml_predictions"],
        db_incident_links_count=db_counts["incident_reports"],
        db_incidents_count=db_counts["incidents"],
        db_priority_calculations_count=db_counts["priority_calculations"],
        orphan_links_count=len(orphan_links),
        synthetic_partition_violations=total_synth_violations,
        websocket_connected=ws_connected,
        websocket_total_frames=len(captured_frames),
        websocket_malformed_frames=sum(1 for f in captured_frames if not f.is_valid_envelope),
        websocket_event_counts=ws_capture.event_counts(),
        websocket_unknown_incident_ids=ws_unknown_incident_ids,
        pairwise_fusion_accuracy=fusion_report,
        duplicate_metrics={
            "tp": dup_tp,
            "fp": dup_fp,
            "fn": dup_fn,
            "tn": dup_tn,
            "precision": dup_prec,
            "recall": dup_rec,
            "f1": dup_f1,
        },
        corroborating_metrics={
            "tp": corrob_tp,
            "fp": corrob_fp,
            "fn": corrob_fn,
            "tn": corrob_tn,
            "precision": corrob_prec,
            "recall": corrob_rec,
            "f1": corrob_f1,
        },
        incident_critical_recall=inc_crit_recall,
        priority_score_ge_75_recall=prio_ge_75_recall,
        scenario_rank_1_status=rank_1_status,
        scenario_rank_1_passed=is_rank_1,
        rank_1_tie_detected=has_tie,
        meaningful_ranking_sample=meaningful_ranking,
        spearman_rank_correlation=spearman_rho,
        diagnostic_spearman_rho=diag_spearman,
        ml_type_macro_f1=type_macro_f1,
        ml_urgency_accuracy=urg_acc,
        ml_casualty_mae=casualty_mae,
        ml_location_precision_accuracy=loc_prec_acc,
    )

    return report, transport_results, captured_frames
