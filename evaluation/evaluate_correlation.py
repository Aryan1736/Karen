"""
Karen's Ear — Incident Correlation & Priority Engine Evaluator.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md, docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened Correlation Benchmark Evaluator

This module benchmarks incident correlation and prioritization:
1. Pairwise Incident Fusion Accuracy (Pairwise Precision, Recall, F1, Rand Index).
2. Duplicate Detection Performance (Precision, Recall, F1).
3. Incident-Level Critical Recall (Safety invariant: fused critical emergencies escalated).
4. Corroboration Escalation & Duplicate Suppression Dynamics with Tri-State Assertions.
5. Scenario Assertion with Strict Tie Definitions: Does the life-safety emergency reach Rank #1?
6. Priority Rank Correlation: Spearman's rank correlation using tie-safe average ranks.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
import uuid

from evaluation.metrics import (
    FusionAccuracyReport,
    LatencyProfile,
    compute_fusion_accuracy,
    compute_latency_profile,
    compute_spearman_rho,
)
from simulator.models import ScenarioEvent

logger = logging.getLogger("evaluation.correlation")


# =============================================================================
# 1. Assertion Enums & Data Structures
# =============================================================================

class AssertionResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class CorrelationEvaluationMode(str, Enum):
    HARNESS_SELF_TEST = "HARNESS_SELF_TEST"
    MOCK_FIXTURE = "MOCK_FIXTURE"
    REAL_CORRELATION = "REAL_CORRELATION"


@dataclass
class CorrelationEvaluationReport:
    """Quantitative scorecard of incident correlation and deduplication."""
    total_reports_processed: int
    fusion_accuracy: FusionAccuracyReport
    duplicate_precision: float
    duplicate_recall: float
    duplicate_f1: float
    incident_critical_recall: Optional[float]
    corroboration_boost_status: AssertionResult
    duplicate_suppression_status: AssertionResult
    scenario_rank_1_status: AssertionResult
    rank_1_tie_detected: bool
    spearman_rank_correlation: Optional[float] = None
    meaningful_ranking_sample: bool = False
    diagnostic_spearman_rho: Optional[float] = None
    priority_score_ge_75_recall: Optional[float] = None
    corrob_precision: Optional[float] = None
    corrob_recall: Optional[float] = None
    corrob_f1: Optional[float] = None
    corrob_tp: int = 0
    corrob_fp: int = 0
    corrob_fn: int = 0
    corrob_tn: int = 0
    embedding_contract: Optional[Dict[str, Any]] = None
    execution_scope: str = "IN_PROCESS_ENGINE_REPLAY"
    is_real_system_result: bool = False
    evaluation_mode: CorrelationEvaluationMode = CorrelationEvaluationMode.HARNESS_SELF_TEST
    latencies_ms: Optional[List[float]] = None
    latency_profile: Optional[LatencyProfile] = None
    cold_latency_ms: Optional[float] = None
    warm_latency_profile: Optional[LatencyProfile] = None
    details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def corroboration_boost_verified(self) -> bool:
        return self.corroboration_boost_status == AssertionResult.PASS

    @property
    def duplicate_suppression_verified(self) -> bool:
        return self.duplicate_suppression_status == AssertionResult.PASS

    @property
    def scenario_rank_1_assertion_passed(self) -> bool:
        return self.scenario_rank_1_status == AssertionResult.PASS

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "total_reports": self.total_reports_processed,
            "pairwise_fusion_f1": round(self.fusion_accuracy.pairwise_f1, 4) if self.fusion_accuracy.pairwise_f1 is not None else None,
            "pairwise_precision": round(self.fusion_accuracy.pairwise_precision, 4) if self.fusion_accuracy.pairwise_precision is not None else None,
            "pairwise_recall": round(self.fusion_accuracy.pairwise_recall, 4) if self.fusion_accuracy.pairwise_recall is not None else None,
            "rand_index": round(self.fusion_accuracy.rand_index, 4),
            "duplicate_precision": round(self.duplicate_precision, 4),
            "duplicate_recall": round(self.duplicate_recall, 4),
            "duplicate_f1": round(self.duplicate_f1, 4),
            "incident_critical_recall": round(self.incident_critical_recall, 4) if self.incident_critical_recall is not None else None,
            "priority_score_ge_75_recall": round(self.priority_score_ge_75_recall, 4) if self.priority_score_ge_75_recall is not None else None,
            "corroboration_boost_status": self.corroboration_boost_status.value,
            "duplicate_suppression_status": self.duplicate_suppression_status.value,
            "scenario_rank_1_status": self.scenario_rank_1_status.value,
            "scenario_rank_1_assertion_passed": self.scenario_rank_1_assertion_passed,
            "rank_1_tie_detected": self.rank_1_tie_detected,
            "meaningful_ranking_sample": self.meaningful_ranking_sample,
            "spearman_rank_correlation": round(self.spearman_rank_correlation, 4) if self.spearman_rank_correlation is not None else None,
            "diagnostic_spearman_rho": round(self.diagnostic_spearman_rho, 4) if self.diagnostic_spearman_rho is not None else None,
            "execution_scope": self.execution_scope,
            "evaluation_mode": self.evaluation_mode.value if isinstance(self.evaluation_mode, Enum) else str(self.evaluation_mode),
            "is_real_system_result": self.is_real_system_result,
        }
        if self.corrob_f1 is not None or self.corrob_tp > 0 or self.corrob_fn > 0:
            d["corroborating_metrics"] = {
                "tp": self.corrob_tp,
                "fp": self.corrob_fp,
                "fn": self.corrob_fn,
                "tn": self.corrob_tn,
                "precision": round(self.corrob_precision, 4) if self.corrob_precision is not None else None,
                "recall": round(self.corrob_recall, 4) if self.corrob_recall is not None else None,
                "f1": round(self.corrob_f1, 4) if self.corrob_f1 is not None else None,
            }
        if self.embedding_contract is not None:
            d["embedding_contract"] = self.embedding_contract
        if self.latency_profile is not None:
            d["latency_profile"] = self.latency_profile.to_dict()
        if self.cold_latency_ms is not None:
            d["cold_latency_ms"] = round(self.cold_latency_ms, 2)
        if self.warm_latency_profile is not None:
            d["warm_latency_profile"] = self.warm_latency_profile.to_dict()
        return d


# =============================================================================
# 2. Correlation Evaluation Runner
# =============================================================================

SEVERITY_ORDER: Dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def _safe_correlation_score(val: Any) -> float:
    """Safely parses priority score, sanitizing None, NaN, Inf, and non-numerics to 0.0."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return max(0.0, f)
    except (ValueError, TypeError):
        return 0.0


def evaluate_correlation_engine(
    events: Sequence[ScenarioEvent],
    correlation_stream_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    mock_correlation_outputs: Optional[Union[Sequence[Dict[str, Any]], Dict[str, Any]]] = None,
    strict_rank_1_no_ties: bool = True,
    is_real_system_result: Optional[bool] = None,
    critical_threshold: float = 80.0,
) -> CorrelationEvaluationReport:
    """
    Evaluates incident grouping, duplicate suppression, and priority escalation.

    Args:
        events: Sequence of ScenarioEvents with ground truth.
        correlation_stream_fn: Optional stateful function receiving public dispatch payload
                               and returning:
                               {"incident_id": str, "relationship": str, "priority_score": float, "rank": int}
        mock_correlation_outputs: Optional pre-recorded stream of outputs matching events.
        strict_rank_1_no_ties: If True, Rank #1 requires strictly higher score than all other incidents.
        is_real_system_result: Explicit override for benchmark certification.
        critical_threshold: Minimum priority score required for critical escalation (default: 80.0 matching PriorityLevel.CRITICAL).

    Returns:
        CorrelationEvaluationReport with comprehensive metrics.
    """
    if not events:
        raise ValueError("Cannot evaluate empty events list.")

    is_self_test = (correlation_stream_fn is None and mock_correlation_outputs is None)
    if is_real_system_result is not None:
        real_result = is_real_system_result
    else:
        real_result = (correlation_stream_fn is not None and not is_self_test)

    if real_result:
        eval_mode = CorrelationEvaluationMode.REAL_CORRELATION
        scope = "IN_PROCESS_ENGINE_REPLAY"
    elif mock_correlation_outputs is not None:
        eval_mode = CorrelationEvaluationMode.MOCK_FIXTURE
        scope = "MOCK_FIXTURE_REPLAY"
    else:
        eval_mode = CorrelationEvaluationMode.HARNESS_SELF_TEST
        scope = "HARNESS_SELF_TEST"

    # Build ID-based lookup if mock_correlation_outputs is provided
    mock_by_id: Optional[Dict[str, Any]] = None
    mock_list: Optional[Sequence[Any]] = None
    if mock_correlation_outputs is not None:
        if isinstance(mock_correlation_outputs, dict):
            mock_by_id = mock_correlation_outputs
        elif isinstance(mock_correlation_outputs, (list, tuple)):
            mock_list = mock_correlation_outputs
            mock_by_id = {}
            for item in mock_correlation_outputs:
                if isinstance(item, dict):
                    if "event_id" in item:
                        mock_by_id[str(item["event_id"])] = item
                    elif "report_id" in item:
                        mock_by_id[str(item["report_id"])] = item

    true_groups: List[str] = []
    pred_groups: List[str] = []

    # Duplicate tracking (Ground truth DUPLICATE vs predicted relationship)
    dup_tp = 0
    dup_fp = 0
    dup_fn = 0
    dup_tn = 0

    # Corroborating tracking (Ground truth CORROBORATING vs predicted relationship)
    corrob_tp = 0
    corrob_fp = 0
    corrob_fn = 0
    corrob_tn = 0

    # Incident-level tracking with monotonic max severity
    group_true_urgency: Dict[str, str] = {}
    true_to_pred_cluster_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    pred_group_max_score: Dict[str, float] = defaultdict(float)

    # Corroboration and suppression tracking for focal critical incident
    van_scores_by_stage: Dict[str, List[float]] = defaultdict(list)

    details: List[Dict[str, Any]] = []

    for idx, event in enumerate(events):
        gt = event.ground_truth
        payload = event.public_payload()
        raw_group = gt.incident_group
        if raw_group is not None and str(raw_group).strip().lower() not in ("none", "null", ""):
            true_group = str(raw_group).strip()
        else:
            true_group = f"standalone-{event.event_id}"
        true_groups.append(true_group)

        # Monotonic severity tracking: preserve maximum observed urgency for incident
        if gt.expected_urgency:
            curr_urg = group_true_urgency.get(true_group)
            new_urg = gt.expected_urgency.value
            if curr_urg is None or SEVERITY_ORDER.get(new_urg, 0) > SEVERITY_ORDER.get(curr_urg, 0):
                group_true_urgency[true_group] = new_urg

        # Obtain prediction (strictly no fallback to ground truth if external outputs provided)
        out: Any = None
        if mock_correlation_outputs is not None:
            if mock_by_id:
                if event.event_id in mock_by_id:
                    out = mock_by_id[event.event_id]
                elif event.dispatch.report_id in mock_by_id:
                    out = mock_by_id[event.dispatch.report_id]
            elif mock_list is not None and not mock_by_id and idx < len(mock_list):
                out = mock_list[idx]
        elif correlation_stream_fn is not None:
            try:
                out = correlation_stream_fn(payload)
            except Exception as exc:
                out = {"error": str(exc)}
        else:
            # Hermetic baseline correlation
            is_dup = (gt.relation_type and gt.relation_type.value == "DUPLICATE")
            rel = "DUPLICATE" if is_dup else (gt.relation_type.value if gt.relation_type else "INITIAL")
            score = 90.0 if gt.expected_urgency and gt.expected_urgency.value == "CRITICAL" else 40.0
            out = {
                "incident_id": f"inc-{true_group}",
                "relationship": rel,
                "priority_score": score,
                "rank": 1 if gt.expected_urgency and gt.expected_urgency.value == "CRITICAL" else 2,
            }

        # Safe adaptation: handle non-dict, missing, or malformed outputs
        if not isinstance(out, dict):
            pred_group = f"unclustered-{event.event_id}"
            pred_rel = "NONE"
            pred_score = 0.0
        else:
            pred_group = str(out.get("incident_id") or f"unclustered-{event.event_id}")
            pred_rel = str(out.get("relationship", "INITIAL")).upper()
            pred_score = _safe_correlation_score(out.get("priority_score"))

        pred_groups.append(pred_group)

        # Track cluster associations and scores
        true_to_pred_cluster_counts[true_group][pred_group] += 1
        pred_group_max_score[pred_group] = max(pred_group_max_score[pred_group], pred_score)

        # Duplicate evaluation
        is_true_dup = (gt.relation_type and gt.relation_type.value == "DUPLICATE")
        is_pred_dup = (pred_rel == "DUPLICATE")

        if is_true_dup and is_pred_dup:
            dup_tp += 1
        elif not is_true_dup and is_pred_dup:
            dup_fp += 1
        elif is_true_dup and not is_pred_dup:
            dup_fn += 1
        else:
            dup_tn += 1

        # Corroborating evaluation
        is_true_corrob = (gt.relation_type and gt.relation_type.value == "CORROBORATING")
        is_pred_corrob = (pred_rel == "CORROBORATING")

        if is_true_corrob and is_pred_corrob:
            corrob_tp += 1
        elif not is_true_corrob and is_pred_corrob:
            corrob_fp += 1
        elif is_true_corrob and not is_pred_corrob:
            corrob_fn += 1
        else:
            corrob_tn += 1

        # Track focal emergency priority progression (e.g. trapped van or highest priority incident)
        is_focal = ("flood" in true_group.lower()) or (gt.expected_urgency and gt.expected_urgency.value == "CRITICAL")
        if is_focal:
            stage = gt.relation_type.value if gt.relation_type else "UNKNOWN"
            van_scores_by_stage[stage].append(pred_score)

        details.append({
            "event_id": event.event_id,
            "true_group": true_group,
            "pred_group": pred_group,
            "true_rel": gt.relation_type.value if gt.relation_type else "NONE",
            "pred_rel": pred_rel,
            "pred_score": pred_score,
        })

    # Map each true group to the maximum priority score achieved by any of its associated predicted clusters
    group_max_pred_score: Dict[str, float] = {}
    for grp, counts in true_to_pred_cluster_counts.items():
        if counts:
            group_max_pred_score[grp] = max(pred_group_max_score.get(p_grp, 0.0) for p_grp in counts.keys())
        else:
            group_max_pred_score[grp] = 0.0

    # 1. Clustering Fusion Metrics
    fusion_rep = compute_fusion_accuracy(true_groups, pred_groups)

    # 2. Duplicate Metrics
    dup_prec = dup_tp / (dup_tp + dup_fp) if (dup_tp + dup_fp) > 0 else (1.0 if dup_tp == 0 and dup_fp == 0 else 0.0)
    dup_rec = dup_tp / (dup_tp + dup_fn) if (dup_tp + dup_fn) > 0 else (1.0 if dup_tp == 0 and dup_fn == 0 else 0.0)
    dup_f1 = (2.0 * dup_prec * dup_rec) / (dup_prec + dup_rec) if (dup_prec + dup_rec) > 0 else 0.0

    # 2b. Corroborating Metrics
    corrob_prec = corrob_tp / (corrob_tp + corrob_fp) if (corrob_tp + corrob_fp) > 0 else (1.0 if corrob_tp == 0 and corrob_fp == 0 else 0.0)
    corrob_rec = corrob_tp / (corrob_tp + corrob_fn) if (corrob_tp + corrob_fn) > 0 else (1.0 if corrob_tp == 0 and corrob_fn == 0 else 0.0)
    corrob_f1 = (2.0 * corrob_prec * corrob_rec) / (corrob_prec + corrob_rec) if (corrob_prec + corrob_rec) > 0 else 0.0

    # 3. Incident-Level Critical Recall (Strict PriorityLevel.CRITICAL >= 80.0 threshold)
    crit_incidents = [grp for grp, urg in group_true_urgency.items() if urg == "CRITICAL"]
    escalated_crit = [grp for grp in crit_incidents if group_max_pred_score.get(grp, 0.0) >= critical_threshold]
    inc_crit_recall = (
        (len(escalated_crit) / len(crit_incidents)) if crit_incidents else None
    )

    # Separate diagnostic score >= 75 recall (not to be conflated with backend CRITICAL level)
    escalated_75 = [grp for grp in crit_incidents if group_max_pred_score.get(grp, 0.0) >= 75.0]
    prio_75_recall = (
        (len(escalated_75) / len(crit_incidents)) if crit_incidents else None
    )

    # 4. Corroboration Dynamics Assertion (Tri-State, strictly positive escalation)
    corrob_scores = van_scores_by_stage.get("CORROBORATING", [])
    initial_scores = van_scores_by_stage.get("INITIAL", [])
    if corrob_scores and initial_scores:
        corrob_status = AssertionResult.PASS if max(corrob_scores) > max(initial_scores) else AssertionResult.FAIL
    else:
        corrob_status = AssertionResult.NOT_EVALUATED

    # 5. Duplicate Suppression Dynamics Assertion (Tri-State: duplicates must not exceed corroboration)
    dup_scores = van_scores_by_stage.get("DUPLICATE", [])
    if dup_scores and corrob_scores:
        dup_status = AssertionResult.PASS if max(dup_scores) <= max(corrob_scores) else AssertionResult.FAIL
    else:
        dup_status = AssertionResult.NOT_EVALUATED

    # 6. Scenario Assertion: Did focal critical incident reach Rank 1? (Tri-State + Strict Tie Semantics)
    # Prefer incident with CRITICAL true urgency; fallback to flood or highest severity
    van_group_id = None
    for grp, urg in group_true_urgency.items():
        if urg == "CRITICAL":
            van_group_id = grp
            break
    if van_group_id is None:
        for grp in group_true_urgency:
            if "flood" in grp.lower():
                van_group_id = grp
                break

    rank_1_status = AssertionResult.NOT_EVALUATED
    rank_1_tie_detected = False

    if van_group_id is not None:
        max_van_score = group_max_pred_score.get(van_group_id, 0.0)
        other_scores = [score for grp, score in group_max_pred_score.items() if grp != van_group_id]
        other_max_score = max(other_scores) if other_scores else 0.0

        if max_van_score <= 0.0:
            rank_1_status = AssertionResult.FAIL
        elif not other_scores:
            rank_1_status = AssertionResult.PASS
        elif max_van_score > other_max_score:
            rank_1_status = AssertionResult.PASS
        elif max_van_score == other_max_score:
            rank_1_tie_detected = True
            rank_1_status = AssertionResult.FAIL if strict_rank_1_no_ties else AssertionResult.PASS
        else:
            rank_1_status = AssertionResult.FAIL

    # 7. Priority Rank Correlation (Spearman's Rho with standard average rank assignment)
    # A meaningful triage ranking benchmark requires at least 2 distinct multi-report ground truth incidents.
    gt_cluster_sizes = Counter(true_groups)
    multi_report_gt_incidents = [
        grp for grp, count in gt_cluster_sizes.items()
        if count >= 2 and not grp.startswith("standalone-")
    ]
    meaningful_ranking = (len(multi_report_gt_incidents) >= 2)

    sorted_groups = sorted(group_true_urgency.keys())
    urgency_weights = {"CRITICAL": 4.0, "HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}
    true_urg_values = [urgency_weights.get(group_true_urgency[g], 1.0) for g in sorted_groups]
    pred_score_values = [group_max_pred_score.get(g, 0.0) for g in sorted_groups]

    diagnostic_rho = compute_spearman_rho(true_urg_values, pred_score_values) if len(sorted_groups) >= 2 else None
    spearman_rho = diagnostic_rho if meaningful_ranking else None

    return CorrelationEvaluationReport(
        total_reports_processed=len(events),
        fusion_accuracy=fusion_rep,
        duplicate_precision=dup_prec,
        duplicate_recall=dup_rec,
        duplicate_f1=dup_f1,
        incident_critical_recall=inc_crit_recall,
        corroboration_boost_status=corrob_status,
        duplicate_suppression_status=dup_status,
        scenario_rank_1_status=rank_1_status,
        rank_1_tie_detected=rank_1_tie_detected,
        spearman_rank_correlation=spearman_rho,
        meaningful_ranking_sample=meaningful_ranking,
        diagnostic_spearman_rho=diagnostic_rho,
        priority_score_ge_75_recall=prio_75_recall,
        corrob_precision=corrob_prec,
        corrob_recall=corrob_rec,
        corrob_f1=corrob_f1,
        corrob_tp=corrob_tp,
        corrob_fp=corrob_fp,
        corrob_fn=corrob_fn,
        corrob_tn=corrob_tn,
        execution_scope=scope,
        is_real_system_result=real_result,
        evaluation_mode=eval_mode,
        details=details,
    )


# =============================================================================
# 3. Real Correlation & Priority Integration Engine
# =============================================================================

@dataclass
class CandidateIncident:
    """Ephemeral in-process incident candidate tracked during correlation stream evaluation."""
    incident_id: str
    embedding: Optional[Sequence[float]]
    created_at: Any
    updated_at: Any
    latitude: Optional[float]
    longitude: Optional[float]
    location_text: Optional[str]
    location_precision: str
    incident_type: Optional[str]
    urgency: Optional[str]
    people_at_risk_count: Optional[int]
    status: str
    report_count: int
    independent_source_count: int
    corroboration_score: float
    candidate_texts: List[str] = field(default_factory=list)
    candidate_source_ids: List[str] = field(default_factory=list)
    ml_confidences: List[Optional[float]] = field(default_factory=list)


def verify_embedding_contract(embeddings: Sequence[Any]) -> Dict[str, Any]:
    """
    Verifies embedding contract for ML outputs:
    - Available / missing count
    - Dimension == 384
    - All values finite (no NaN, no Inf)
    - L2 norm approximately 1.0 (unit vector)
    """
    total = len(embeddings)
    available = 0
    missing = 0
    wrong_dimension = 0
    non_finite = 0
    norms: List[float] = []

    for emb in embeddings:
        if emb is None:
            missing += 1
            continue
        if not isinstance(emb, (list, tuple)) and not hasattr(emb, "__len__"):
            wrong_dimension += 1
            continue
        if len(emb) != 384:
            wrong_dimension += 1
            continue

        is_finite = True
        sum_sq = 0.0
        for val in emb:
            try:
                f = float(val)
                if math.isnan(f) or math.isinf(f):
                    is_finite = False
                    break
                sum_sq += f * f
            except (ValueError, TypeError):
                is_finite = False
                break

        if not is_finite:
            non_finite += 1
            continue

        available += 1
        norms.append(math.sqrt(sum_sq))

    return {
        "total": total,
        "available": available,
        "missing": missing,
        "wrong_dimension": wrong_dimension,
        "non_finite": non_finite,
        "norm_min": round(min(norms), 4) if norms else None,
        "norm_mean": round(sum(norms) / len(norms), 4) if norms else None,
        "norm_max": round(max(norms), 4) if norms else None,
        "all_valid": (available == total and missing == 0 and wrong_dimension == 0 and non_finite == 0),
    }


def build_real_correlation_stream_fn(
    ml_predictor: Optional[Callable[[str, Optional[str], Optional[Dict[str, Any]]], Any]] = None,
    duplicate_threshold: Optional[float] = None,
    corroboration_threshold: Optional[float] = None,
    tau_decay_hours: Optional[float] = None,
    cutoff_hours: Optional[float] = None,
    spatial_cluster_radius_km: Optional[float] = None,
    latency_collector: Optional[List[float]] = None,
    embedding_collector: Optional[List[Any]] = None,
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Constructs a stateful streaming callable for in-process incident correlation and prioritization.
    Strictly follows Daksh's deterministic correlation and priority formulas:
      - Uses real ML pipeline with include_embedding=True (384-dimensional dense vectors).
      - Compares each incoming public dispatch payload against active incident candidates.
      - Fuses reports into existing incidents when composite similarity >= corroboration threshold.
      - Escalates priority based on independent corroborating eyewitness accounts.
      - Suppresses duplicate spam/retweets without inflating priority score.
      - Evaluates priority using calculate_priority().
      - Zero ground-truth leakage: only legitimate public dispatch fields are processed.
    """
    from backend.app.engine.correlation import (
        DEFAULT_CORROBORATION_THRESHOLD,
        DEFAULT_DUPLICATE_THRESHOLD,
        DEFAULT_SPATIAL_CLUSTER_RADIUS_KM,
        DEFAULT_TEMPORAL_CUTOFF_HOURS,
        DEFAULT_TEMPORAL_DECAY_HOURS,
        calculate_corroboration_score,
        correlate_report_to_incident,
    )
    from backend.app.engine.priority import calculate_priority
    from backend.app.schemas.common import RelationshipType

    dup_thresh = duplicate_threshold if duplicate_threshold is not None else DEFAULT_DUPLICATE_THRESHOLD
    corrob_thresh = corroboration_threshold if corroboration_threshold is not None else DEFAULT_CORROBORATION_THRESHOLD
    tau_decay = tau_decay_hours if tau_decay_hours is not None else DEFAULT_TEMPORAL_DECAY_HOURS
    cutoff = cutoff_hours if cutoff_hours is not None else DEFAULT_TEMPORAL_CUTOFF_HOURS
    radius_km = spatial_cluster_radius_km if spatial_cluster_radius_km is not None else DEFAULT_SPATIAL_CLUSTER_RADIUS_KM

    if ml_predictor is not None:
        analyzer = ml_predictor
    else:
        try:
            from backend.app.services.ml_adapter import get_ml_adapter
            adapter = get_ml_adapter()
            def _adapted_analyzer(text: str, report_id: Optional[str] = None, location_hint: Optional[Dict[str, Any]] = None):
                return adapter.analyze_report(text=text, report_id=report_id or "unknown", location_hint=location_hint)
            analyzer = _adapted_analyzer
        except Exception:
            from evaluation.evaluate_ml import build_real_ml_predictor
            raw_predictor = build_real_ml_predictor(include_embedding=True)
            def _raw_analyzer(text: str, report_id: Optional[str] = None, location_hint: Optional[Dict[str, Any]] = None):
                return raw_predictor(text, report_id, location_hint)
            analyzer = _raw_analyzer

    candidates: List[CandidateIncident] = []

    def correlation_stream_fn(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError(f"Payload must be a dictionary, got {type(payload).__name__}")

        t0 = time.perf_counter()

        text = str(payload.get("text") or "")
        report_id = str(payload.get("report_id") or "")
        location_hint = payload.get("location_hint")
        metadata = payload.get("metadata") or {}
        reported_at = payload.get("reported_at")
        source_id = (
            metadata.get("caller_id")
            or metadata.get("source_id")
            or payload.get("source")
        )

        pred = analyzer(text, report_id, location_hint)

        # Extract embedding
        if hasattr(pred, "embedding"):
            pred_embedding = pred.embedding
        elif isinstance(pred, dict):
            pred_embedding = pred.get("embedding")
        else:
            pred_embedding = None

        if embedding_collector is not None:
            embedding_collector.append(pred_embedding)

        # Extract location & coordinates
        if hasattr(pred, "location") and pred.location is not None:
            loc = pred.location
            pred_lat = getattr(loc, "latitude", None)
            pred_lon = getattr(loc, "longitude", None)
            pred_loc_text = getattr(loc, "text", None)
            pred_prec = getattr(loc, "precision", "unknown")
        elif isinstance(pred, dict) and pred.get("location"):
            loc = pred["location"]
            pred_lat = loc.get("latitude")
            pred_lon = loc.get("longitude")
            pred_loc_text = loc.get("text")
            pred_prec = loc.get("precision", "unknown")
        else:
            pred_lat, pred_lon, pred_loc_text, pred_prec = None, None, None, "unknown"

        # Overlay location_hint coordinates if missing from ML
        if (pred_lat is None or pred_lon is None) and location_hint:
            if isinstance(location_hint, dict):
                if pred_lat is None: pred_lat = location_hint.get("latitude")
                if pred_lon is None: pred_lon = location_hint.get("longitude")
                if pred_loc_text is None: pred_loc_text = location_hint.get("raw_text") or location_hint.get("text")
            else:
                if pred_lat is None: pred_lat = getattr(location_hint, "latitude", None)
                if pred_lon is None: pred_lon = getattr(location_hint, "longitude", None)
                if pred_loc_text is None: pred_loc_text = getattr(location_hint, "raw_text", None) or getattr(location_hint, "text", None)

        # Extract incident_type
        if hasattr(pred, "incident_type") and pred.incident_type is not None:
            pred_type = getattr(pred.incident_type, "label", None) or getattr(pred.incident_type, "value", None)
        elif isinstance(pred, dict) and pred.get("incident_type"):
            it = pred["incident_type"]
            pred_type = it.get("label") or it.get("value") if isinstance(it, dict) else str(it)
        else:
            pred_type = None

        # Extract urgency
        if hasattr(pred, "urgency") and pred.urgency is not None:
            pred_urgency = getattr(pred.urgency, "label", None) or getattr(pred.urgency, "value", None)
        elif isinstance(pred, dict) and pred.get("urgency"):
            ug = pred["urgency"]
            pred_urgency = ug.get("label") or ug.get("value") if isinstance(ug, dict) else str(ug)
        else:
            pred_urgency = None

        # Extract people_at_risk
        if hasattr(pred, "people_at_risk") and pred.people_at_risk is not None:
            pred_risk_count = getattr(pred.people_at_risk, "count", None)
        elif isinstance(pred, dict) and pred.get("people_at_risk"):
            pr = pred["people_at_risk"]
            pred_risk_count = pr.get("count") if isinstance(pr, dict) else None
        else:
            pred_risk_count = None

        conf = getattr(pred, "overall_confidence", None) if not isinstance(pred, dict) else pred.get("confidence", {}).get("overall")

        rep_dict = {
            "text": text,
            "embedding": pred_embedding,
            "reported_at": reported_at,
            "latitude": pred_lat,
            "longitude": pred_lon,
            "location_text": pred_loc_text,
            "source_id": source_id,
            "metadata": metadata,
        }

        best_cand: Optional[CandidateIncident] = None
        best_res: Any = None
        highest_score: float = -1.0

        for cand in candidates:
            res = correlate_report_to_incident(
                report=rep_dict,
                incident=cand,
                report_text=text,
                report_embedding=pred_embedding,
                report_timestamp=reported_at,
                report_latitude=pred_lat,
                report_longitude=pred_lon,
                report_location_text=pred_loc_text,
                report_source_id=source_id,
                incident_embedding=cand.embedding,
                incident_latitude=cand.latitude,
                incident_longitude=cand.longitude,
                incident_location_text=cand.location_text,
                incident_timestamp=cand.updated_at,
                current_report_count=cand.report_count,
                current_independent_sources=cand.independent_source_count,
                candidate_texts=cand.candidate_texts,
                candidate_source_ids=cand.candidate_source_ids,
                duplicate_threshold=dup_thresh,
                corroboration_threshold=corrob_thresh,
                tau_decay_hours=tau_decay,
                cutoff_hours=cutoff,
                spatial_cluster_radius_km=radius_km,
            )
            if res.is_match and res.composite_score > highest_score:
                highest_score = res.composite_score
                best_cand = cand
                best_res = res

        if best_cand is not None and best_res is not None:
            rel = best_res.relationship
            best_cand.report_count += 1
            if rel == RelationshipType.CORROBORATING:
                best_cand.independent_source_count += 1
            best_cand.corroboration_score = calculate_corroboration_score(best_cand.independent_source_count)
            best_cand.candidate_texts.append(text)
            if source_id:
                best_cand.candidate_source_ids.append(source_id)
            best_cand.updated_at = reported_at

            # Monotonic urgency escalation (highest observed wins)
            if pred_urgency:
                ranks = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
                cur_r = ranks.get(str(best_cand.urgency).upper(), 0)
                new_r = ranks.get(str(pred_urgency).upper(), 0)
                if new_r > cur_r:
                    best_cand.urgency = pred_urgency

            # People at risk (max known count)
            if pred_risk_count is not None:
                if best_cand.people_at_risk_count is None:
                    best_cand.people_at_risk_count = pred_risk_count
                else:
                    best_cand.people_at_risk_count = max(best_cand.people_at_risk_count, pred_risk_count)

            # Location update
            if best_cand.latitude is None and pred_lat is not None:
                best_cand.latitude = pred_lat
                best_cand.longitude = pred_lon
                best_cand.location_text = pred_loc_text

            prio = calculate_priority(
                incident=best_cand,
                urgency=best_cand.urgency,
                people_at_risk_count=best_cand.people_at_risk_count,
                independent_sources=best_cand.independent_source_count,
                corroboration_score=best_cand.corroboration_score,
                incident_type=best_cand.incident_type,
                status=best_cand.status,
                ml_confidence=conf,
            )
            target_inc_id = best_cand.incident_id
            assigned_rel = rel.value if isinstance(rel, Enum) else str(rel)
        else:
            new_inc_id = f"inc-{len(candidates)+1:03d}-{uuid.uuid4().hex[:6]}"
            new_cand = CandidateIncident(
                incident_id=new_inc_id,
                embedding=pred_embedding,
                created_at=reported_at,
                updated_at=reported_at,
                latitude=pred_lat,
                longitude=pred_lon,
                location_text=pred_loc_text,
                location_precision=str(pred_prec),
                incident_type=pred_type,
                urgency=pred_urgency,
                people_at_risk_count=pred_risk_count,
                status="ACTIVE",
                report_count=1,
                independent_source_count=1,
                corroboration_score=calculate_corroboration_score(1),
                candidate_texts=[text],
                candidate_source_ids=[source_id] if source_id else [],
                ml_confidences=[conf] if conf is not None else [],
            )
            candidates.append(new_cand)
            prio = calculate_priority(
                incident=new_cand,
                urgency=new_cand.urgency,
                people_at_risk_count=new_cand.people_at_risk_count,
                independent_sources=new_cand.independent_source_count,
                corroboration_score=new_cand.corroboration_score,
                incident_type=new_cand.incident_type,
                status=new_cand.status,
                ml_confidence=conf,
            )
            target_inc_id = new_inc_id
            assigned_rel = "INITIAL"

        t_elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if latency_collector is not None:
            latency_collector.append(t_elapsed_ms)

        return {
            "incident_id": target_inc_id,
            "relationship": assigned_rel,
            "priority_score": prio.score,
            "priority_level": prio.level.value if isinstance(prio.level, Enum) else str(prio.level),
            "explanation": prio.explanation,
        }

    return correlation_stream_fn


def evaluate_real_correlation(
    events: Optional[Sequence[ScenarioEvent]] = None,
    ml_predictor: Optional[Callable[[str, Optional[str], Optional[Dict[str, Any]]], Any]] = None,
    duplicate_threshold: Optional[float] = None,
    corroboration_threshold: Optional[float] = None,
    tau_decay_hours: Optional[float] = None,
    cutoff_hours: Optional[float] = None,
    spatial_cluster_radius_km: Optional[float] = None,
    critical_threshold: float = 80.0,
    strict_rank_1_no_ties: bool = True,
) -> CorrelationEvaluationReport:
    """
    Executes the REAL_CORRELATION benchmark against Daksh's live correlation and priority engines.
    Streams public event dispatches through real ML embedding extraction and candidate correlation.
    Captures live execution latencies and produces a CorrelationEvaluationReport marked REAL_CORRELATION.
    """
    if events is None:
        from simulator.scenarios import get_scenario, list_scenarios
        events = []
        for sid in list_scenarios():
            events.extend(get_scenario(sid))

    measured_latencies: List[float] = []
    measured_embeddings: List[Any] = []
    stream_fn = build_real_correlation_stream_fn(
        ml_predictor=ml_predictor,
        duplicate_threshold=duplicate_threshold,
        corroboration_threshold=corroboration_threshold,
        tau_decay_hours=tau_decay_hours,
        cutoff_hours=cutoff_hours,
        spatial_cluster_radius_km=spatial_cluster_radius_km,
        latency_collector=measured_latencies,
        embedding_collector=measured_embeddings,
    )

    report = evaluate_correlation_engine(
        events=events,
        correlation_stream_fn=stream_fn,
        strict_rank_1_no_ties=strict_rank_1_no_ties,
        is_real_system_result=True,
        critical_threshold=critical_threshold,
    )

    report.evaluation_mode = CorrelationEvaluationMode.REAL_CORRELATION
    report.execution_scope = "IN_PROCESS_ENGINE_REPLAY"
    if measured_embeddings:
        report.embedding_contract = verify_embedding_contract(measured_embeddings)
    if measured_latencies:
        report.latencies_ms = measured_latencies
        report.latency_profile = compute_latency_profile(measured_latencies)
        report.cold_latency_ms = measured_latencies[0]
        if len(measured_latencies) > 1:
            report.warm_latency_profile = compute_latency_profile(measured_latencies[1:])

    return report


def main(args: Optional[List[str]] = None) -> int:
    import argparse
    from pathlib import Path
    import sys

    parser = argparse.ArgumentParser(description="Karen's Ear Incident Correlation & Priority Evaluator Runner")
    parser.add_argument("--real-correlation", action="store_true", help="Evaluate live correlation and priority engine")
    parser.add_argument("--output", "-o", help="Optional output JSON path")
    parser.add_argument("--scenarios", nargs="*", default=None, help="Specific scenario names to evaluate")
    parsed = parser.parse_args(args)

    from simulator.scenarios import get_scenario, list_scenarios

    scenario_names = parsed.scenarios or list_scenarios()
    events: List[ScenarioEvent] = []
    for sid in scenario_names:
        events.extend(get_scenario(sid))

    if parsed.real_correlation:
        report = evaluate_real_correlation(events=events)
    else:
        report = evaluate_correlation_engine(events=events)

    rep_dict = report.to_dict()
    print(json.dumps(rep_dict, indent=2))

    if parsed.output:
        out_p = Path(parsed.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(rep_dict, f, indent=2)
        print(f"\n[OK] Correlation evaluation report saved to {out_p}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
