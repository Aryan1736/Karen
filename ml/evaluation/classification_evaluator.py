"""
Karen's Ear — Classification Evaluation Module.

Feature 11 — Quantitative Evaluation Layer.
Evaluates the Incident Classification component via the canonical public
inference pipeline entry point:
    from ml.pipeline import inference_engine
    result = inference_engine.analyze(report_text)

Evaluates performance across all 9 canonical incident classes using
the 63-sample curated engineering benchmark (INCIDENT_BENCHMARK_DATASET).
Preserves all class names without collapsing into binary tasks.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from ml.config import CANONICAL_INCIDENT_TYPES
from ml.evaluation.metrics import (
    calculate_accuracy,
    calculate_macro_metrics,
    calculate_per_class_metrics,
    compute_confusion_matrix,
)
from ml.pipeline import inference_engine
from ml.pipeline.inference_engine import InferenceEngine
from ml.tests.fixtures.incident_benchmark import INCIDENT_BENCHMARK_DATASET, BenchmarkItem


@dataclass
class ClassificationClassMetrics:
    """Metrics for an individual incident category."""

    label: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    support: int = 0


@dataclass
class ClassificationEvaluationResult:
    """Quantitative results from evaluating incident classification."""

    fixture_name: str
    sample_count: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_class: dict[str, ClassificationClassMetrics]
    confusion_matrix: dict[str, dict[str, int]]
    canonical_labels: list[str]
    elapsed_seconds: float
    misclassifications: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converts results to a JSON-serializable dictionary."""
        return {
            "fixture_name": self.fixture_name,
            "sample_count": self.sample_count,
            "accuracy": self.accuracy,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "canonical_labels": self.canonical_labels,
            "per_class": {k: asdict(v) for k, v in self.per_class.items()},
            "confusion_matrix": self.confusion_matrix,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "misclassifications": self.misclassifications,
        }


class ClassificationEvaluator:
    """
    Evaluator for incident classification via the unified inference pipeline.
    Measures precision, recall, F1, and confusion matrix across canonical classes.
    """

    def __init__(
        self,
        engine: InferenceEngine | None = None,
        canonical_classes: Sequence[str] = CANONICAL_INCIDENT_TYPES,
    ) -> None:
        self.engine = engine or inference_engine
        self.canonical_classes = list(canonical_classes)

    def evaluate(
        self,
        dataset: Sequence[BenchmarkItem] = INCIDENT_BENCHMARK_DATASET,
        fixture_name: str = "INCIDENT_BENCHMARK_DATASET",
    ) -> ClassificationEvaluationResult:
        """
        Executes classification evaluation across all items in the benchmark dataset.
        Consumes the unified inference pipeline via engine.analyze().
        """
        if not dataset:
            raise ValueError("Evaluation dataset cannot be empty")

        y_true: list[str] = []
        y_pred: list[str] = []
        misclassifications: list[dict[str, Any]] = []

        t_start = time.perf_counter()

        for item in dataset:
            true_label = item.expected_label
            # Call unified public inference entry point
            res = self.engine.analyze(item.text, report_id=item.id)
            pred_info = res.get("incident_type", {})
            pred_label = pred_info.get("label") or "OTHER_GENERAL_INCIDENT"
            confidence = pred_info.get("confidence")

            y_true.append(true_label)
            y_pred.append(pred_label)

            if pred_label != true_label:
                misclassifications.append({
                    "id": item.id,
                    "expected": true_label,
                    "predicted": pred_label,
                    "confidence": confidence,
                    "text_snippet": item.text[:80] + ("..." if len(item.text) > 80 else ""),
                })

        elapsed = time.perf_counter() - t_start

        # Calculate confusion matrix & per-class metrics
        matrix = compute_confusion_matrix(y_true, y_pred, self.canonical_classes)
        per_class_raw = calculate_per_class_metrics(matrix, self.canonical_classes)
        macro = calculate_macro_metrics(per_class_raw, only_supported=True)

        correct_count = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
        acc = calculate_accuracy(correct_count, len(y_true))

        per_class_objs: dict[str, ClassificationClassMetrics] = {
            label: ClassificationClassMetrics(
                label=label,
                tp=data["tp"],
                fp=data["fp"],
                fn=data["fn"],
                tn=data["tn"],
                precision=data["precision"],
                recall=data["recall"],
                f1=data["f1"],
                support=data["support"],
            )
            for label, data in per_class_raw.items()
        }

        return ClassificationEvaluationResult(
            fixture_name=fixture_name,
            sample_count=len(dataset),
            accuracy=acc,
            macro_precision=macro["macro_precision"],
            macro_recall=macro["macro_recall"],
            macro_f1=macro["macro_f1"],
            per_class=per_class_objs,
            confusion_matrix=matrix,
            canonical_labels=self.canonical_classes,
            elapsed_seconds=elapsed,
            misclassifications=misclassifications,
        )
