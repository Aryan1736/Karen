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
    EvaluationMode,
    MLEvaluationReport,
    build_real_ml_predictor,
    evaluate_ml_predictions,
    evaluate_real_ml,
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
    compute_multilabel_response_metrics,
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


def test_latency_profile_invariants():
    """Verify mathematical invariants: min <= mean <= max, min <= p50 <= max, min <= p95 <= max."""
    test_cases = [
        [15.5],
        [10.0, 20.0, 30.0, 40.0],
        [15329.55, 24.13, 22.69, 25.34, 24.41, 18.99, 42.47],
        [50.0, 50.0, 50.0, 50.0],
    ]
    for case in test_cases:
        prof = compute_latency_profile(case)
        assert prof.min_ms <= prof.mean_ms <= prof.max_ms
        assert prof.min_ms <= prof.p50_ms <= prof.max_ms
        assert prof.min_ms <= prof.p90_ms <= prof.max_ms
        assert prof.min_ms <= prof.p95_ms <= prof.max_ms
        assert prof.min_ms <= prof.p99_ms <= prof.max_ms
        assert prof.sample_count == len(case)


def test_latency_profile_known_sample():
    """Verify exact percentile index mapping on known [10, 20, 30, 40] list."""
    lats = [10.0, 20.0, 30.0, 40.0]
    prof = compute_latency_profile(lats)
    assert prof.sample_count == 4
    assert prof.min_ms == 10.0
    assert prof.max_ms == 40.0
    assert prof.mean_ms == 25.0
    # idx for 0.50 is ceil(0.50*4)-1 = 1 -> 20.0
    assert prof.p50_ms == 20.0
    # idx for 0.90 is ceil(0.90*4)-1 = 3 -> 40.0
    assert prof.p90_ms == 40.0
    assert prof.p95_ms == 40.0
    assert prof.p99_ms == 40.0


def test_latency_cold_warm_separation():
    """Verify cold-start separation: warm stats must be computed ONLY from warm samples."""
    latencies = [1000.0, 10.0, 20.0, 30.0]
    cold_latency = latencies[0]
    assert cold_latency == 1000.0

    warm_lats = latencies[1:]
    warm_prof = compute_latency_profile(warm_lats)

    assert warm_prof.sample_count == 3
    assert warm_prof.min_ms == 10.0
    assert warm_prof.max_ms == 30.0
    assert warm_prof.mean_ms == 20.0
    assert warm_prof.p50_ms == 20.0
    assert warm_prof.min_ms <= warm_prof.mean_ms <= warm_prof.max_ms
    assert warm_prof.min_ms <= warm_prof.p50_ms <= warm_prof.max_ms
    assert warm_prof.min_ms <= warm_prof.p95_ms <= warm_prof.max_ms


def test_response_metric_zero_denominator_policy():
    """
    Verify documented zero-denominator convention in compute_multilabel_response_metrics:
    - If a label has zero ground-truth support (tp + fn == 0), the evaluator's policy
      returns recall = 1.0 (via '1.0 if tp == 0 and fn == 0 else 0.0').
    - If the model predicts it (fp > 0), precision = 0.0 and f1 = 0.0.
    - If a label has positive support, standard recall = tp / (tp + fn).
    """
    true_tags = [["SEARCH_AND_RESCUE"], ["SEARCH_AND_RESCUE"], []]
    pred_tags = [["SEARCH_AND_RESCUE"], ["FIRE_HAZMAT"], ["PUBLIC_WORKS_UTILITY"]]

    rep = compute_multilabel_response_metrics(true_tags, pred_tags)

    # SEARCH_AND_RESCUE: TP=1, FP=0, FN=1 -> P=1.0, R=0.5, F1=0.6667
    sar = rep.per_tag["SEARCH_AND_RESCUE"]
    assert sar["precision"] == 1.0
    assert sar["recall"] == 0.5
    assert sar["f1"] == 0.6667

    # FIRE_HAZMAT: TP=0, FP=1, FN=0 -> Support=0 -> P=0.0, R=1.0 (zero-support rule), F1=0.0
    fh = rep.per_tag["FIRE_HAZMAT"]
    assert fh["precision"] == 0.0
    assert fh["recall"] == 1.0
    assert fh["f1"] == 0.0

    # PUBLIC_WORKS_UTILITY: TP=0, FP=1, FN=0 -> Support=0 -> P=0.0, R=1.0 (zero-support rule), F1=0.0
    pwu = rep.per_tag["PUBLIC_WORKS_UTILITY"]
    assert pwu["precision"] == 0.0
    assert pwu["recall"] == 1.0
    assert pwu["f1"] == 0.0



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


# =============================================================================
# 8. Real ML Evaluation & Ground Truth Firewall Tests
# =============================================================================

def test_real_ml_predictor_ground_truth_firewall(monkeypatch):
    """
    Verify that the Real ML predictor strictly enforces a zero-leakage firewall:
    Only text, report_id, and location_hint are passed to Aryan's InferenceEngine.analyze().
    No ground truth fields (expected_*, incident_group, relation_type, ground_truth, etc.)
    may ever cross the public boundary into the ML inference pipeline.
    """
    intercepted_calls = []

    class MockEngine:
        def analyze(self, report, report_id=None, location_hint=None, include_embedding=False):
            intercepted_calls.append({
                "report": report,
                "report_id": report_id,
                "location_hint": location_hint,
                "include_embedding": include_embedding,
            })
            return {
                "report_id": report_id,
                "incident_type": {"label": "FLOOD", "confidence": 0.95},
                "urgency": {"label": "CRITICAL", "confidence": 0.90},
                "people_at_risk": {"count": 2, "confidence": 0.85, "at_risk": True},
                "location": {
                    "text": location_hint.get("raw_text") if location_hint else None,
                    "latitude": location_hint.get("latitude") if location_hint else None,
                    "longitude": location_hint.get("longitude") if location_hint else None,
                    "precision": "approximate",
                    "confidence": 0.90,
                },
                "required_response": [{"type": "SEARCH_AND_RESCUE", "confidence": 0.95}],
                "model_version": "test-v1",
                "processing_status": "SUCCESS",
            }

    import ml.pipeline
    monkeypatch.setattr(ml.pipeline, "get_inference_engine", lambda: MockEngine())

    events = get_scenario("flood_rasulgarh")
    report = evaluate_real_ml(events=events)

    assert len(intercepted_calls) == len(events)
    assert report.total_samples == len(events)
    assert report.evaluation_mode == EvaluationMode.REAL_ML
    assert report.is_real_system_result is True

    forbidden_gt_keys = {
        "expected_incident_type",
        "expected_urgency",
        "expected_people_at_risk",
        "expected_people_count",
        "expected_required_response",
        "expected_actionable",
        "incident_group",
        "relation_type",
        "ground_truth",
        "is_hard_negative",
        "duplicate_of",
        "event_id",
    }

    for call in intercepted_calls:
        # Verify valid call payload types
        assert isinstance(call["report"], str)
        assert len(call["report"]) > 0
        assert isinstance(call["report_id"], str)
        assert call["report_id"].startswith("rep-")
        assert call["include_embedding"] is False

        # If location_hint is passed, it must only contain public dispatch location fields
        loc_hint = call["location_hint"]
        if loc_hint is not None:
            assert isinstance(loc_hint, dict)
            allowed_loc_keys = {"raw_text", "latitude", "longitude", "precision"}
            assert set(loc_hint.keys()).issubset(allowed_loc_keys)

        # Explicitly verify zero GT leakage in any call argument
        for k in forbidden_gt_keys:
            assert k not in call
            if isinstance(loc_hint, dict):
                assert k not in loc_hint


def test_real_ml_predictor_engine_reuse(monkeypatch):
    """
    Verify that get_inference_engine() is invoked exactly ONCE to instantiate a
    process-wide singleton, and engine.analyze() is reused across all dispatches.
    """
    engine_init_count = 0
    analyze_call_count = 0

    class MockEngine:
        def __init__(self):
            nonlocal engine_init_count
            engine_init_count += 1

        def analyze(self, report, report_id=None, location_hint=None, include_embedding=False):
            nonlocal analyze_call_count
            analyze_call_count += 1
            return {
                "report_id": report_id,
                "incident_type": {"label": "FLOOD", "confidence": 0.95},
                "urgency": {"label": "CRITICAL", "confidence": 0.90},
                "people_at_risk": {"count": 0, "confidence": 0.1, "at_risk": False},
                "location": {"text": "Test", "latitude": 20.0, "longitude": 85.0, "precision": "approximate"},
                "required_response": [],
                "model_version": "test-v1",
                "processing_status": "SUCCESS",
            }

    import ml.pipeline
    monkeypatch.setattr(ml.pipeline, "get_inference_engine", lambda: MockEngine())

    events = get_scenario("flood_rasulgarh")
    report = evaluate_real_ml(events=events)

    assert engine_init_count == 1
    assert analyze_call_count == len(events)
    assert report.total_samples == len(events)


def test_real_ml_evaluation_provenance(monkeypatch):
    """
    Verify report provenance integrity:
    - evaluate_real_ml produces evaluation_mode=REAL_ML, is_real_system_result=True,
      captures latency_profile, cold_latency_ms, warm_latency_profile, and model_version.
    - evaluate_ml_predictions produces evaluation_mode=HARNESS_SELF_TEST, is_real_system_result=False.
    """
    class MockEngine:
        def analyze(self, report, report_id=None, location_hint=None, include_embedding=False):
            return {
                "report_id": report_id,
                "incident_type": {"label": "FLOOD", "confidence": 0.95},
                "urgency": {"label": "CRITICAL", "confidence": 0.90},
                "people_at_risk": {"count": 1, "confidence": 0.9, "at_risk": True},
                "location": {"text": "Bhubaneswar", "latitude": 20.29, "longitude": 85.86, "precision": "approximate"},
                "required_response": [{"type": "FIRE", "confidence": 0.9}],
                "model_version": "real-ml-pipeline-v1.0",
                "processing_status": "SUCCESS",
            }

    import ml.pipeline
    monkeypatch.setattr(ml.pipeline, "get_inference_engine", lambda: MockEngine())

    events = get_scenario("flood_rasulgarh")[:3]

    # 1. Real ML benchmark evaluation
    real_report = evaluate_real_ml(events=events)
    assert real_report.evaluation_mode == EvaluationMode.REAL_ML
    assert real_report.is_real_system_result is True
    assert real_report.is_hermetic_mock is False
    assert real_report.model_version == "real-ml-pipeline-v1.0"
    assert real_report.status_counts == {"SUCCESS": 3}
    assert real_report.latency_profile is not None
    assert real_report.latency_profile.sample_count == 3
    assert len(real_report.latencies_ms) == 3
    assert real_report.cold_latency_ms is not None
    assert real_report.warm_latency_profile is not None
    assert real_report.warm_latency_profile.sample_count == 2
    assert real_report.warm_latency_profile.min_ms <= real_report.warm_latency_profile.mean_ms <= real_report.warm_latency_profile.max_ms

    # 2. Hermetic self-test baseline evaluation
    self_test_report = evaluate_ml_predictions(events=events)
    assert self_test_report.evaluation_mode == EvaluationMode.HARNESS_SELF_TEST
    assert self_test_report.is_real_system_result is False
    assert self_test_report.is_hermetic_mock is True


def test_real_ml_engine_failure_propagates_visibly(monkeypatch):
    """
    Verify that if get_inference_engine() fails (e.g. broken weights or missing runtime),
    evaluate_real_ml() raises the error visibly rather than silently falling back to mock fixtures.
    """
    import ml.pipeline
    def broken_engine():
        raise RuntimeError("ML model failed to initialize in test environment")

    monkeypatch.setattr(ml.pipeline, "get_inference_engine", broken_engine)

    events = get_scenario("flood_rasulgarh")[:2]
    with pytest.raises(RuntimeError, match="ML model failed to initialize"):
        evaluate_real_ml(events=events)


def test_real_ml_canonical_failed_status(monkeypatch):
    """
    Verify that if Aryan's pipeline returns processing_status="FAILED",
    the evaluator scores it legitimately as real output without crashing or substituting GT.
    """
    class FailingEngine:
        def analyze(self, report, report_id=None, location_hint=None, include_embedding=False):
            return {
                "report_id": report_id,
                "incident_type": {"label": "OTHER_GENERAL_INCIDENT", "confidence": 0.0},
                "urgency": {"label": "LOW", "confidence": 0.0},
                "people_at_risk": {"count": None, "confidence": 0.0, "at_risk": False},
                "location": {"text": None, "latitude": None, "longitude": None, "precision": "unknown"},
                "required_response": [],
                "model_version": "test-v1",
                "processing_status": "FAILED",
            }

    import ml.pipeline
    monkeypatch.setattr(ml.pipeline, "get_inference_engine", lambda: FailingEngine())

    events = get_scenario("flood_rasulgarh")[:2]
    report = evaluate_real_ml(events=events)

    assert report.evaluation_mode == EvaluationMode.REAL_ML
    assert report.is_real_system_result is True
    assert report.status_counts.get("FAILED") == 2
    assert report.total_samples == 2
