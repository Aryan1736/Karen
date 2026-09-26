"""
Karen's Ear — Confidence Calibration & Quality Control Subpackage.

Step 4 of the ML pipeline (architecture/ml-pipeline.md Section 4).
Responsible for:
- Computing overall model confidence from component scores via weighted harmonic mean
- Evaluating quality thresholds (confidence < 0.60 flag)
- Deterministically resolving operational status (SUCCESS, PARTIAL, FAILED, NEEDS_REVIEW)
- Routing uncertain, contradictory, or degraded inferences to human operator review
"""

from ml.confidence.confidence_engine import (
    ComponentConfidenceDetail,
    ConfidenceEngine,
    ConfidenceResult,
    calculate_confidence,
    validate_confidence_value,
)
from ml.confidence.evaluator import (
    ConfidenceEvaluationReport,
    ConfidenceEvaluator,
    run_confidence_evaluation,
)
from ml.config import DEFAULT_CONFIDENCE_WEIGHTS

__all__ = [
    "ConfidenceEngine",
    "ConfidenceResult",
    "ComponentConfidenceDetail",
    "calculate_confidence",
    "validate_confidence_value",
    "DEFAULT_CONFIDENCE_WEIGHTS",
    "ConfidenceEvaluator",
    "ConfidenceEvaluationReport",
    "run_confidence_evaluation",
]
