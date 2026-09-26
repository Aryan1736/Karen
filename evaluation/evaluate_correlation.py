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
import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from evaluation.metrics import (
    FusionAccuracyReport,
    compute_fusion_accuracy,
    compute_spearman_rho,
)
from simulator.models import ScenarioEvent


# =============================================================================
# 1. Assertion Enums & Data Structures
# =============================================================================

class AssertionResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


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
    spearman_rank_correlation: float
    is_real_system_result: bool = False
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
        return {
            "total_reports": self.total_reports_processed,
            "pairwise_fusion_f1": round(self.fusion_accuracy.pairwise_f1, 4) if self.fusion_accuracy.pairwise_f1 is not None else None,
            "pairwise_precision": round(self.fusion_accuracy.pairwise_precision, 4) if self.fusion_accuracy.pairwise_precision is not None else None,
            "pairwise_recall": round(self.fusion_accuracy.pairwise_recall, 4) if self.fusion_accuracy.pairwise_recall is not None else None,
            "rand_index": round(self.fusion_accuracy.rand_index, 4),
            "duplicate_precision": round(self.duplicate_precision, 4),
            "duplicate_recall": round(self.duplicate_recall, 4),
            "duplicate_f1": round(self.duplicate_f1, 4),
            "incident_critical_recall": round(self.incident_critical_recall, 4) if self.incident_critical_recall is not None else None,
            "corroboration_boost_status": self.corroboration_boost_status.value,
            "duplicate_suppression_status": self.duplicate_suppression_status.value,
            "scenario_rank_1_status": self.scenario_rank_1_status.value,
            "scenario_rank_1_assertion_passed": self.scenario_rank_1_assertion_passed,
            "rank_1_tie_detected": self.rank_1_tie_detected,
            "spearman_rank_correlation": round(self.spearman_rank_correlation, 4),
            "is_real_system_result": self.is_real_system_result,
        }


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
    critical_threshold: float = 75.0,
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
        critical_threshold: Minimum priority score required for critical escalation (default: 75.0).

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
        true_group = gt.incident_group or f"standalone-{event.event_id}"
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

    # 3. Incident-Level Critical Recall
    crit_incidents = [grp for grp, urg in group_true_urgency.items() if urg == "CRITICAL"]
    escalated_crit = [grp for grp in crit_incidents if group_max_pred_score.get(grp, 0.0) >= critical_threshold]
    inc_crit_recall = (
        (len(escalated_crit) / len(crit_incidents)) if crit_incidents else None
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
    sorted_groups = sorted(group_true_urgency.keys())
    urgency_weights = {"CRITICAL": 4.0, "HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}
    true_urg_values = [urgency_weights.get(group_true_urgency[g], 1.0) for g in sorted_groups]
    pred_score_values = [group_max_pred_score.get(g, 0.0) for g in sorted_groups]

    spearman_rho = compute_spearman_rho(true_urg_values, pred_score_values) if len(sorted_groups) >= 2 else 1.0

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
        is_real_system_result=real_result,
        details=details,
    )
