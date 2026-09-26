"""
Karen's Ear — ML Evaluation Metrics Deterministic Unit Tests.

Feature 11 — Quantitative Evaluation Layer.
Tests all 12 core requirements:
1. Precision calculation
2. Recall calculation
3. F1 calculation
4. Zero-denominator handling (no NaN, no DivisionByZero, returns 0.0)
5. Confusion matrix generation & per-class decomposition
6. Critical false-negative rate calculation (FN / (TP + FN))
7. Entity exact-match normalization behavior
8. Embedding threshold metrics (TP, FP, FN, TN, precision, recall)
9. ROC-AUC calculation (exact Mann-Whitney U, ties, bounds)
10. Percentile latency calculation (p50, p90, p95, p99)
11. Performance result structure & memory metrics
12. Evaluation report schema & JSON serialization
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from ml.evaluation.metrics import (
    calculate_accuracy,
    calculate_binary_metrics_at_threshold,
    calculate_critical_false_negative_rate,
    calculate_critical_recall,
    calculate_f1,
    calculate_f1_from_counts,
    calculate_macro_metrics,
    calculate_per_class_metrics,
    calculate_percentiles,
    calculate_precision,
    calculate_recall,
    calculate_roc_auc,
    calculate_roc_curve,
    compute_confusion_matrix,
)
from ml.evaluation.entity_evaluator import normalize_span
from ml.evaluation.performance_evaluator import (
    ColdStartMemoryMetrics,
    ColdStartMetrics,
    EnvironmentMetadata,
    LatencyDistribution,
    MemoryUsageMetrics,
    PerformanceEvaluationResult,
)
from ml.evaluation.report import EvaluationReport, Finding


# ==============================================================================
# 1. Precision Calculation
# ==============================================================================
def test_precision_calculation_standard():
    """Precision equals TP / (TP + FP)."""
    assert calculate_precision(tp=8, fp=2) == 0.8
    assert calculate_precision(tp=10, fp=0) == 1.0
    assert calculate_precision(tp=0, fp=5) == 0.0


# ==============================================================================
# 2. Recall Calculation
# ==============================================================================
def test_recall_calculation_standard():
    """Recall equals TP / (TP + FN)."""
    assert calculate_recall(tp=8, fn=2) == 0.8
    assert calculate_recall(tp=10, fn=0) == 1.0
    assert calculate_recall(tp=0, fn=5) == 0.0


# ==============================================================================
# 3. F1 Calculation
# ==============================================================================
def test_f1_calculation_standard():
    """F1 is harmonic mean: 2 * (P * R) / (P + R)."""
    # Precision = 0.8, Recall = 0.8 -> F1 = 0.8
    assert calculate_f1(0.8, 0.8) == 0.8
    # Precision = 1.0, Recall = 0.5 -> 2 * 0.5 / 1.5 = 2/3 = 0.6667
    assert calculate_f1(1.0, 0.5) == 0.6667
    # Count-based F1
    assert calculate_f1_from_counts(tp=8, fp=2, fn=2) == 0.8


# ==============================================================================
# 4. Zero-Denominator Handling (No Crashes, No NaNs)
# ==============================================================================
def test_zero_denominator_handling():
    """Zero denominators must safely return 0.0 without raising exceptions or returning NaN."""
    # Precision with TP=0, FP=0
    prec = calculate_precision(0, 0)
    assert prec == 0.0
    assert not math.isnan(prec)

    # Recall with TP=0, FN=0
    rec = calculate_recall(0, 0)
    assert rec == 0.0
    assert not math.isnan(rec)

    # F1 with P=0, R=0
    f1 = calculate_f1(0.0, 0.0)
    assert f1 == 0.0
    assert not math.isnan(f1)

    # F1 from counts with all zeros
    f1_c = calculate_f1_from_counts(0, 0, 0)
    assert f1_c == 0.0
    assert not math.isnan(f1_c)

    # Accuracy with total=0
    acc = calculate_accuracy(0, 0)
    assert acc == 0.0
    assert not math.isnan(acc)


# ==============================================================================
# 5. Confusion Matrix Generation & Per-Class Decomposition
# ==============================================================================
def test_confusion_matrix_and_per_class_metrics():
    """Multi-class confusion matrix matches per-class decomposition."""
    labels = ["CLASS_A", "CLASS_B", "CLASS_C"]
    y_true = ["CLASS_A", "CLASS_A", "CLASS_B", "CLASS_B", "CLASS_C"]
    y_pred = ["CLASS_A", "CLASS_B", "CLASS_B", "CLASS_C", "CLASS_C"]

    matrix = compute_confusion_matrix(y_true, y_pred, labels)

    # Check matrix counts
    assert matrix["CLASS_A"]["CLASS_A"] == 1
    assert matrix["CLASS_A"]["CLASS_B"] == 1
    assert matrix["CLASS_A"]["CLASS_C"] == 0
    assert matrix["CLASS_B"]["CLASS_B"] == 1
    assert matrix["CLASS_B"]["CLASS_C"] == 1
    assert matrix["CLASS_C"]["CLASS_C"] == 1

    per_class = calculate_per_class_metrics(matrix, labels)

    # For CLASS_A: TP=1, FP=0, FN=1, TN=3, Support=2
    ca = per_class["CLASS_A"]
    assert ca["tp"] == 1
    assert ca["fp"] == 0
    assert ca["fn"] == 1
    assert ca["tn"] == 3
    assert ca["support"] == 2
    assert ca["precision"] == 1.0
    assert ca["recall"] == 0.5
    assert ca["f1"] == 0.6667

    # For CLASS_B: TP=1, FP=1, FN=1, TN=2, Support=2
    cb = per_class["CLASS_B"]
    assert cb["tp"] == 1
    assert cb["fp"] == 1
    assert cb["fn"] == 1
    assert cb["precision"] == 0.5
    assert cb["recall"] == 0.5
    assert cb["f1"] == 0.5

    # Macro averages
    macro = calculate_macro_metrics(per_class)
    assert "macro_precision" in macro
    assert "macro_recall" in macro
    assert "macro_f1" in macro
    assert 0.0 <= macro["macro_f1"] <= 1.0


# ==============================================================================
# 6. Critical False-Negative Rate Calculation
# ==============================================================================
def test_critical_false_negative_rate():
    """Critical FNR must strictly be FN / (TP + FN)."""
    # 9 TP, 1 FN -> FNR = 1 / 10 = 0.1, Recall = 0.9
    assert calculate_critical_false_negative_rate(tp=9, fn=1) == 0.1
    assert calculate_critical_recall(tp=9, fn=1) == 0.9

    # 10 TP, 0 FN -> FNR = 0.0
    assert calculate_critical_false_negative_rate(tp=10, fn=0) == 0.0

    # 0 TP, 5 FN -> FNR = 5 / 5 = 1.0 (worst case: all critical events missed)
    assert calculate_critical_false_negative_rate(tp=0, fn=5) == 1.0

    # Zero denominator (no critical events in set) -> 0.0 without crash
    assert calculate_critical_false_negative_rate(tp=0, fn=0) == 0.0
    assert calculate_critical_recall(tp=0, fn=0) == 0.0


# ==============================================================================
# 7. Entity Exact-Match Normalization Behavior
# ==============================================================================
def test_entity_exact_match_normalization():
    """Span normalization strips, lowercases, and collapses whitespace."""
    assert normalize_span("  Rasulgarh  Flyover  ") == "rasulgarh flyover"
    assert normalize_span("NH16\n near  Patia") == "nh16 near patia"
    assert normalize_span(None) == ""
    assert normalize_span("") == ""


# ==============================================================================
# 8. Embedding Threshold Metrics
# ==============================================================================
def test_embedding_threshold_metrics():
    """Binary metrics correctly categorize pairs given a threshold."""
    y_true = [1, 1, 0, 0]
    scores = [0.90, 0.70, 0.60, 0.40]

    # Threshold 0.75:
    # scores >= 0.75 -> [1, 0, 0, 0]
    # TP: (true=1, pred=1) -> pair 0
    # FN: (true=1, pred=0) -> pair 1
    # TN: (true=0, pred=0) -> pair 2, pair 3
    # FP: 0
    res = calculate_binary_metrics_at_threshold(y_true, scores, threshold=0.75)
    assert res["tp"] == 1
    assert res["fn"] == 1
    assert res["fp"] == 0
    assert res["tn"] == 2
    assert res["precision"] == 1.0
    assert res["recall"] == 0.5
    assert res["f1"] == 0.6667
    assert res["accuracy"] == 0.75

    # Threshold 0.50:
    # scores >= 0.50 -> [1, 1, 1, 0]
    # TP=2, FP=1, FN=0, TN=1
    res50 = calculate_binary_metrics_at_threshold(y_true, scores, threshold=0.50)
    assert res50["tp"] == 2
    assert res50["fp"] == 1
    assert res50["fn"] == 0
    assert res50["tn"] == 1
    assert res50["precision"] == 0.6667
    assert res50["recall"] == 1.0


# ==============================================================================
# 9. ROC-AUC Calculation
# ==============================================================================
def test_roc_auc_calculation():
    """ROC-AUC produces exact deterministic results across scenarios."""
    # Perfect ranking: all positives scored higher than all negatives
    y_true_perfect = [1, 1, 1, 0, 0, 0]
    y_score_perfect = [0.95, 0.90, 0.85, 0.40, 0.30, 0.20]
    assert calculate_roc_auc(y_true_perfect, y_score_perfect) == 1.0

    # Perfectly inverted ranking
    y_score_inverted = [0.20, 0.30, 0.40, 0.85, 0.90, 0.95]
    assert calculate_roc_auc(y_true_perfect, y_score_inverted) == 0.0

    # Tied scores with average rank
    y_true_tied = [1, 0]
    y_score_tied = [0.5, 0.5]
    assert calculate_roc_auc(y_true_tied, y_score_tied) == 0.5

    # Single class edge cases
    assert calculate_roc_auc([1, 1, 1], [0.9, 0.8, 0.7]) == 0.0
    assert calculate_roc_auc([], []) == 0.0

    # ROC curve points
    fpr, tpr, thresholds = calculate_roc_curve(y_true_perfect, y_score_perfect)
    assert fpr[0] == 0.0 and tpr[0] == 0.0
    assert fpr[-1] == 1.0 and tpr[-1] == 1.0


# ==============================================================================
# 10. Percentile Latency Calculation
# ==============================================================================
def test_percentile_latency_calculation():
    """Empirical percentiles (p50, p90, p95, p99) computed correctly."""
    # 100 values from 1.0 to 100.0
    latencies = [float(i) for i in range(1, 101)]
    p = calculate_percentiles(latencies, (50.0, 90.0, 95.0, 99.0))

    assert p["p50"] == 50.5
    assert p["p90"] == 90.1
    assert p["p95"] == 95.05
    assert p["p99"] == 99.01

    # Empty values edge case
    empty_p = calculate_percentiles([], (50.0, 95.0))
    assert empty_p["p50"] == 0.0
    assert empty_p["p95"] == 0.0


# ==============================================================================
# 11. Performance Result Structure
# ==============================================================================
def test_performance_result_structure():
    """PerformanceEvaluationResult packages metadata, memory, and latencies."""
    env = EnvironmentMetadata(
        python_version="3.13.5",
        platform="Windows-11",
        operating_system="Windows",
        architecture="AMD64",
        processor="Intel64",
        process_pid=1234,
        model_version="1.0.0",
    )
    dist = LatencyDistribution(
        unit="milliseconds",
        sample_count=20,
        p50_ms=45.2,
        p90_ms=80.1,
        p95_ms=92.4,
        p99_ms=110.0,
        mean_ms=52.3,
        min_ms=30.0,
        max_ms=115.0,
        std_ms=15.2,
        throughput_items_per_sec=19.1,
    )
    cold_mem = ColdStartMemoryMetrics(
        methodology="Fresh subprocess Resident Set Size (RSS) and peak working set via psutil",
        initial_rss_mb=210.0,
        post_inference_rss_mb=320.0,
        rss_delta_mb=110.0,
        peak_working_set_mb=360.0,
        limitation_notice="Process RSS reflects operating system virtual memory pages resident in RAM.",
    )
    cold_start = ColdStartMetrics(
        methodology="fresh subprocess first full inference",
        definition="Time from fresh subprocess execution immediately before ML initialization through completion of first full inference_engine.analyze(...) call.",
        latency_ms=450.2,
        unit="milliseconds",
        memory=cold_mem,
        subprocess_pid=5678,
    )
    res = PerformanceEvaluationResult(
        fixture_name="INCIDENT_BENCHMARK_DATASET",
        environment=env,
        cold_start=cold_start,
        warm_latency=dist,
        elapsed_seconds=1.5,
    )

    d = res.to_dict()
    assert d["cold_start"]["latency_ms"] == 450.2
    assert d["cold_start"]["methodology"] == "fresh subprocess first full inference"
    assert d["cold_start_latency_ms"] == 450.2
    assert d["warm_latency"]["p50_ms"] == 45.2
    assert "warmup_samples" in d["warm_latency"]
    assert "timed_samples" in d["warm_latency"]
    assert d["memory"]["rss_delta_mb"] == 110.0
    assert d["environment"]["python_version"] == "3.13.5"
    assert "timestamp_utc" not in d["environment"]


# ==============================================================================
# 12. Evaluation Report Schema & Serialization
# ==============================================================================
def test_evaluation_report_schema_and_serialization(tmp_path: Path):
    """EvaluationReport serializes to valid JSON and formats human-readable text."""
    report = EvaluationReport(
        evaluation_version="1.0.0",
        timestamp_utc="2026-09-26T12:00:00Z",
        environment={"python_version": "3.13.5", "model_version": "1.0.0"},
        classification={"fixture_name": "INCIDENT_BENCHMARK_DATASET", "accuracy": 0.95, "sample_count": 63},
        entity_extraction={"fixture_name": "NER_BENCHMARK_DATASET", "sample_count": 30},
        urgency={"fixture_name": "CURATED_URGENCY_BENCHMARK", "critical_recall": 1.0, "critical_false_negative_rate": 0.0},
        embeddings={"fixture_name": "CURATED_SEMANTIC_PAIRS", "roc_auc": 0.98, "configured_threshold": 0.75},
        performance={"cold_start_latency_ms": 350.0, "warm_latency": {"p50_ms": 40.0}},
        findings=[
            {
                "category": "measured_results",
                "title": "High Critical Recall",
                "details": "Measured 100% Critical recall on curated set.",
            }
        ],
    )

    # Verify JSON serialization
    save_file = tmp_path / "test_report.json"
    saved_path = report.save(save_file)
    assert saved_path.exists()

    with open(saved_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["evaluation_version"] == "1.0.0"
    assert loaded["urgency"]["critical_recall"] == 1.0
    assert loaded["embeddings"]["roc_auc"] == 0.98

    # Verify human-readable summary
    summary = report.format_human_readable_summary()
    assert "# Karen's Ear — Machine Learning Evaluation Report" in summary
    assert "Incident Classification Evaluation" in summary
    assert "Urgency Engine Evaluation" in summary
    assert "Dense Semantic Embedding Evaluation" in summary
    assert "Performance & Resource Profiling" in summary
