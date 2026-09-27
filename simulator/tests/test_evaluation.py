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
    CorrelationEvaluationMode,
    CorrelationEvaluationReport,
    build_real_correlation_stream_fn,
    evaluate_correlation_engine,
    evaluate_real_correlation,
    verify_embedding_contract,
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


# =============================================================================
# 7. Phase 3 — Real Correlation & Priority Integration Tests
# =============================================================================

def test_real_correlation_calls_daksh_functions(monkeypatch):
    """
    Verify that build_real_correlation_stream_fn calls Daksh's correlate_report_to_incident
    and calculate_priority with valid schema parameters and without falling back to ground truth.
    """
    import backend.app.engine.correlation as corr_mod
    import backend.app.engine.priority as prio_mod

    correlate_calls = []
    orig_correlate = corr_mod.correlate_report_to_incident
    def spy_correlate(*args, **kwargs):
        correlate_calls.append((args, kwargs))
        return orig_correlate(*args, **kwargs)
    monkeypatch.setattr(corr_mod, "correlate_report_to_incident", spy_correlate)

    priority_calls = []
    orig_prio = prio_mod.calculate_priority
    def spy_priority(*args, **kwargs):
        priority_calls.append((args, kwargs))
        return orig_prio(*args, **kwargs)
    monkeypatch.setattr(prio_mod, "calculate_priority", spy_priority)

    # Use a lightweight deterministic mock ML predictor so this unit test runs instantaneously
    dummy_vec = [0.1] * 384
    def dummy_ml(text, report_id=None, location_hint=None):
        return {
            "report_id": report_id,
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.9},
            "urgency": {"label": "HIGH", "confidence": 0.85},
            "people_at_risk": {"count": 2, "confidence": 0.8},
            "location": {"text": "Rasulgarh", "latitude": 20.2961, "longitude": 85.8245, "precision": "approximate"},
            "embedding": dummy_vec,
            "overall_confidence": 0.85,
        }

    stream_fn = build_real_correlation_stream_fn(ml_predictor=dummy_ml)
    events = get_scenario("flood_rasulgarh")[:3]

    outputs = [stream_fn(ev.public_payload()) for ev in events]

    assert len(outputs) == 3
    for out in outputs:
        assert "incident_id" in out
        assert "relationship" in out
        assert "priority_score" in out
        assert "priority_level" in out
        assert "explanation" in out
        assert isinstance(out["priority_score"], float)

    # First report spawns incident, second and third correlate against candidate
    assert len(priority_calls) == 3
    assert len(correlate_calls) >= 2


def test_real_correlation_ground_truth_isolation(monkeypatch):
    """
    Verify that zero ground truth tokens or expected_* keys leak into
    correlate_report_to_incident or calculate_priority.
    """
    import backend.app.engine.correlation as corr_mod

    observed_inputs = []
    orig_correlate = corr_mod.correlate_report_to_incident

    def spy_correlate(*args, **kwargs):
        observed_inputs.append(kwargs)
        return orig_correlate(*args, **kwargs)

    monkeypatch.setattr(corr_mod, "correlate_report_to_incident", spy_correlate)

    def dummy_ml(text, report_id=None, location_hint=None):
        return {
            "report_id": report_id,
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.9},
            "urgency": {"label": "HIGH", "confidence": 0.85},
            "people_at_risk": {"count": 1, "confidence": 0.8},
            "location": {"text": "Rasulgarh", "latitude": 20.2961, "longitude": 85.8245, "precision": "approximate"},
            "embedding": [0.05] * 384,
            "overall_confidence": 0.85,
        }

    stream_fn = build_real_correlation_stream_fn(ml_predictor=dummy_ml)
    events = get_scenario("flood_rasulgarh")[:3]

    for ev in events:
        stream_fn(ev.public_payload())

    forbidden_keys = {
        "incident_group",
        "relation_type",
        "expected_incident_type",
        "expected_urgency",
        "expected_people_at_risk",
        "expected_direction",
        "ground_truth",
        "gt",
    }
    for call_kw in observed_inputs:
        for k in call_kw:
            assert k not in forbidden_keys, f"Forbidden ground truth key '{k}' found in correlation call!"
            val_str = str(call_kw[k])
            assert "expected_" not in val_str.lower(), f"Ground truth token detected in correlation input: {val_str}"


def test_real_correlation_missing_embedding_fallback():
    """
    Verify that when ML inference provides embedding=None,
    correlation handles missing embedding gracefully via Daksh's reweighting logic
    without crashing, hallucinating vectors, or raising exceptions.
    """
    def dummy_ml_no_emb(text, report_id=None, location_hint=None):
        return {
            "report_id": report_id,
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.8},
            "urgency": {"label": "MEDIUM", "confidence": 0.75},
            "people_at_risk": {"count": None, "confidence": None},
            "location": {"text": "Rasulgarh", "latitude": 20.2961, "longitude": 85.8245, "precision": "approximate"},
            "embedding": None,  # Missing dense vector
            "overall_confidence": 0.75,
        }

    stream_fn = build_real_correlation_stream_fn(ml_predictor=dummy_ml_no_emb)
    events = get_scenario("flood_rasulgarh")[:3]

    outputs = [stream_fn(ev.public_payload()) for ev in events]
    assert len(outputs) == 3
    assert outputs[0]["relationship"] == "INITIAL"
    assert outputs[1]["priority_score"] >= 0.0


def test_real_correlation_provenance():
    """
    Verify that evaluate_real_correlation returns a report correctly tagged
    with is_real_system_result=True and evaluation_mode=REAL_CORRELATION.
    """
    def dummy_ml(text, report_id=None, location_hint=None):
        return {
            "report_id": report_id,
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.9},
            "urgency": {"label": "CRITICAL", "confidence": 0.95},
            "people_at_risk": {"count": 4, "confidence": 0.9},
            "location": {"text": "Rasulgarh", "latitude": 20.2961, "longitude": 85.8245, "precision": "approximate"},
            "embedding": [0.05] * 384,
            "overall_confidence": 0.9,
        }

    events = get_scenario("flood_rasulgarh")[:4]
    report = evaluate_real_correlation(events=events, ml_predictor=dummy_ml)

    assert report.is_real_system_result is True
    assert report.evaluation_mode == CorrelationEvaluationMode.REAL_CORRELATION
    assert report.total_reports_processed == 4
    assert report.latencies_ms is not None
    assert len(report.latencies_ms) == 4
    assert report.cold_latency_ms is not None
    assert report.warm_latency_profile is not None


def test_real_correlation_corroboration_and_duplicate_dynamics():
    """
    Verify that independent reports increase corroboration score while duplicate
    reports suppress priority score increases.
    """
    dummy_vec = [0.05] * 384
    def dummy_ml(text, report_id=None, location_hint=None):
        return {
            "report_id": report_id,
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.9},
            "urgency": {"label": "HIGH", "confidence": 0.85},
            "people_at_risk": {"count": 2, "confidence": 0.8},
            "location": {"text": "Rasulgarh underpass", "latitude": 20.2960, "longitude": 85.8245, "precision": "approximate"},
            "embedding": dummy_vec,
            "overall_confidence": 0.85,
        }

    stream_fn = build_real_correlation_stream_fn(ml_predictor=dummy_ml)

    # Initial report
    rep1 = {
        "report_id": "rep-001",
        "text": "Flood water underpass Rasulgarh trapped van",
        "reported_at": "2026-09-26T18:00:00Z",
        "location_hint": {"latitude": 20.2960, "longitude": 85.8245, "raw_text": "Rasulgarh underpass"},
        "metadata": {"caller_id": "caller-alice"},
    }
    out1 = stream_fn(rep1)
    assert out1["relationship"] == "INITIAL"
    score1 = out1["priority_score"]

    # Corroborating independent report (different caller, varied text)
    rep2 = {
        "report_id": "rep-002",
        "text": "Water rising quickly at Rasulgarh bridge, vehicle stuck inside",
        "reported_at": "2026-09-26T18:01:00Z",
        "location_hint": {"latitude": 20.2960, "longitude": 85.8245, "raw_text": "Rasulgarh underpass"},
        "metadata": {"caller_id": "caller-bob"},
    }
    out2 = stream_fn(rep2)
    assert out2["relationship"] == "CORROBORATING"
    score2 = out2["priority_score"]
    assert score2 > score1, "Corroboration from independent witness must increase priority score"

    # Duplicate verbatim report (same caller and verbatim text)
    rep3 = {
        "report_id": "rep-003",
        "text": "Flood water underpass Rasulgarh trapped van",
        "reported_at": "2026-09-26T18:02:00Z",
        "location_hint": {"latitude": 20.2960, "longitude": 85.8245, "raw_text": "Rasulgarh underpass"},
        "metadata": {"caller_id": "caller-alice"},
    }
    out3 = stream_fn(rep3)
    assert out3["relationship"] == "DUPLICATE"
    score3 = out3["priority_score"]
    assert score3 == score2, "Duplicate report must not increase priority score"


def test_predicted_cluster_labels_permutation_invariant():
    """
    Verify that arbitrary backend incident IDs are never compared directly as strings
    to ground truth incident group IDs, and that arbitrary label permutations
    yield identical pairwise precision, recall, F1, and Rand index.
    """
    true_groups = ["bbsr-flood-01", "bbsr-flood-01", "cuttack-fire-02", "cuttack-fire-02"]

    # Evaluator assigns arbitrary internal cluster IDs
    pred_groups_1 = ["inc-uuid-alpha", "inc-uuid-alpha", "inc-uuid-beta", "inc-uuid-beta"]
    pred_groups_2 = ["inc-999-permuted", "inc-999-permuted", "inc-111-permuted", "inc-111-permuted"]
    pred_groups_3 = ["totally-different-label", "totally-different-label", "another-arbitrary-id", "another-arbitrary-id"]

    r1 = compute_fusion_accuracy(true_groups, pred_groups_1)
    r2 = compute_fusion_accuracy(true_groups, pred_groups_2)
    r3 = compute_fusion_accuracy(true_groups, pred_groups_3)

    assert r1.pairwise_f1 == r2.pairwise_f1 == r3.pairwise_f1 == 1.0
    assert r1.pairwise_precision == r2.pairwise_precision == r3.pairwise_precision == 1.0
    assert r1.pairwise_recall == r2.pairwise_recall == r3.pairwise_recall == 1.0
    assert r1.rand_index == r2.rand_index == r3.rand_index == 1.0
    assert r1.true_positive_pairs == r2.true_positive_pairs == r3.true_positive_pairs == 2
    assert r1.false_positive_pairs == r2.false_positive_pairs == r3.false_positive_pairs == 0


def test_real_correlation_deterministic_repeatability():
    """
    Verify that executing the correlation stream twice on identical dispatches
    produces identical relationship decisions and priority scores.
    """
    dummy_vec = [0.08] * 384
    def dummy_ml(text, report_id=None, location_hint=None):
        return {
            "report_id": report_id,
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.9},
            "urgency": {"label": "HIGH", "confidence": 0.85},
            "people_at_risk": {"count": 3, "confidence": 0.8},
            "location": {"text": "Rasulgarh underpass", "latitude": 20.2960, "longitude": 85.8245, "precision": "approximate"},
            "embedding": dummy_vec,
            "overall_confidence": 0.85,
        }

    events = get_scenario("flood_rasulgarh")[:5]

    stream_1 = build_real_correlation_stream_fn(ml_predictor=dummy_ml)
    outputs_1 = [stream_1(ev.public_payload()) for ev in events]

    stream_2 = build_real_correlation_stream_fn(ml_predictor=dummy_ml)
    outputs_2 = [stream_2(ev.public_payload()) for ev in events]

    assert len(outputs_1) == len(outputs_2) == 5
    for o1, o2 in zip(outputs_1, outputs_2):
        assert o1["relationship"] == o2["relationship"]
        assert o1["priority_score"] == o2["priority_score"]
        assert o1["priority_level"] == o2["priority_level"]


# =============================================================================
# Phase 3.1 Correctness Verification & Audit Unit Tests
# =============================================================================

def test_critical_priority_threshold_semantics():
    """
    Verify that score 79.99 is strictly PriorityLevel.HIGH and NOT CRITICAL,
    while score 80.0 is PriorityLevel.CRITICAL.
    Evaluator incident_critical_recall must require score >= 80.0 (backend threshold).
    """
    from backend.app.engine.priority import map_priority_level
    from backend.app.schemas.common import PriorityLevel

    # Backend level mapping verification
    assert map_priority_level(79.99) == PriorityLevel.HIGH
    assert map_priority_level(80.0) == PriorityLevel.CRITICAL
    assert map_priority_level(75.0) == PriorityLevel.HIGH
    assert map_priority_level(85.0) == PriorityLevel.CRITICAL

    # Use flood scenario event with expected_urgency = CRITICAL (evt-flood-004)
    event_crit = get_scenario("flood_rasulgarh")[3]

    # Sub-critical score 79.99: must NOT count as CRITICAL
    mock_sub_crit = [{"event_id": event_crit.event_id, "priority_score": 79.99, "incident_id": "inc-001"}]
    rep_sub = evaluate_correlation_engine(
        events=[event_crit],
        mock_correlation_outputs=mock_sub_crit,
        critical_threshold=80.0,
    )
    assert rep_sub.incident_critical_recall == 0.0, "Score 79.99 must yield critical recall 0.0"
    assert rep_sub.priority_score_ge_75_recall == 1.0, "Score 79.99 is >= 75.0"

    # Critical score 80.0: must count as CRITICAL
    mock_crit = [{"event_id": event_crit.event_id, "priority_score": 80.0, "incident_id": "inc-001"}]
    rep_crit = evaluate_correlation_engine(
        events=[event_crit],
        mock_correlation_outputs=mock_crit,
        critical_threshold=80.0,
    )
    assert rep_crit.incident_critical_recall == 1.0, "Score 80.0 must yield critical recall 1.0"
    assert rep_crit.priority_score_ge_75_recall == 1.0


def test_none_noise_groups_do_not_collapse_into_single_cluster():
    """
    Verify that reports with incident_group = None (NOISE / hard negatives)
    are treated as distinct singletons and NEVER grouped together as a false positive pair.
    Specifically: true groups [None, None, 'A', 'A'] must have exactly 1 true positive pair ('A'-'A'),
    NOT 2 positive pairs.
    """
    evs = get_scenario("flood_rasulgarh")
    # evs[13] and evs[14] have incident_group=None (NOISE)
    # evs[0] and evs[1] have incident_group="bbsr-flood-rasulgarh-01"
    events = [evs[13], evs[14], evs[0], evs[1]]

    # Perfect prediction: noise events each get unique unclustered ID, emergency gets shared ID
    mock_perfect = [
        {"event_id": evs[13].event_id, "incident_id": "inc-unclustered-1"},
        {"event_id": evs[14].event_id, "incident_id": "inc-unclustered-2"},
        {"event_id": evs[0].event_id, "incident_id": "inc-fused-A"},
        {"event_id": evs[1].event_id, "incident_id": "inc-fused-A"},
    ]

    rep = evaluate_correlation_engine(events=events, mock_correlation_outputs=mock_perfect)
    fa = rep.fusion_accuracy

    # Exactly 1 true positive pair (evs[0] with evs[1])
    # Total pairs = 4 * 3 / 2 = 6
    # Negative pairs = 6 - 1 = 5
    assert fa.true_positive_pairs == 1, f"Expected 1 TP pair, got {fa.true_positive_pairs}"
    assert fa.false_positive_pairs == 0
    assert fa.false_negative_pairs == 0
    assert fa.true_negative_pairs == 5
    assert fa.pairwise_precision == 1.0
    assert fa.pairwise_recall == 1.0
    assert fa.pairwise_f1 == 1.0
    assert fa.rand_index == 1.0


def test_source_id_parity_with_backend_ingestion(monkeypatch):
    """
    Verify that build_real_correlation_stream_fn extracts report_source_id
    with exact parity to Daksh's backend ingestion.py precedence:
    caller_id -> source_id -> payload.source.

    Explicitly verifies Cases A, B, C, D:
    - Case A: caller_id takes precedence over source_id, reporter_id, phone, and source.
    - Case B: source_id takes precedence over reporter_id, phone, and source when caller_id is absent.
    - Case C: reporter_id and phone in metadata are strictly ignored; fallback is payload.source.
    - Case D: empty metadata falls back to payload.source.
    """
    import backend.app.engine.correlation as corr_mod

    observed_calls = []
    orig_correlate = corr_mod.correlate_report_to_incident

    def spy_correlate(*args, **kwargs):
        observed_calls.append(kwargs)
        return orig_correlate(*args, **kwargs)

    monkeypatch.setattr(corr_mod, "correlate_report_to_incident", spy_correlate)

    dummy_vec = [0.05] * 384
    def dummy_ml(text, report_id=None, location_hint=None):
        return {
            "report_id": report_id,
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.8},
            "urgency": {"label": "HIGH", "confidence": 0.8},
            "people_at_risk": {"count": 1, "confidence": 0.8},
            "location": {"text": "Test", "latitude": 20.0, "longitude": 85.0, "precision": "exact"},
            "embedding": dummy_vec,
            "overall_confidence": 0.8,
        }

    s = build_real_correlation_stream_fn(ml_predictor=dummy_ml)
    # Seed initial candidate
    s({
        "report_id": "seed",
        "text": "Initial seed report",
        "source": "SEED_SRC",
        "metadata": {"caller_id": "seed_caller"},
    })

    # Case A: caller_id takes precedence over source_id, reporter_id, phone, source
    s({
        "report_id": "case_a",
        "text": "Case A report",
        "source": "SIM_SOURCE",
        "metadata": {
            "caller_id": "caller_alpha",
            "source_id": "source_beta",
            "reporter_id": "reporter_gamma",
            "phone": "+1234567890",
        },
    })
    assert observed_calls[-1]["report_source_id"] == "caller_alpha"

    # Case B: source_id takes precedence over reporter_id, phone, source when caller_id is absent
    s({
        "report_id": "case_b",
        "text": "Case B report",
        "source": "SIM_SOURCE",
        "metadata": {
            "source_id": "source_beta",
            "reporter_id": "reporter_gamma",
            "phone": "+1234567890",
        },
    })
    assert observed_calls[-1]["report_source_id"] == "source_beta"

    # Case C: reporter_id and phone in metadata are strictly ignored; fallback is payload.source
    s({
        "report_id": "case_c",
        "text": "Case C report",
        "source": "SIM_FALLBACK_SRC",
        "metadata": {
            "reporter_id": "reporter_gamma",
            "phone": "+1234567890",
        },
    })
    assert observed_calls[-1]["report_source_id"] == "SIM_FALLBACK_SRC"

    # Case D: empty metadata falls back to payload.source
    s({
        "report_id": "case_d",
        "text": "Case D report",
        "source": "SIM_FALLBACK_SRC_2",
        "metadata": {},
    })
    assert observed_calls[-1]["report_source_id"] == "SIM_FALLBACK_SRC_2"


def test_embedding_contract_verification():
    """
    Verify embedding contract validation:
    - 384-dimensional normalized vector passes with all_valid=True
    - Missing / None is recorded in missing
    - Wrong dimensions (e.g. 512, 100) recorded in wrong_dimension
    - Non-finite (NaN, Inf) recorded in non_finite
    """
    import math

    valid_norm_1 = [1.0 / math.sqrt(384)] * 384
    valid_res = verify_embedding_contract([valid_norm_1, valid_norm_1])
    assert valid_res["all_valid"] is True
    assert valid_res["available"] == 2
    assert valid_res["missing"] == 0
    assert valid_res["wrong_dimension"] == 0
    assert valid_res["non_finite"] == 0
    assert 0.999 <= valid_res["norm_mean"] <= 1.001

    mixed_embeddings = [
        valid_norm_1,
        None,                        # missing
        [0.1] * 128,                 # wrong dimension
        [float("nan")] + [0.1] * 383, # non-finite
        [float("inf")] + [0.1] * 383, # non-finite
    ]
    mixed_res = verify_embedding_contract(mixed_embeddings)
    assert mixed_res["all_valid"] is False
    assert mixed_res["total"] == 5
    assert mixed_res["available"] == 1
    assert mixed_res["missing"] == 1
    assert mixed_res["wrong_dimension"] == 1
    assert mixed_res["non_finite"] == 2


def test_execution_scope_provenance():
    """
    Verify execution scope provenance:
    - REAL_CORRELATION has execution_scope = "IN_PROCESS_ENGINE_REPLAY"
    - HARNESS_SELF_TEST has execution_scope = "HARNESS_SELF_TEST"
    - is_real_system_result is correctly populated
    """
    dummy_vec = [0.05] * 384
    def dummy_ml(text, report_id=None, location_hint=None):
        return {
            "report_id": report_id,
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.8},
            "urgency": {"label": "HIGH", "confidence": 0.8},
            "people_at_risk": {"count": 1, "confidence": 0.8},
            "location": {"text": "Test", "latitude": 20.0, "longitude": 85.0, "precision": "exact"},
            "embedding": dummy_vec,
            "overall_confidence": 0.8,
        }

    events = get_scenario("flood_rasulgarh")[:3]

    # Real correlation run
    real_rep = evaluate_real_correlation(events=events, ml_predictor=dummy_ml)
    assert real_rep.evaluation_mode == CorrelationEvaluationMode.REAL_CORRELATION
    assert real_rep.execution_scope == "IN_PROCESS_ENGINE_REPLAY"
    assert real_rep.is_real_system_result is True
    assert real_rep.to_dict()["execution_scope"] == "IN_PROCESS_ENGINE_REPLAY"

    # Self-test run
    self_rep = evaluate_correlation_engine(events=events)
    assert self_rep.evaluation_mode == CorrelationEvaluationMode.HARNESS_SELF_TEST
    assert self_rep.execution_scope == "HARNESS_SELF_TEST"
    assert self_rep.is_real_system_result is False


def test_ranking_insufficient_sample_not_evaluated():
    """
    Verify that when the evaluation scenario has fewer than 2 distinct multi-report
    incidents, ranking cannot be meaningfully evaluated.
    meaningful_ranking_sample must be False, and spearman_rank_correlation must be None.
    """
    # Single incident with multiple reports
    events = get_scenario("flood_rasulgarh")[:3]

    rep = evaluate_correlation_engine(events=events)
    assert rep.meaningful_ranking_sample is False
    assert rep.spearman_rank_correlation is None
    d = rep.to_dict()
    assert d["meaningful_ranking_sample"] is False
    assert d["spearman_rank_correlation"] is None


# =============================================================================
# 11. Phase 5 E2E & WebSocket Benchmark Collector Tests
# =============================================================================

def test_websocket_frame_canonical_envelope():
    """
    Verify WebSocket envelope parsing:
    Canonical frame must have event, payload, and timestamp.
    """
    from evaluation.collector import WebSocketCapture

    capture = WebSocketCapture()

    # 1. Canonical valid frame
    valid_raw = json.dumps({
        "event": "INCIDENT_CREATED",
        "payload": {"incident_id": "inc-001", "priority_score": 85.0},
        "timestamp": "2026-09-27T06:00:00Z",
    })
    capture._process_frame(valid_raw, t_recv=100.0)

    # 2. Malformed non-canonical frame (missing timestamp)
    non_canonical = json.dumps({
        "event": "INCIDENT_UPDATED",
        "payload": {"incident_id": "inc-001"},
    })
    capture._process_frame(non_canonical, t_recv=101.0)

    # 3. Non-JSON raw text
    capture._process_frame("NOT_A_JSON_STRING", t_recv=102.0)

    frames = capture.get_frames()
    assert len(frames) == 3

    assert frames[0].event == "INCIDENT_CREATED"
    assert frames[0].is_valid_envelope is True
    assert frames[0].payload["incident_id"] == "inc-001"

    assert frames[1].event == "INCIDENT_UPDATED"
    assert frames[1].is_valid_envelope is False

    assert frames[2].event == "MALFORMED_NON_JSON"
    assert frames[2].is_valid_envelope is False

    counts = capture.event_counts()
    assert counts["INCIDENT_CREATED"] == 1
    assert counts["INCIDENT_UPDATED"] == 1
    assert counts["MALFORMED_NON_JSON"] == 1


def test_database_collector_mock_counts(monkeypatch):
    """
    Verify DatabaseCollector properly aggregates run-scoped counts.
    """
    from evaluation.collector import DatabaseCollector

    db = DatabaseCollector(db_name="test_db")

    def mock_query_json(sql: str):
        if "priority_calculations" in sql:
            return [{"cnt": 27}]
        if "raw_reports" in sql:
            return [{"cnt": 27}]
        if "ml_predictions" in sql:
            return [{"cnt": 27}]
        if "incident_reports" in sql and "DISTINCT incident_id" in sql:
            return [{"cnt": 12}]
        if "incident_reports" in sql:
            return [{"cnt": 27}]
        return []

    monkeypatch.setattr(db, "query_json", mock_query_json)

    counts = db.get_run_counts("test-run")
    assert counts["raw_reports"] == 27
    assert counts["ml_predictions"] == 27
    assert counts["incident_reports"] == 27
    assert counts["incidents"] == 12
    assert counts["priority_calculations"] == 27


def test_e2e_evaluation_report_serialization():
    """
    Verify E2EEvaluationReport serialization preserves required contract fields.
    """
    from evaluation.collector import E2EEvaluationReport
    from evaluation.metrics import FusionAccuracyReport, LatencyProfile

    fusion = FusionAccuracyReport(
        pairwise_precision=0.75,
        pairwise_recall=1.0,
        pairwise_f1=0.8571,
        rand_index=0.92,
        true_positive_pairs=78,
        false_positive_pairs=26,
        false_negative_pairs=0,
        true_negative_pairs=247,
        total_pairs=351,
    )
    lat_prof = LatencyProfile(
        p50_ms=50.0,
        p90_ms=58.0,
        p95_ms=67.0,
        p99_ms=110.0,
        mean_ms=53.0,
        min_ms=44.0,
        max_ms=110.0,
        sample_count=26,
        is_measured=True,
    )

    report = E2EEvaluationReport(
        run_id="test-run-001",
        total_reports_attempted=27,
        total_reports_successful=27,
        http_errors_4xx=0,
        http_errors_5xx=0,
        http_timeouts=0,
        transport_retries=0,
        transport_buffered=0,
        circuit_breaker_tripped=False,
        http_cold_latency_ms=1500.0,
        http_warm_latency_profile=lat_prof,
        db_raw_reports_count=27,
        db_ml_predictions_count=27,
        db_incident_links_count=27,
        db_incidents_count=12,
        db_priority_calculations_count=27,
        orphan_links_count=0,
        synthetic_partition_violations=0,
        websocket_connected=True,
        websocket_total_frames=27,
        websocket_malformed_frames=0,
        websocket_event_counts={"INCIDENT_CREATED": 12, "INCIDENT_UPDATED": 15},
        websocket_unknown_incident_ids=[],
        pairwise_fusion_accuracy=fusion,
        duplicate_metrics={"tp": 2, "fp": 10, "fn": 0, "tn": 15, "precision": 0.1667, "recall": 1.0, "f1": 0.2858},
        corroborating_metrics={"tp": 3, "fp": 0, "fn": 4, "tn": 20, "precision": 1.0, "recall": 0.4286, "f1": 0.6},
        incident_critical_recall=1.0,
        priority_score_ge_75_recall=1.0,
        scenario_rank_1_status="PASS",
        scenario_rank_1_passed=True,
        rank_1_tie_detected=False,
        meaningful_ranking_sample=False,
        spearman_rank_correlation=None,
        diagnostic_spearman_rho=0.3336,
        ml_type_macro_f1=0.5343,
        ml_urgency_accuracy=0.5926,
        ml_casualty_mae=0.0,
        ml_location_precision_accuracy=0.9259,
    )

    d = report.to_dict()
    assert d["evaluation_mode"] == "REAL_E2E"
    assert d["is_real_system_result"] is True
    assert d["execution_scope"] == "LIVE_HTTP_POSTGRES_WEBSOCKET"
    assert d["total_reports_attempted"] == 27
    assert d["total_reports_successful"] == 27
    assert d["db_raw_reports_count"] == 27
    assert d["db_incidents_count"] == 12
    assert d["scenario_rank_1_status"] == "PASS"
    assert d["websocket_connected"] is True


def test_ground_truth_singleton_handling_and_pairwise_clustering():
    """
    Verify that unclustered ground-truth reports (incident_group is None)
    are treated as distinct singletons, preventing false ground-truth merging.
    """
    from evaluation.metrics import compute_fusion_accuracy

    # 3 reports: 2 in true cluster "flood", 1 noise with None
    # If noise is properly treated as a unique singleton:
    true_groups = ["flood", "flood", "singleton-noise-01"]
    # Suppose system merged all 3 into one cluster "inc-1"
    pred_groups = ["inc-1", "inc-1", "inc-1"]

    rep = compute_fusion_accuracy(true_groups, pred_groups)
    # Pairs: (0,1)=same true, same pred -> TP
    # (0,2)=diff true, same pred -> FP
    # (1,2)=diff true, same pred -> FP
    assert rep.true_positive_pairs == 1
    assert rep.false_positive_pairs == 2
    assert rep.false_negative_pairs == 0
    assert rep.true_negative_pairs == 0
    assert rep.pairwise_recall == 1.0
    assert rep.pairwise_precision == 1.0 / 3.0


def test_websocket_capture_event_breakdown_and_filtering():
    """
    Verify WebSocketCapture handles all standard Karen event types:
    INCIDENT_CREATED, INCIDENT_UPDATED, INCIDENT_STATUS_CHANGED, SIMULATION_PULSE, PING.
    """
    from evaluation.collector import WebSocketCapture

    capture = WebSocketCapture()
    events_to_test = [
        "INCIDENT_CREATED",
        "INCIDENT_UPDATED",
        "INCIDENT_STATUS_CHANGED",
        "SIMULATION_PULSE",
        "PING",
    ]
    for ev in events_to_test:
        raw = json.dumps({"event": ev, "payload": {}, "timestamp": "2026-09-27T06:00:00Z"})
        capture._process_frame(raw, t_recv=100.0)

    counts = capture.event_counts()
    for ev in events_to_test:
        assert counts.get(ev) == 1


# =============================================================================
# 12. Phase 6 Surge & Resilience Hermetic Tests
# =============================================================================

def test_generate_surge_events_contract():
    """
    Verify generate_surge_events produces valid ScenarioEvents adhering to
    strict safety contracts: is_synthetic=True, source='simulator', zero GT leakage.
    """
    from evaluation.evaluate_resilience import generate_surge_events
    from simulator.models import verify_no_ground_truth_leakage

    events = generate_surge_events(run_id="test-p6", count=20)
    assert len(events) == 20

    seen_ids = set()
    for ev in events:
        assert ev.dispatch.report_id.startswith("test-p6-rep-")
        assert ev.dispatch.is_synthetic is True
        assert ev.dispatch.source == "simulator"
        assert len(ev.dispatch.text) >= 3
        assert ev.dispatch.location_hint is not None

        # Verify zero ground-truth leakage in public payload
        pub = ev.public_payload()
        verify_no_ground_truth_leakage(pub)
        assert "ground_truth" not in pub

        seen_ids.add(ev.dispatch.report_id)

    assert len(seen_ids) == 20


def test_controlled_429_hermetic():
    """
    Verify execute_controlled_429_test runs hermetically and confirms
    Retry-After backoff and eventual success.
    """
    from evaluation.evaluate_resilience import execute_controlled_429_test

    res = execute_controlled_429_test()
    assert res["call_count"] == 2
    assert res["final_status_code"] == 201
    assert res["success"] is True
    assert res["retries"] == 1
    assert res["buffered"] is False


def test_controlled_5xx_hermetic():
    """
    Verify execute_controlled_5xx_test runs hermetically and verifies both
    transient retry recovery and exhausted retry buffering.
    """
    from evaluation.evaluate_resilience import execute_controlled_5xx_test

    res = execute_controlled_5xx_test()
    assert res["transient_calls"] == 3
    assert res["transient_success"] is True
    assert res["transient_retries"] == 2
    assert res["exhausted_calls"] == 3
    assert res["exhausted_success"] is False
    assert res["exhausted_retries"] == 2
    assert res["exhausted_buffered"] is True
    assert res["buffer_size_after_exhaustion"] == 1


def test_circuit_breaker_hermetic():
    """
    Verify execute_circuit_breaker_test exercises exact state machine transitions:
    CLOSED -> OPEN -> HALF_OPEN -> CLOSED and HALF_OPEN -> OPEN.
    """
    from evaluation.evaluate_resilience import execute_circuit_breaker_test

    res = execute_circuit_breaker_test()
    assert res["state_after_4_failures"] == "CLOSED"
    assert res["state_after_5_failures"] == "OPEN"
    assert res["can_attempt_while_open"] is False
    assert res["state_after_timeout"] == "HALF_OPEN"
    assert res["probe_permitted"] is True
    assert res["probe_second_throttled"] is True
    assert res["state_after_probe_1"] == "HALF_OPEN"
    assert res["state_after_probe_2"] == "CLOSED"
    assert res["state_after_half_open_failure"] == "OPEN"


def test_fifo_buffer_order_hermetic():
    """
    Verify execute_fifo_buffer_test verifies zero data loss and exact FIFO order preservation.
    """
    from evaluation.evaluate_resilience import execute_fifo_buffer_test

    res = execute_fifo_buffer_test()
    assert res["order_preserved"] is True
    assert res["buffer_size_before"] == 4
    assert res["buffer_size_after"] == 0
    assert res["flush_all_succeeded"] is True


def test_buffer_capacity_overflow_hermetic():
    """
    Verify execute_buffer_capacity_test raises BufferOverflowError at capacity + 1.
    """
    from evaluation.evaluate_resilience import execute_buffer_capacity_test

    res = execute_buffer_capacity_test()
    assert res["configured_capacity"] == 5
    assert res["size_at_cap_minus_1"] == 4
    assert res["size_at_capacity"] == 5
    assert res["overflow_raised"] is True
    assert res["policy"] == "reject_and_raise_BufferOverflowError"
