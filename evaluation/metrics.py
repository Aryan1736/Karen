"""
Karen's Ear — Evaluation Metrics & Quantitative Benchmark Harness.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md, docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened Evaluation Foundation

This module provides pure-Python, zero-dependency statistical evaluation metrics:
1. Confusion Matrix: Multiclass Precision, Recall, F1, and Macro-F1.
2. Dual-Level Critical Recall:
     - report_critical_recall (Single-report life safety)
     - incident_critical_recall (Fused incident life safety)
3. Urgency Alignment Score: Mean Absolute Error (MAE) and High-Urgency Recall.
4. Deduplication & Fusion Accuracy: Pairwise Precision, Recall, F1, and Rand Index.
5. Ranking Correlation: Spearman's Rank Correlation Coefficient (rho) with average-rank tie handling.
6. Latency Profiling: P50, P90, P95, Mean, Min, Max latency statistics (truthful: distinguishes measured vs unmeasured).
7. Multilabel Response Service Metrics: Micro/Macro F1 across responder agencies.
8. Location Extraction & Geocoding: Fuzzy string match, Haversine error, positive-text match, and coordinate hallucination rate.
9. People-at-Risk Casualty Profiling: Life-safety binary accuracy, risk recall, and casualty count MAE.
10. Coverage & Invalid Prediction Auditing: Tracks invalid schema outputs and penalizes coverage.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union


# =============================================================================
# 1. Classification & Confusion Matrix Metrics
# =============================================================================

@dataclass
class ClassMetric:
    label: str
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    precision: float
    recall: float
    f1: float
    support: int


@dataclass
class ClassificationReport:
    per_class: Dict[str, ClassMetric]
    macro_precision: float
    macro_recall: float
    macro_f1: float
    accuracy: float
    total_samples: int
    confusion_matrix: Dict[str, Dict[str, int]]  # [true_label][predicted_label]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "macro_precision": round(self.macro_precision, 4),
            "macro_recall": round(self.macro_recall, 4),
            "macro_f1": round(self.macro_f1, 4),
            "accuracy": round(self.accuracy, 4),
            "total_samples": self.total_samples,
            "per_class": {
                k: {
                    "precision": round(v.precision, 4),
                    "recall": round(v.recall, 4),
                    "f1": round(v.f1, 4),
                    "support": v.support,
                }
                for k, v in self.per_class.items()
            },
        }


def compute_classification_report(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: Optional[Sequence[str]] = None,
) -> ClassificationReport:
    """
    Computes a multiclass confusion matrix and comprehensive classification metrics.
    """
    if len(y_true) != len(y_pred):
        raise ValueError(f"Length mismatch: len(y_true)={len(y_true)}, len(y_pred)={len(y_pred)}")

    all_labels = sorted(list(set(labels) if labels else set(y_true).union(set(y_pred))))
    n = len(y_true)

    # Initialize confusion matrix [actual][predicted]
    cm: Dict[str, Dict[str, int]] = {true_lbl: {pred_lbl: 0 for pred_lbl in all_labels} for true_lbl in all_labels}

    for yt, yp in zip(y_true, y_pred):
        if yt in cm and yp in cm[yt]:
            cm[yt][yp] += 1

    per_class: Dict[str, ClassMetric] = {}
    macro_p_sum = 0.0
    macro_r_sum = 0.0
    macro_f1_sum = 0.0
    correct = 0

    for lbl in all_labels:
        tp = cm[lbl][lbl]
        correct += tp
        fp = sum(cm[other][lbl] for other in all_labels if other != lbl)
        fn = sum(cm[lbl][other] for other in all_labels if other != lbl)
        tn = n - (tp + fp + fn)
        support = tp + fn

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2.0 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[lbl] = ClassMetric(
            label=lbl,
            true_positive=tp,
            false_positive=fp,
            false_negative=fn,
            true_negative=tn,
            precision=prec,
            recall=rec,
            f1=f1,
            support=support,
        )

        macro_p_sum += prec
        macro_r_sum += rec
        macro_f1_sum += f1

    num_classes = len(all_labels) or 1
    accuracy = correct / n if n > 0 else 0.0

    return ClassificationReport(
        per_class=per_class,
        macro_precision=macro_p_sum / num_classes,
        macro_recall=macro_r_sum / num_classes,
        macro_f1=macro_f1_sum / num_classes,
        accuracy=accuracy,
        total_samples=n,
        confusion_matrix=cm,
    )


# =============================================================================
# 2. Dual-Level Critical Recall
# =============================================================================

@dataclass
class DualCriticalRecall:
    """
    Measures life-safety critical identification at both report and incident tiers.
    Zero-denominator cases truthfully return None rather than falsely claiming 100%.
    """
    report_critical_recall: Optional[float]
    total_ground_truth_critical_reports: int
    correctly_identified_critical_reports: int
    incident_critical_recall: Optional[float]
    total_ground_truth_critical_situations: int
    correctly_identified_critical_situations: int
    missed_critical_report_ids: List[str] = field(default_factory=list)
    missed_critical_situation_ids: List[str] = field(default_factory=list)

    @property
    def detected_critical_reports(self) -> int:
        return self.correctly_identified_critical_reports

    @property
    def detected_critical_incidents(self) -> int:
        return self.correctly_identified_critical_situations

    @property
    def total_ground_truth_critical_incidents(self) -> int:
        return self.total_ground_truth_critical_situations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_critical_recall": round(self.report_critical_recall, 4) if self.report_critical_recall is not None else None,
            "total_gt_critical_reports": self.total_ground_truth_critical_reports,
            "correctly_identified_critical_reports": self.correctly_identified_critical_reports,
            "missed_critical_report_ids": self.missed_critical_report_ids,
            "incident_critical_recall": round(self.incident_critical_recall, 4) if self.incident_critical_recall is not None else None,
            "total_gt_critical_situations": self.total_ground_truth_critical_situations,
            "correctly_identified_critical_situations": self.correctly_identified_critical_situations,
            "missed_critical_situation_ids": self.missed_critical_situation_ids,
        }


def compute_dual_critical_recall(
    report_evals: Sequence[Dict[str, Any]],
    incident_evals: Sequence[Dict[str, Any]],
) -> DualCriticalRecall:
    """
    Computes critical recall at both single-report and multi-source incident levels.
    """
    gt_crit_reports = 0
    correct_crit_reports = 0
    missed_reports: List[str] = []

    for r in report_evals:
        t_urg = str(r.get("true_urgency", "")).upper()
        p_urg = str(r.get("pred_urgency", "")).upper()
        rid = str(r.get("report_id", "unknown"))
        if t_urg == "CRITICAL":
            gt_crit_reports += 1
            if p_urg == "CRITICAL":
                correct_crit_reports += 1
            else:
                missed_reports.append(rid)

    report_recall = correct_crit_reports / gt_crit_reports if gt_crit_reports > 0 else None

    gt_crit_incidents = 0
    correct_crit_incidents = 0
    missed_incidents: List[str] = []

    for inc in incident_evals:
        t_urg = str(inc.get("true_urgency", "")).upper()
        p_urg = str(inc.get("pred_urgency", "")).upper()
        iid = str(inc.get("incident_group", inc.get("incident_id", "unknown")))
        if t_urg == "CRITICAL":
            gt_crit_incidents += 1
            if p_urg == "CRITICAL":
                correct_crit_incidents += 1
            else:
                missed_incidents.append(iid)

    inc_recall = correct_crit_incidents / gt_crit_incidents if gt_crit_incidents > 0 else None

    return DualCriticalRecall(
        report_critical_recall=report_recall,
        total_ground_truth_critical_reports=gt_crit_reports,
        correctly_identified_critical_reports=correct_crit_reports,
        incident_critical_recall=inc_recall,
        total_ground_truth_critical_situations=gt_crit_incidents,
        correctly_identified_critical_situations=correct_crit_incidents,
        missed_critical_report_ids=missed_reports,
        missed_critical_situation_ids=missed_incidents,
    )


# =============================================================================
# 3. Urgency Alignment Score
# =============================================================================

URGENCY_TIER_SCORES: Dict[str, float] = {
    "LOW": 1.0,
    "MEDIUM": 2.0,
    "HIGH": 3.0,
    "CRITICAL": 4.0,
}


@dataclass
class UrgencyAlignmentReport:
    mae: Optional[float]
    high_urgency_recall: Optional[float]
    total_evaluated: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "urgency_mae": round(self.mae, 4) if self.mae is not None else None,
            "high_urgency_recall": round(self.high_urgency_recall, 4) if self.high_urgency_recall is not None else None,
            "total_evaluated": self.total_evaluated,
        }


def compute_urgency_alignment(
    true_urgencies: Sequence[str],
    pred_urgencies: Sequence[str],
) -> UrgencyAlignmentReport:
    """
    Computes Urgency Mean Absolute Error (MAE) on a 1.0 to 4.0 scale and High-Urgency Recall.
    """
    if len(true_urgencies) != len(pred_urgencies):
        raise ValueError("Length mismatch in urgency sequences")

    total_error = 0.0
    valid_count = 0
    high_gt_count = 0
    high_correct_count = 0

    for yt, yp in zip(true_urgencies, pred_urgencies):
        yt_str = str(yt).upper()
        yp_str = str(yp).upper()

        if yt_str in URGENCY_TIER_SCORES and yp_str in URGENCY_TIER_SCORES:
            score_true = URGENCY_TIER_SCORES[yt_str]
            score_pred = URGENCY_TIER_SCORES[yp_str]
            total_error += abs(score_true - score_pred)
            valid_count += 1

            if score_true >= 3.0:  # HIGH or CRITICAL
                high_gt_count += 1
                if score_pred >= 3.0:
                    high_correct_count += 1

    mae = total_error / valid_count if valid_count > 0 else None
    high_recall = high_correct_count / high_gt_count if high_gt_count > 0 else (None if valid_count > 0 and high_gt_count == 0 else None)

    return UrgencyAlignmentReport(
        mae=mae,
        high_urgency_recall=high_recall,
        total_evaluated=valid_count,
    )


# =============================================================================
# 4. Deduplication & Incident Fusion Metrics
# =============================================================================

@dataclass
class FusionAccuracyReport:
    pairwise_precision: Optional[float]
    pairwise_recall: Optional[float]
    pairwise_f1: Optional[float]
    rand_index: float
    true_positive_pairs: int
    false_positive_pairs: int
    false_negative_pairs: int
    true_negative_pairs: int
    total_pairs: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pairwise_precision": round(self.pairwise_precision, 4) if self.pairwise_precision is not None else None,
            "pairwise_recall": round(self.pairwise_recall, 4) if self.pairwise_recall is not None else None,
            "pairwise_f1": round(self.pairwise_f1, 4) if self.pairwise_f1 is not None else None,
            "rand_index": round(self.rand_index, 4),
            "tp_pairs": self.true_positive_pairs,
            "fp_pairs": self.false_positive_pairs,
            "fn_pairs": self.false_negative_pairs,
            "tn_pairs": self.true_negative_pairs,
            "total_pairs": self.total_pairs,
        }


def compute_fusion_accuracy(
    true_incident_groups: Sequence[str],
    pred_incident_groups: Sequence[str],
) -> FusionAccuracyReport:
    """
    Computes Pairwise Precision, Recall, F1, and Rand Index for clustering.
    Evaluates whether pairs of reports are correctly grouped into the same incident or kept separate.
    """
    n = len(true_incident_groups)
    if n != len(pred_incident_groups):
        raise ValueError("Length mismatch in clustering groups")

    if n < 2:
        return FusionAccuracyReport(
            pairwise_precision=1.0,
            pairwise_recall=1.0,
            pairwise_f1=1.0,
            rand_index=1.0,
            true_positive_pairs=0,
            false_positive_pairs=0,
            false_negative_pairs=0,
            true_negative_pairs=0,
            total_pairs=0,
        )

    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for i in range(n):
        for j in range(i + 1, n):
            same_true = (true_incident_groups[i] == true_incident_groups[j])
            same_pred = (pred_incident_groups[i] == pred_incident_groups[j])

            if same_true and same_pred:
                tp += 1
            elif not same_true and same_pred:
                fp += 1
            elif same_true and not same_pred:
                fn += 1
            else:
                tn += 1

    total_pairs = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if tp == 0 and fp == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if tp == 0 and fn == 0 else 0.0)
    f1 = (2.0 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    rand_idx = (tp + tn) / total_pairs if total_pairs > 0 else 1.0

    return FusionAccuracyReport(
        pairwise_precision=precision,
        pairwise_recall=recall,
        pairwise_f1=f1,
        rand_index=rand_idx,
        true_positive_pairs=tp,
        false_positive_pairs=fp,
        false_negative_pairs=fn,
        true_negative_pairs=tn,
        total_pairs=total_pairs,
    )


# =============================================================================
# 5. Ranking Correlation (Spearman's Rho with NaN-Safe Average-Rank Tie Handling)
# =============================================================================

def _is_rank_equal(x: Union[int, float], y: Union[int, float]) -> bool:
    """Safe equality check handling float('nan') without entering infinite loops."""
    if isinstance(x, float) and math.isnan(x):
        return isinstance(y, float) and math.isnan(y)
    if isinstance(y, float) and math.isnan(y):
        return False
    return x == y


def rankdata(a: Sequence[Union[int, float]]) -> List[float]:
    """
    Assigns standard fractional ranks to data, dealing with ties by averaging.
    Matches scipy.stats.rankdata behavior in pure Python.
    Robust against NaN and infinite values, guaranteeing deterministic loop exit.
    """
    n = len(a)
    if n == 0:
        return []

    # Sort indices, placing NaNs cleanly at the end
    sorted_indices = sorted(
        range(n),
        key=lambda i: (1, 0.0) if (isinstance(a[i], float) and math.isnan(a[i])) else (0, float(a[i])),
    )
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and _is_rank_equal(a[sorted_indices[j]], a[sorted_indices[i]]):
            j += 1
        # Indices from i to j-1 are tied
        # 1-based ranks are (i+1), (i+2), ..., j
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[sorted_indices[k]] = avg_rank
        i = j
    return ranks


def pearson_correlation(x: Sequence[float], y: Sequence[float]) -> float:
    """Computes standard Pearson correlation between two float series."""
    n = len(x)
    if n < 2:
        return 1.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)
    if var_x == 0.0 or var_y == 0.0:
        # Zero variance: if both constant and identical, correlation is 1.0, otherwise 0.0
        return 1.0 if x == y else 0.0
    denom = math.sqrt(var_x * var_y)
    if denom == 0.0:
        return 0.0
    return max(-1.0, min(1.0, cov / denom))


def compute_spearman_rho(
    true_ranks: Sequence[Union[int, float]],
    pred_ranks: Sequence[Union[int, float]],
) -> float:
    """
    Computes Spearman's rank correlation coefficient between true and predicted queue orders.
    Accurately handles tied ranks via average rank assignment.
    Range: [-1.0, 1.0], where 1.0 indicates perfect monotonically identical ranking.
    """
    n = len(true_ranks)
    if n != len(pred_ranks):
        raise ValueError("Length mismatch in rank sequences")
    if n < 2:
        return 1.0

    # Penalize NaNs in predicted priority queues to 0.0 (unranked/lowest priority)
    # A model outputting NaNs for high-urgency events cannot game the queue to achieve 1.0 correlation
    sanitized_pred = [0.0 if (isinstance(v, float) and math.isnan(v)) else v for v in pred_ranks]

    rx = rankdata(true_ranks)
    ry = rankdata(sanitized_pred)
    return round(pearson_correlation(rx, ry), 4)


# =============================================================================
# 6. Latency Profiling (Truthful: Distinguishes Measured vs Unmeasured)
# =============================================================================

@dataclass
class LatencyProfile:
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float
    sample_count: int
    is_measured: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "p50_ms": round(self.p50_ms, 2) if self.is_measured else None,
            "p90_ms": round(self.p90_ms, 2) if self.is_measured else None,
            "p95_ms": round(self.p95_ms, 2) if self.is_measured else None,
            "p99_ms": round(self.p99_ms, 2) if self.is_measured else None,
            "mean_ms": round(self.mean_ms, 2) if self.is_measured else None,
            "min_ms": round(self.min_ms, 2) if self.is_measured else None,
            "max_ms": round(self.max_ms, 2) if self.is_measured else None,
            "sample_count": self.sample_count,
            "is_measured": self.is_measured,
        }


def compute_latency_profile(latencies_ms: Sequence[float]) -> LatencyProfile:
    """
    Calculates distribution percentiles (P50, P90, P95, P99) and summary statistics.
    If empty, returns profile marked is_measured=False without fabricating mock numbers.
    """
    if not latencies_ms:
        return LatencyProfile(
            p50_ms=0.0, p90_ms=0.0, p95_ms=0.0, p99_ms=0.0,
            mean_ms=0.0, min_ms=0.0, max_ms=0.0, sample_count=0,
            is_measured=False,
        )

    sorted_lats = sorted(latencies_ms)
    n = len(sorted_lats)

    def percentile(p: float) -> float:
        idx = int(math.ceil(p * n)) - 1
        return sorted_lats[max(0, min(idx, n - 1))]

    return LatencyProfile(
        p50_ms=percentile(0.50),
        p90_ms=percentile(0.90),
        p95_ms=percentile(0.95),
        p99_ms=percentile(0.99),
        mean_ms=sum(sorted_lats) / n,
        min_ms=sorted_lats[0],
        max_ms=sorted_lats[-1],
        sample_count=n,
        is_measured=True,
    )


# =============================================================================
# 7. Multilabel Tactical Response Agency Metrics
# =============================================================================

@dataclass
class MultilabelReport:
    micro_precision: Optional[float]
    micro_recall: Optional[float]
    micro_f1: Optional[float]
    macro_f1: Optional[float]
    per_tag: Dict[str, Dict[str, Optional[float]]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "micro_precision": round(self.micro_precision, 4) if self.micro_precision is not None else None,
            "micro_recall": round(self.micro_recall, 4) if self.micro_recall is not None else None,
            "micro_f1": round(self.micro_f1, 4) if self.micro_f1 is not None else None,
            "macro_f1": round(self.macro_f1, 4) if self.macro_f1 is not None else None,
            "per_tag": self.per_tag,
        }


def compute_multilabel_response_metrics(
    true_tags: Sequence[Sequence[str]],
    pred_tags: Sequence[Sequence[str]],
) -> MultilabelReport:
    """
    Computes micro and macro multilabel precision, recall, and F1 for required response agencies.
    """
    if len(true_tags) != len(pred_tags):
        raise ValueError("Length mismatch in multilabel tag sequences")

    all_labels = sorted(list(set(t for tags in true_tags for t in tags).union(
        set(t for tags in pred_tags for t in tags)
    )))

    if not all_labels:
        return MultilabelReport(1.0, 1.0, 1.0, 1.0, {})

    per_tag: Dict[str, Dict[str, Optional[float]]] = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0
    f1_sum = 0.0

    for lbl in all_labels:
        tp = sum(1 for yt, yp in zip(true_tags, pred_tags) if lbl in yt and lbl in yp)
        fp = sum(1 for yt, yp in zip(true_tags, pred_tags) if lbl not in yt and lbl in yp)
        fn = sum(1 for yt, yp in zip(true_tags, pred_tags) if lbl in yt and lbl not in yp)

        p = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if tp == 0 and fp == 0 else 0.0)
        r = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if tp == 0 and fn == 0 else 0.0)
        f = (2.0 * p * r) / (p + r) if (p + r) > 0 else 0.0

        per_tag[lbl] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}
        total_tp += tp
        total_fp += fp
        total_fn += fn
        f1_sum += f

    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    micro_f = (2.0 * micro_p * micro_r) / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0
    macro_f = f1_sum / len(all_labels)

    return MultilabelReport(
        micro_precision=micro_p,
        micro_recall=micro_r,
        micro_f1=micro_f,
        macro_f1=macro_f,
        per_tag=per_tag,
    )


# =============================================================================
# 8. Location Extraction & Coordinate Hallucination Metrics
# =============================================================================

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance in kilometers between two GPS coordinates."""
    r = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    # Strictly clamp to [0.0, 1.0] to eliminate floating-point domain error
    a = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return r * c


@dataclass
class LocationEvaluationReport:
    mode: str
    text_match_rate: float
    coordinate_hallucination_rate: float
    total_unlocated_reports: int
    hallucinated_coordinate_count: int
    mean_distance_error_km: Optional[float]
    total_evaluated: int
    text_match_rate_on_positive: Optional[float] = None
    location_presence_accuracy: Optional[float] = None
    total_located_reports: int = 0
    coordinate_recall: Optional[float] = None
    total_geocoded_ground_truth: int = 0
    recalled_geocoded_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "text_match_rate": round(self.text_match_rate, 4),
            "text_match_rate_on_positive": round(self.text_match_rate_on_positive, 4) if self.text_match_rate_on_positive is not None else None,
            "location_presence_accuracy": round(self.location_presence_accuracy, 4) if self.location_presence_accuracy is not None else None,
            "coordinate_hallucination_rate": round(self.coordinate_hallucination_rate, 4),
            "coordinate_recall": round(self.coordinate_recall, 4) if self.coordinate_recall is not None else None,
            "total_unlocated_reports": self.total_unlocated_reports,
            "total_located_reports": self.total_located_reports,
            "total_geocoded_ground_truth": self.total_geocoded_ground_truth,
            "recalled_geocoded_count": self.recalled_geocoded_count,
            "hallucinated_coordinate_count": self.hallucinated_coordinate_count,
            "mean_distance_error_km": (
                round(self.mean_distance_error_km, 3) if self.mean_distance_error_km is not None else None
            ),
            "total_evaluated": self.total_evaluated,
        }


GENERIC_LOCATION_TOKENS: frozenset[str] = frozenset({
    "near", "road", "street", "area", "lane", "block", "under", "above",
    "behind", "beside", "across", "side", "from", "into", "next", "close",
    "towards", "between", "some", "where", "somewhere",
})


def _is_location_text_match(t_text: str, p_text: str, min_jaccard: float = 0.4) -> bool:
    """
    Robust location text matching. Rejects single-character or trivial substrings like 'e' or 'the'.
    Requires significant token overlap (Jaccard >= min_jaccard) or meaningful non-generic token match.
    """
    if not t_text or not p_text:
        return False
    t_norm = t_text.strip().lower()
    p_norm = p_text.strip().lower()
    if t_norm == p_norm:
        return True

    t_tokens = set(re.findall(r"\b\w{2,}\b", t_norm))
    p_tokens = set(re.findall(r"\b\w{2,}\b", p_norm))

    if not p_tokens or not t_tokens:
        return False

    # Single-token predicted string of length < 3 is rejected (e.g. 'e')
    if len(p_tokens) == 1 and len(next(iter(p_tokens))) < 3:
        return False

    intersection = t_tokens.intersection(p_tokens)
    union = t_tokens.union(p_tokens)

    jaccard = len(intersection) / len(union) if union else 0.0
    if jaccard >= min_jaccard:
        return True

    # Substring match allowed only if predicted is a subset with at least 1 meaningful non-generic token (>= 4 chars)
    meaningful_tokens = [tok for tok in p_tokens if len(tok) >= 4 and tok not in GENERIC_LOCATION_TOKENS]
    if p_tokens.issubset(t_tokens) and len(meaningful_tokens) >= 1:
        return True
    return False


def compute_location_metrics(
    true_locations: Sequence[Dict[str, Any]],
    pred_locations: Sequence[Dict[str, Any]],
    mode: str = "HINT_ASSISTED",
) -> LocationEvaluationReport:
    """
    Evaluates extracted locations against ground truth.
    Separates location presence match from positive text match accuracy.
    Tracks coordinate hallucinations and coordinate recall.
    """
    if len(true_locations) != len(pred_locations):
        raise ValueError("Length mismatch in location sequences")

    n = len(true_locations)
    if n == 0:
        return LocationEvaluationReport(
            mode=mode,
            text_match_rate=1.0,
            coordinate_hallucination_rate=0.0,
            total_unlocated_reports=0,
            hallucinated_coordinate_count=0,
            mean_distance_error_km=None,
            total_evaluated=0,
            text_match_rate_on_positive=None,
            location_presence_accuracy=1.0,
            total_located_reports=0,
            coordinate_recall=None,
            total_geocoded_ground_truth=0,
            recalled_geocoded_count=0,
        )

    text_matches = 0
    positive_located_count = 0
    positive_text_matches = 0
    presence_matches = 0

    unlocated_count = 0
    hallucinated_count = 0
    geocoded_gt_count = 0
    recalled_geocoded_count = 0
    distance_errors: List[float] = []

    for t_loc, p_loc in zip(true_locations, pred_locations):
        t_text = (t_loc.get("raw_text") or t_loc.get("text") or "").strip().lower()
        p_text = (p_loc.get("text") or "").strip().lower()

        t_has_text = bool(t_text)
        p_has_text = bool(p_text)

        if t_has_text == p_has_text:
            presence_matches += 1

        if t_has_text:
            positive_located_count += 1
            if p_has_text and _is_location_text_match(t_text, p_text):
                positive_text_matches += 1
                text_matches += 1
        else:
            if not p_has_text:
                text_matches += 1

        # Coordinate hallucination & recall check
        t_lat = t_loc.get("latitude")
        t_lon = t_loc.get("longitude")
        p_lat = p_loc.get("latitude")
        p_lon = p_loc.get("longitude")

        if t_lat is None or t_lon is None:
            unlocated_count += 1
            if p_lat is not None or p_lon is not None:
                hallucinated_count += 1
        else:
            geocoded_gt_count += 1
            if p_lat is not None and p_lon is not None:
                recalled_geocoded_count += 1
                dist = haversine_distance_km(t_lat, t_lon, p_lat, p_lon)
                distance_errors.append(dist)

    text_rate = text_matches / n
    pos_text_rate = (positive_text_matches / positive_located_count) if positive_located_count > 0 else None
    presence_rate = presence_matches / n
    hallucination_rate = (
        hallucinated_count / unlocated_count if unlocated_count > 0 else 0.0
    )
    coord_recall = (
        recalled_geocoded_count / geocoded_gt_count if geocoded_gt_count > 0 else None
    )
    mean_dist = (
        sum(distance_errors) / len(distance_errors) if distance_errors else None
    )

    return LocationEvaluationReport(
        mode=mode,
        text_match_rate=text_rate,
        coordinate_hallucination_rate=hallucination_rate,
        total_unlocated_reports=unlocated_count,
        hallucinated_coordinate_count=hallucinated_count,
        mean_distance_error_km=mean_dist,
        total_evaluated=n,
        text_match_rate_on_positive=pos_text_rate,
        location_presence_accuracy=presence_rate,
        total_located_reports=positive_located_count,
        coordinate_recall=coord_recall,
        total_geocoded_ground_truth=geocoded_gt_count,
        recalled_geocoded_count=recalled_geocoded_count,
    )


# =============================================================================
# 9. People-at-Risk Casualty Profiling
# =============================================================================

@dataclass
class PeopleAtRiskEvaluationReport:
    binary_accuracy: float
    binary_recall: Optional[float]
    binary_precision: Optional[float]
    count_mae: Optional[float]
    exact_count_match_rate: Optional[float]
    total_evaluated: int
    total_gt_at_risk: int
    detected_gt_at_risk: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "binary_accuracy": round(self.binary_accuracy, 4),
            "binary_recall": round(self.binary_recall, 4) if self.binary_recall is not None else None,
            "binary_precision": round(self.binary_precision, 4) if self.binary_precision is not None else None,
            "count_mae": round(self.count_mae, 4) if self.count_mae is not None else None,
            "exact_count_match_rate": round(self.exact_count_match_rate, 4) if self.exact_count_match_rate is not None else None,
            "total_evaluated": self.total_evaluated,
            "total_gt_at_risk": self.total_gt_at_risk,
            "detected_gt_at_risk": self.detected_gt_at_risk,
        }


def compute_people_at_risk_metrics(
    gt_at_risk: Sequence[bool],
    pred_at_risk: Sequence[bool],
    gt_counts: Optional[Sequence[Optional[int]]] = None,
    pred_counts: Optional[Sequence[Optional[int]]] = None,
) -> PeopleAtRiskEvaluationReport:
    """
    Computes life-safety accuracy on binary people_at_risk and numerical casualty counts.
    """
    n = len(gt_at_risk)
    if n != len(pred_at_risk):
        raise ValueError("Length mismatch in people_at_risk sequences")
    if n == 0:
        return PeopleAtRiskEvaluationReport(1.0, None, None, None, None, 0, 0, 0)

    correct_binary = 0
    tp = 0
    fp = 0
    fn = 0
    total_gt = sum(1 for g in gt_at_risk if g)

    for g, p in zip(gt_at_risk, pred_at_risk):
        if g == p:
            correct_binary += 1
        if g and p:
            tp += 1
        elif not g and p:
            fp += 1
        elif g and not p:
            fn += 1

    bin_acc = correct_binary / n
    bin_rec = (tp / (tp + fn)) if (tp + fn) > 0 else None
    bin_prec = (tp / (tp + fp)) if (tp + fp) > 0 else (1.0 if tp == 0 and fp == 0 else 0.0)

    count_mae = None
    exact_match_rate = None

    if gt_counts is not None and pred_counts is not None:
        if len(gt_counts) != n or len(pred_counts) != n:
            raise ValueError("Length mismatch in casualty count sequences")
        valid_count_diffs = []
        exact_count_matches = 0
        valid_count_samples = 0

        for gc, pc in zip(gt_counts, pred_counts):
            if gc is not None and pc is not None:
                diff = abs(gc - pc)
                valid_count_diffs.append(diff)
                if diff == 0:
                    exact_count_matches += 1
                valid_count_samples += 1

        if valid_count_samples > 0:
            count_mae = sum(valid_count_diffs) / valid_count_samples
            exact_match_rate = exact_count_matches / valid_count_samples

    return PeopleAtRiskEvaluationReport(
        binary_accuracy=bin_acc,
        binary_recall=bin_rec,
        binary_precision=bin_prec,
        count_mae=count_mae,
        exact_count_match_rate=exact_match_rate,
        total_evaluated=n,
        total_gt_at_risk=total_gt,
        detected_gt_at_risk=tp,
    )


# =============================================================================
# 10. Coverage & Schema Invariant Metrics
# =============================================================================

@dataclass
class CoverageReport:
    total_samples: int
    valid_predictions: int
    invalid_predictions: int
    coverage_rate: float
    invalid_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "valid_predictions": self.valid_predictions,
            "invalid_predictions": self.invalid_predictions,
            "coverage_rate": round(self.coverage_rate, 4),
            "invalid_reasons": self.invalid_reasons[:20],
        }


def compute_coverage_report(
    total_samples: int,
    valid_predictions: int,
    invalid_predictions: int,
    invalid_reasons: Sequence[str] = (),
) -> CoverageReport:
    """Computes prediction schema coverage rate and records failure diagnostics."""
    rate = valid_predictions / total_samples if total_samples > 0 else 0.0
    return CoverageReport(
        total_samples=total_samples,
        valid_predictions=valid_predictions,
        invalid_predictions=invalid_predictions,
        coverage_rate=rate,
        invalid_reasons=list(invalid_reasons),
    )
