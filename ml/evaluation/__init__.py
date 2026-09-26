"""
Karen's Ear — Machine Learning Evaluation Package.

Feature 11 — Quantitative Evaluation Layer.
Provides reproducible quantitative evaluation harness for the existing ML pipeline:
- Classification metrics & confusion matrix across 9 canonical incident categories
- Entity extraction metrics & explicit matching methodologies (location spans, joint, span-only)
- Urgency engine evaluation (4x4 confusion matrix, critical recall, critical false-negative rate)
- Semantic embedding evaluation (ROC-AUC, precision/recall @ configurable threshold)
- Performance and resource profiling (cold-start, warm latency p50/p95, memory RSS via psutil)
- Machine-readable JSON report and human-readable summary output
"""

from __future__ import annotations

from ml.evaluation.classification_evaluator import (
    ClassificationClassMetrics,
    ClassificationEvaluationResult,
    ClassificationEvaluator,
)
from ml.evaluation.embedding_evaluator import (
    EmbeddingEvaluationResult,
    EmbeddingEvaluator,
    EmbeddingThresholdMetrics,
)
from ml.evaluation.entity_evaluator import (
    EntityEvaluationResult,
    EntityEvaluator,
    SpanMetrics,
    normalize_span,
)
from ml.evaluation.urgency_evaluator import (
    UrgencyEvaluationResult,
    UrgencyEvaluator,
    UrgencyTierMetrics,
)
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
from ml.evaluation.performance_evaluator import (
    ColdStartMemoryMetrics,
    ColdStartMetrics,
    EnvironmentMetadata,
    LatencyDistribution,
    MemoryUsageMetrics,
    PerformanceEvaluationResult,
    PerformanceEvaluator,
)
from ml.evaluation.report import (
    EvaluationReport,
    Finding,
    MLEvaluationHarness,
)

__all__ = [
    # Metrics
    "calculate_precision",
    "calculate_recall",
    "calculate_f1",
    "calculate_f1_from_counts",
    "calculate_accuracy",
    "compute_confusion_matrix",
    "calculate_per_class_metrics",
    "calculate_macro_metrics",
    "calculate_critical_recall",
    "calculate_critical_false_negative_rate",
    "calculate_roc_curve",
    "calculate_roc_auc",
    "calculate_binary_metrics_at_threshold",
    "calculate_percentiles",
    "normalize_span",
    # Evaluators & Results
    "ClassificationEvaluator",
    "ClassificationEvaluationResult",
    "ClassificationClassMetrics",
    "EntityEvaluator",
    "EntityEvaluationResult",
    "SpanMetrics",
    "UrgencyEvaluator",
    "UrgencyEvaluationResult",
    "EmbeddingEvaluator",
    "EmbeddingEvaluationResult",
    "EmbeddingThresholdMetrics",
    "PerformanceEvaluator",
    "PerformanceEvaluationResult",
    "ColdStartMetrics",
    "ColdStartMemoryMetrics",
    "LatencyDistribution",
    "MemoryUsageMetrics",
    "EnvironmentMetadata",
    # Orchestration & Report
    "MLEvaluationHarness",
    "EvaluationReport",
    "Finding",
]
