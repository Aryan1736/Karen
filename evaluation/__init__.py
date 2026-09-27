"""
Karen's Ear — Canonical Evaluation & Benchmark Package.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md, docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened Evaluation Package
"""

from evaluation.metrics import (
    ClassMetric,
    ClassificationReport,
    CoverageReport,
    DualCriticalRecall,
    FusionAccuracyReport,
    LatencyProfile,
    LocationEvaluationReport,
    MultilabelReport,
    PeopleAtRiskEvaluationReport,
    UrgencyAlignmentReport,
    compute_classification_report,
    compute_coverage_report,
    compute_dual_critical_recall,
    compute_fusion_accuracy,
    compute_latency_profile,
    compute_location_metrics,
    compute_multilabel_response_metrics,
    compute_people_at_risk_metrics,
    compute_spearman_rho,
    compute_urgency_alignment,
)
from evaluation.evaluate_ml import (
    EvaluationMode,
    LocationEvalMode,
    MLEvaluationReport,
    MLPredictionAdapter,
    NormalizedMLPrediction,
    build_real_ml_predictor,
    evaluate_ml_predictions,
    evaluate_real_ml,
)
from evaluation.evaluate_correlation import (
    AssertionResult,
    CandidateIncident,
    CorrelationEvaluationMode,
    CorrelationEvaluationReport,
    build_real_correlation_stream_fn,
    evaluate_correlation_engine,
    evaluate_real_correlation,
    verify_embedding_contract,
)
from evaluation.collector import (
    CapturedWebSocketFrame,
    DatabaseCollector,
    E2EEvaluationReport,
    WebSocketCapture,
    run_full_e2e_benchmark,
)
from evaluation.evaluate_resilience import (
    LiveSurgeReport,
    execute_buffer_capacity_test,
    execute_circuit_breaker_test,
    execute_controlled_422_test,
    execute_controlled_429_test,
    execute_controlled_5xx_test,
    execute_fifo_buffer_test,
    execute_idempotency_test,
    execute_live_interruption_test,
    execute_live_surge,
    generate_surge_events,
)
from evaluation.final_scorecard import (
    ClusteringEvaluationMetrics,
    DirectMLMetrics,
    LatencyProfileSummary,
    LiveReliabilityMetrics,
    PersistedE2EMLMetrics,
    PriorityTriageMetrics,
    RealSystemScorecard,
    RelationshipClassificationMetrics,
    ResilienceFaultMetrics,
    build_final_scorecard,
)
from typing import Any


def __getattr__(name: str) -> Any:
    if name in ("generate_markdown_scorecard", "run_full_benchmark"):
        from evaluation import run_all_evals
        return getattr(run_all_evals, name)
    raise AttributeError(f"module 'evaluation' has no attribute '{name}'")


__all__ = [
    "AssertionResult",
    "CandidateIncident",
    "ClassMetric",
    "ClassificationReport",
    "CorrelationEvaluationMode",
    "CorrelationEvaluationReport",
    "CoverageReport",
    "DualCriticalRecall",
    "EvaluationMode",
    "FusionAccuracyReport",
    "LatencyProfile",
    "LocationEvalMode",
    "LocationEvaluationReport",
    "MLEvaluationReport",
    "MLPredictionAdapter",
    "MultilabelReport",
    "NormalizedMLPrediction",
    "PeopleAtRiskEvaluationReport",
    "UrgencyAlignmentReport",
    "build_real_correlation_stream_fn",
    "build_real_ml_predictor",
    "evaluate_real_correlation",
    "evaluate_real_ml",
    "compute_classification_report",
    "compute_coverage_report",
    "compute_dual_critical_recall",
    "compute_fusion_accuracy",
    "compute_latency_profile",
    "compute_location_metrics",
    "compute_multilabel_response_metrics",
    "compute_people_at_risk_metrics",
    "compute_spearman_rho",
    "compute_urgency_alignment",
    "evaluate_correlation_engine",
    "evaluate_ml_predictions",
    "generate_markdown_scorecard",
    "run_full_benchmark",
    "verify_embedding_contract",
    "ClusteringEvaluationMetrics",
    "DirectMLMetrics",
    "LatencyProfileSummary",
    "LiveReliabilityMetrics",
    "PersistedE2EMLMetrics",
    "PriorityTriageMetrics",
    "RealSystemScorecard",
    "RelationshipClassificationMetrics",
    "ResilienceFaultMetrics",
    "build_final_scorecard",
]
