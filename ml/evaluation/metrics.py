"""
Karen's Ear — ML Evaluation Core Metric Computations.

Feature 11 — Quantitative Evaluation Layer.
Provides deterministic, zero-dependency metric calculation functions:
- Precision, Recall, F1 (with explicit zero-denominator handling)
- Confusion Matrix generation & per-class decomposition
- Macro Precision, Recall, F1 averaging
- Critical Recall and Critical False-Negative Rate (FNR = FN / (TP + FN))
- Semantic Similarity ROC curve and ROC-AUC calculation
- Threshold-calibrated classification metrics
- Latency percentile calculation (p50, p90, p95, p99)
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np


def calculate_precision(tp: int, fp: int) -> float:
    """
    Computes precision = TP / (TP + FP).
    Explicitly handles zero denominator by returning 0.0.
    """
    denom = tp + fp
    if denom <= 0:
        return 0.0
    return round(float(tp / denom), 4)


def calculate_recall(tp: int, fn: int) -> float:
    """
    Computes recall = TP / (TP + FN).
    Explicitly handles zero denominator by returning 0.0.
    """
    denom = tp + fn
    if denom <= 0:
        return 0.0
    return round(float(tp / denom), 4)


def calculate_f1(precision: float, recall: float) -> float:
    """
    Computes harmonic mean F1 = 2 * (P * R) / (P + R).
    Explicitly handles zero denominator by returning 0.0.
    """
    denom = precision + recall
    if denom <= 0.0:
        return 0.0
    return round(float(2.0 * (precision * recall) / denom), 4)


def calculate_f1_from_counts(tp: int, fp: int, fn: int) -> float:
    """
    Computes F1 score directly from TP, FP, FN counts:
    F1 = 2 * TP / (2 * TP + FP + FN).
    Explicitly handles zero denominator by returning 0.0.
    """
    denom = 2 * tp + fp + fn
    if denom <= 0:
        return 0.0
    return round(float((2 * tp) / denom), 4)


def calculate_accuracy(correct: int, total: int) -> float:
    """
    Computes accuracy = correct / total.
    Explicitly handles zero denominator by returning 0.0.
    """
    if total <= 0:
        return 0.0
    return round(float(correct / total), 4)


def compute_confusion_matrix(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: Sequence[str],
) -> dict[str, dict[str, int]]:
    """
    Builds a deterministic 2D confusion matrix represented as a nested dict:
    matrix[true_label][predicted_label] = count.
    """
    matrix: dict[str, dict[str, int]] = {
        true_l: {pred_l: 0 for pred_l in labels}
        for true_l in labels
    }
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
        elif t in matrix:
            # Handle unknown predicted class
            pass
    return matrix


def calculate_per_class_metrics(
    matrix: dict[str, dict[str, int]],
    labels: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """
    Computes per-class TP, FP, FN, TN, Precision, Recall, F1, and support
    from a multi-class confusion matrix.
    """
    total_samples = sum(sum(matrix[r].values()) for r in labels if r in matrix)
    results: dict[str, dict[str, Any]] = {}

    for label in labels:
        if label not in matrix:
            results[label] = {
                "tp": 0,
                "fp": 0,
                "fn": 0,
                "tn": 0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "support": 0,
            }
            continue

        tp = matrix[label].get(label, 0)
        # FP: predicted as label, but actually another class
        fp = sum(matrix[other].get(label, 0) for other in labels if other != label and other in matrix)
        # FN: actually label, but predicted as another class
        fn = sum(matrix[label].get(other, 0) for other in labels if other != label)
        # TN: neither actually label nor predicted as label
        tn = total_samples - (tp + fp + fn)
        support = tp + fn

        prec = calculate_precision(tp, fp)
        rec = calculate_recall(tp, fn)
        f1 = calculate_f1(prec, rec)

        results[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "support": support,
        }

    return results


def calculate_macro_metrics(
    per_class_metrics: dict[str, dict[str, Any]],
    only_supported: bool = False,
) -> dict[str, float]:
    """
    Computes unweighted macro Precision, Recall, and F1 across evaluated classes.
    If only_supported is True, averages only over classes with support > 0.
    """
    classes_to_average = [
        m for m in per_class_metrics.values()
        if (not only_supported) or (m.get("support", 0) > 0)
    ]
    if not classes_to_average:
        return {"macro_precision": 0.0, "macro_recall": 0.0, "macro_f1": 0.0}

    macro_p = sum(c["precision"] for c in classes_to_average) / len(classes_to_average)
    macro_r = sum(c["recall"] for c in classes_to_average) / len(classes_to_average)
    macro_f1 = sum(c["f1"] for c in classes_to_average) / len(classes_to_average)

    return {
        "macro_precision": round(float(macro_p), 4),
        "macro_recall": round(float(macro_r), 4),
        "macro_f1": round(float(macro_f1), 4),
    }


def calculate_critical_recall(tp: int, fn: int) -> float:
    """
    Computes recall for the CRITICAL urgency class:
    Critical Recall = TP / (TP + FN).
    """
    return calculate_recall(tp, fn)


def calculate_critical_false_negative_rate(tp: int, fn: int) -> float:
    """
    Computes false negative rate specifically for the CRITICAL urgency class:
    Critical FNR = FN / (TP + FN).
    Positives are actual CRITICAL dispatches.
    Zero denominator explicitly returns 0.0.
    """
    denom = tp + fn
    if denom <= 0:
        return 0.0
    return round(float(fn / denom), 4)


def calculate_roc_curve(
    y_true: Sequence[int],
    y_score: Sequence[float],
) -> tuple[list[float], list[float], list[float]]:
    """
    Computes Receiver Operating Characteristic (ROC) curve:
    Returns (fpr_list, tpr_list, thresholds_list).
    Handles edge cases deterministically.
    """
    if len(y_true) != len(y_score) or len(y_true) == 0:
        return [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]

    n_pos = sum(1 for y in y_true if y == 1)
    n_neg = len(y_true) - n_pos

    if n_pos == 0 or n_neg == 0:
        # Undefined curve if only one class exists
        return [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]

    # Sort descending by score
    desc_indices = np.argsort(y_score)[::-1]
    sorted_scores = np.array(y_score)[desc_indices]
    sorted_true = np.array(y_true)[desc_indices]

    # Find distinct threshold points
    distinct_value_indices = np.where(np.diff(sorted_scores))[0]
    threshold_idxs = np.r_[distinct_value_indices, len(sorted_true) - 1]

    tps = np.cumsum(sorted_true)[threshold_idxs]
    fps = 1 + threshold_idxs - tps

    tpr = list(tps / n_pos)
    fpr = list(fps / n_neg)
    thresholds = list(sorted_scores[threshold_idxs])

    # Prepend (0, 0) origin at threshold = max_score + 1e-4
    fpr = [0.0] + [round(float(x), 4) for x in fpr]
    tpr = [0.0] + [round(float(x), 4) for x in tpr]
    thresholds = [round(float(thresholds[0] + 0.01), 4)] + [round(float(x), 4) for x in thresholds]

    return fpr, tpr, thresholds


def calculate_roc_auc(
    y_true: Sequence[int],
    y_score: Sequence[float],
) -> float:
    """
    Computes ROC-AUC (Area Under the Receiver Operating Characteristic Curve)
    using the exact Mann-Whitney U rank statistic with tie averaging.
    Deterministic, numerically stable, and exact match to standard definitions.
    """
    if len(y_true) != len(y_score) or len(y_true) == 0:
        return 0.0

    n_pos = sum(1 for y in y_true if y == 1)
    n_neg = len(y_true) - n_pos

    if n_pos == 0 or n_neg == 0:
        return 0.0

    # Rank data with average rank for ties
    ranks = _compute_fractional_ranks(y_score)
    pos_rank_sum = sum(ranks[i] for i, y in enumerate(y_true) if y == 1)

    # Mann-Whitney U formula
    u = pos_rank_sum - (n_pos * (n_pos + 1)) / 2.0
    auc = u / (n_pos * n_neg)
    return round(float(auc), 4)


def _compute_fractional_ranks(scores: Sequence[float]) -> list[float]:
    """Computes 1-based fractional ranks for tied values."""
    n = len(scores)
    sorted_indices = sorted(range(n), key=lambda i: scores[i])
    ranks = [0.0] * n

    i = 0
    while i < n:
        j = i
        while j < n - 1 and scores[sorted_indices[j]] == scores[sorted_indices[j + 1]]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[sorted_indices[k]] = avg_rank
        i = j + 1

    return ranks


def calculate_binary_metrics_at_threshold(
    y_true: Sequence[int],
    y_score: Sequence[float],
    threshold: float,
) -> dict[str, Any]:
    """
    Computes TP, FP, FN, TN, Precision, Recall, and F1 at a given decision threshold:
    positive prediction if score >= threshold.
    """
    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for yt, score in zip(y_true, y_score):
        yp = 1 if score >= threshold else 0
        if yt == 1 and yp == 1:
            tp += 1
        elif yt == 0 and yp == 1:
            fp += 1
        elif yt == 1 and yp == 0:
            fn += 1
        else:
            tn += 1

    prec = calculate_precision(tp, fp)
    rec = calculate_recall(tp, fn)
    f1 = calculate_f1(prec, rec)
    acc = calculate_accuracy(tp + tn, len(y_true))

    return {
        "threshold": round(float(threshold), 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "accuracy": acc,
        "total_pairs": len(y_true),
    }


def calculate_percentiles(
    values: Sequence[float],
    percentiles: Sequence[float] = (50.0, 90.0, 95.0, 99.0),
) -> dict[str, float]:
    """
    Calculates empirical percentile values (e.g. p50, p90, p95, p99) for latencies.
    Returns empty/0.0 values if values list is empty.
    """
    if not values:
        return {f"p{int(p)}": 0.0 for p in percentiles}

    arr = np.array(values, dtype=np.float64)
    result: dict[str, float] = {}
    for p in percentiles:
        key = f"p{int(p)}" if p == int(p) else f"p{p}"
        val = float(np.percentile(arr, p))
        result[key] = round(val, 2)
    return result
