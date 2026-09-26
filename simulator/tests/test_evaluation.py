"""
Karen's Ear — Evaluation & Benchmark Harness Unit Tests.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), DISASTER_SIMULATOR_ROADMAP.md
Status: Phase 5 — Evaluation & Benchmark Harness Test Suite
"""

import json
from pathlib import Path
import pytest

from simulator.evaluation.evaluate_correlation import (
    CorrelationEvaluationReport,
    evaluate_correlation_engine,
)
from simulator.evaluation.evaluate_ml import (
    MLEvaluationReport,
    evaluate_ml_predictions,
)
from simulator.evaluation.metrics import (
    ClassificationReport,
    DualCriticalRecall,
    FusionAccuracyReport,
    LatencyProfile,
    UrgencyAlignmentReport,
    compute_classification_report,
    compute_dual_critical_recall,
    compute_fusion_accuracy,
    compute_latency_profile,
    compute_spearman_rho,
    compute_urgency_alignment,
)
from simulator.evaluation.run_all_evals import (
    generate_markdown_scorecard,
    load_all_golden_events,
    run_full_benchmark,
)
from simulator.scenarios import get_scenario


# =============================================================================
# 1. Classification Metrics Tests
# =============================================================================

def test_compute_classification_report_perfect():
    y_true = ["FLOOD", "FIRE", "COLLAPSE", "FLOOD"]
    y_pred = ["FLOOD", "FIRE", "COLLAPSE", "FLOOD"]

    rep = compute_classification_report(y_true, y_pred)
    assert rep.accuracy == 1.0
    assert rep.macro_f1 == 1.0
    assert rep.macro_precision == 1.0
    assert rep.macro_recall == 1.0
    assert rep.total_samples == 4
    assert rep.confusion_matrix["FLOOD"]["FLOOD"] == 2
    assert rep.confusion_matrix["FIRE"]["FIRE"] == 1


def test_compute_classification_report_with_errors():
    y_true = ["FLOOD", "FLOOD", "FIRE", "FIRE"]
    y_pred = ["FLOOD", "FIRE", "FIRE", "FLOOD"]

    rep = compute_classification_report(y_true, y_pred)
    assert rep.accuracy == 0.5
    assert rep.confusion_matrix["FLOOD"]["FIRE"] == 1
    assert rep.confusion_matrix["FIRE"]["FLOOD"] == 1
    assert rep.per_class["FLOOD"].f1 == 0.5
    assert rep.per_class["FIRE"].f1 == 0.5


def test_classification_length_mismatch_raises_error():
    with pytest.raises(ValueError, match="Length mismatch"):
        compute_classification_report(["FLOOD"], ["FLOOD", "FIRE"])


def test_hand_calculated_3x3_confusion_matrix_and_metrics():
    """
    Explicit hand-calculated 3x3 confusion matrix test.
    Classes: A, B, C (N = 10 samples)
    True:  [A, A, A, A, B, B, B, C, C, C]
    Pred:  [A, A, B, C, B, B, A, C, A, B]

    Matrix (True \\ Pred):
         A  B  C
      A  2  1  1  (Sum: 4)
      B  1  2  0  (Sum: 3)
      C  1  1  1  (Sum: 3)
    Pred:4  4  2

    Hand calculation:
      Accuracy = 5 / 10 = 0.50
      Precisions: A=2/4=0.5, B=2/4=0.5, C=1/2=0.5 -> Macro Precision = 0.50
      Recalls:    A=2/4=0.5, B=2/3=0.6667, C=1/3=0.3333 -> Macro Recall = 0.50
      F1:         A=0.50, B=4/7=0.5714, C=2/5=0.40 -> Macro F1 = (0.5 + 4/7 + 0.4)/3 = 0.4905
    """
    y_true = ["A", "A", "A", "A", "B", "B", "B", "C", "C", "C"]
    y_pred = ["A", "A", "B", "C", "B", "B", "A", "C", "A", "B"]

    rep = compute_classification_report(y_true, y_pred)
    assert rep.total_samples == 10
    assert rep.accuracy == 0.5
    assert rep.confusion_matrix["A"]["A"] == 2
    assert rep.confusion_matrix["A"]["B"] == 1
    assert rep.confusion_matrix["A"]["C"] == 1
    assert rep.confusion_matrix["B"]["A"] == 1
    assert rep.confusion_matrix["B"]["B"] == 2
    assert rep.confusion_matrix["B"]["C"] == 0
    assert rep.confusion_matrix["C"]["A"] == 1
    assert rep.confusion_matrix["C"]["B"] == 1
    assert rep.confusion_matrix["C"]["C"] == 1

    assert rep.macro_precision == 0.5
    assert abs(rep.macro_recall - 0.5) < 1e-6
    assert abs(rep.macro_f1 - (0.5 + 4 / 7 + 0.4) / 3) < 1e-4

    assert rep.per_class["A"].precision == 0.5
    assert rep.per_class["A"].recall == 0.5
    assert rep.per_class["A"].f1 == 0.5

    assert rep.per_class["B"].precision == 0.5
    assert abs(rep.per_class["B"].recall - 2 / 3) < 1e-6
    assert abs(rep.per_class["B"].f1 - 4 / 7) < 1e-6

    assert rep.per_class["C"].precision == 0.5
    assert abs(rep.per_class["C"].recall - 1 / 3) < 1e-6
    assert rep.per_class["C"].f1 == 0.4



# =============================================================================
# 2. Dual-Level Critical Recall Tests
# =============================================================================

def test_compute_dual_critical_recall_perfect():
    report_evals = [
        {"report_id": "rep-1", "true_urgency": "CRITICAL", "pred_urgency": "CRITICAL"},
        {"report_id": "rep-2", "true_urgency": "CRITICAL", "pred_urgency": "CRITICAL"},
        {"report_id": "rep-3", "true_urgency": "LOW", "pred_urgency": "LOW"},
    ]
    incident_evals = [
        {"incident_group": "inc-A", "true_urgency": "CRITICAL", "pred_urgency": "CRITICAL"},
        {"incident_group": "inc-B", "true_urgency": "LOW", "pred_urgency": "LOW"},
    ]

    dual = compute_dual_critical_recall(report_evals, incident_evals)
    assert dual.report_critical_recall == 1.0
    assert dual.total_ground_truth_critical_reports == 2
    assert dual.correctly_identified_critical_reports == 2
    assert dual.incident_critical_recall == 1.0
    assert len(dual.missed_critical_report_ids) == 0


def test_compute_dual_critical_recall_with_misses():
    report_evals = [
        {"report_id": "rep-1", "true_urgency": "CRITICAL", "pred_urgency": "CRITICAL"},
        {"report_id": "rep-2", "true_urgency": "CRITICAL", "pred_urgency": "MEDIUM"},  # Missed
    ]
    incident_evals = [
        {"incident_group": "inc-A", "true_urgency": "CRITICAL", "pred_urgency": "HIGH"},  # Missed
    ]

    dual = compute_dual_critical_recall(report_evals, incident_evals)
    assert dual.report_critical_recall == 0.5
    assert dual.missed_critical_report_ids == ["rep-2"]
    assert dual.incident_critical_recall == 0.0
    assert dual.missed_critical_situation_ids == ["inc-A"]


# =============================================================================
# 3. Urgency Alignment MAE Tests
# =============================================================================

def test_urgency_alignment_mae():
    y_true = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    y_pred = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    align = compute_urgency_alignment(y_true, y_pred)
    assert align.mae == 0.0
    assert align.high_urgency_recall == 1.0
    assert align.total_evaluated == 4

    # Off by one tier across all samples (1.0 vs 2.0, etc.)
    y_pred_off = ["MEDIUM", "HIGH", "CRITICAL", "HIGH"]
    align_off = compute_urgency_alignment(y_true, y_pred_off)
    assert align_off.mae == 1.0
    assert align_off.high_urgency_recall == 1.0  # HIGH and CRITICAL still classified as >= HIGH


# =============================================================================
# 4. Pairwise Clustering Fusion Tests
# =============================================================================

def test_pairwise_fusion_perfect():
    true_groups = ["inc-1", "inc-1", "inc-2", "inc-2"]
    pred_groups = ["cluster-A", "cluster-A", "cluster-B", "cluster-B"]

    report = compute_fusion_accuracy(true_groups, pred_groups)
    assert report.pairwise_precision == 1.0
    assert report.pairwise_recall == 1.0
    assert report.pairwise_f1 == 1.0
    assert report.rand_index == 1.0
    assert report.true_positive_pairs == 2
    assert report.false_positive_pairs == 0
    assert report.false_negative_pairs == 0


def test_pairwise_fusion_imperfect():
    true_groups = ["inc-1", "inc-1", "inc-2", "inc-2"]
    # All merged into single cluster
    pred_groups = ["cluster-A", "cluster-A", "cluster-A", "cluster-A"]

    report = compute_fusion_accuracy(true_groups, pred_groups)
    # TP = 2, FP = 4, FN = 0, TN = 0
    assert report.pairwise_recall == 1.0
    assert report.pairwise_precision < 1.0
    assert report.false_positive_pairs == 4


# =============================================================================
# 5. Spearman's Rho Tests
# =============================================================================

def test_spearman_rho():
    assert compute_spearman_rho([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert compute_spearman_rho([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0


# =============================================================================
# 6. Latency Profile Tests
# =============================================================================

def test_latency_profile():
    lats = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    prof = compute_latency_profile(lats)
    assert prof.min_ms == 10.0
    assert prof.max_ms == 100.0
    assert prof.mean_ms == 55.0
    assert prof.p50_ms == 50.0
    assert prof.sample_count == 10

    empty = compute_latency_profile([])
    assert empty.sample_count == 0
    assert empty.mean_ms == 0.0


# =============================================================================
# 7. ML & Correlation Evaluator Integration Tests
# =============================================================================

def test_evaluate_ml_predictions_hermetic():
    events = get_scenario("flood_rasulgarh")
    report = evaluate_ml_predictions(events)

    assert report.total_samples == 15
    assert report.hazard_classification.accuracy == 1.0
    assert report.report_critical_recall == 1.0
    assert report.urgency_mae == 0.0
    assert report.is_hermetic_mock is True


def test_evaluate_correlation_engine_flood():
    events = get_scenario("flood_rasulgarh")
    report = evaluate_correlation_engine(events)

    assert report.total_reports_processed == 15
    assert report.fusion_accuracy.pairwise_f1 == 1.0
    assert report.duplicate_f1 == 1.0
    assert report.incident_critical_recall == 1.0
    assert report.corroboration_boost_verified is True
    assert report.duplicate_suppression_verified is True
    assert report.scenario_rank_1_assertion_passed is True


def test_run_all_evals_master_runner(tmp_path):
    output_dir = tmp_path / "benchmark_out"
    json_rep = run_full_benchmark(output_dir=str(output_dir), quiet=True)

    json_path = output_dir / "evaluation_scorecard.json"
    md_path = output_dir / "evaluation_scorecard.md"

    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_dispatches"] == 27
    assert data["ml_evaluation"]["report_critical_recall"] == 1.0
    assert data["correlation_evaluation"]["scenario_rank_1_assertion_passed"] is True

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    assert "Karen's Ear — Emergency Intelligence System Benchmark Scorecard" in md_text
    assert "Report-Level Critical Recall" in md_text
    assert "Incident-Level Critical Recall" in md_text
    assert "Scenario Rank #1 Escalation" in md_text
