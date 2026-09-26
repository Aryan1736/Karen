"""
Karen's Ear — Urgency Evaluation Module.

Feature 11 — Quantitative Evaluation Layer.
Evaluates the operational urgency engine via the canonical public
inference pipeline entry point:
    from ml.pipeline import inference_engine
    result = inference_engine.analyze(report_text)

Evaluates performance across all 4 canonical urgency tiers:
    CRITICAL (80-100), HIGH (60-79), MEDIUM (35-59), LOW (0-34)
using the curated engineering urgency benchmark (CURATED_URGENCY_BENCHMARK).

IMPORTANT EVALUATION NOTICE:
This benchmark measures agreement against CURATED ENGINEERING REFERENCE LABELS.
It does NOT report accuracy against CrisiText ground truth (which does not exist).
It is an internal engineering fixture to verify deterministic tier mapping,
boundary handling, and life-safety priority.

Critical Metric Invariant:
    Critical False-Negative Rate = FN / (TP + FN)
    where positive class is CRITICAL.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from ml.config import CANONICAL_URGENCY_LEVELS
from ml.evaluation.metrics import (
    calculate_accuracy,
    calculate_critical_false_negative_rate,
    calculate_critical_recall,
    calculate_macro_metrics,
    calculate_per_class_metrics,
    compute_confusion_matrix,
)
from ml.pipeline import inference_engine
from ml.pipeline.inference_engine import InferenceEngine
from ml.tests.fixtures.urgency_benchmark import (
    CURATED_URGENCY_BENCHMARK,
    UrgencyBenchmarkSample,
)


@dataclass
class UrgencyTierMetrics:
    """Metrics for an individual urgency tier."""

    tier: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    support: int = 0


@dataclass
class UrgencyEvaluationResult:
    """Consolidated quantitative results from urgency evaluation."""

    fixture_name: str
    sample_count: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    critical_recall: float
    critical_false_negative_rate: float
    per_tier: dict[str, UrgencyTierMetrics]
    confusion_matrix: dict[str, dict[str, int]]
    canonical_tiers: list[str]
    elapsed_seconds: float
    notice: str = (
        "Engineering reference benchmark evaluation only. "
        "CrisiText does NOT provide operational urgency labels."
    )
    mismatches: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converts results to a JSON-serializable dictionary."""
        return {
            "fixture_name": self.fixture_name,
            "sample_count": self.sample_count,
            "accuracy": self.accuracy,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "critical_recall": self.critical_recall,
            "critical_false_negative_rate": self.critical_false_negative_rate,
            "canonical_tiers": self.canonical_tiers,
            "per_tier": {k: asdict(v) for k, v in self.per_tier.items()},
            "confusion_matrix": self.confusion_matrix,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "notice": self.notice,
            "mismatches": self.mismatches,
        }


class UrgencyEvaluator:
    """
    Evaluator for operational urgency classification via the unified inference pipeline.
    """

    def __init__(
        self,
        engine: InferenceEngine | None = None,
        canonical_tiers: Sequence[str] = CANONICAL_URGENCY_LEVELS,
    ) -> None:
        self.engine = engine or inference_engine
        self.canonical_tiers = list(canonical_tiers)

    def evaluate(
        self,
        dataset: Sequence[UrgencyBenchmarkSample] = CURATED_URGENCY_BENCHMARK,
        fixture_name: str = "CURATED_URGENCY_BENCHMARK",
    ) -> UrgencyEvaluationResult:
        """
        Executes urgency evaluation across all samples in the curated benchmark.
        """
        if not dataset:
            raise ValueError("Evaluation dataset cannot be empty")

        y_true: list[str] = []
        y_pred: list[str] = []
        mismatches: list[dict[str, Any]] = []

        t_start = time.perf_counter()

        for sample in dataset:
            ref_label = sample.expected_reference_label
            res = self.engine.analyze(sample.text, report_id=sample.id)
            urgency_dict = res.get("urgency", {})
            pred_label = urgency_dict.get("label") or "LOW"
            confidence = urgency_dict.get("confidence")

            y_true.append(ref_label)
            y_pred.append(pred_label)

            if pred_label != ref_label:
                mismatches.append({
                    "id": sample.id,
                    "expected": ref_label,
                    "predicted": pred_label,
                    "confidence": confidence,
                    "scenario": sample.scenario_category,
                    "text_snippet": sample.text[:80] + ("..." if len(sample.text) > 80 else ""),
                })

        elapsed = time.perf_counter() - t_start

        # Calculate 4x4 confusion matrix & per-tier metrics
        matrix = compute_confusion_matrix(y_true, y_pred, self.canonical_tiers)
        per_tier_raw = calculate_per_class_metrics(matrix, self.canonical_tiers)
        macro = calculate_macro_metrics(per_tier_raw, only_supported=True)

        correct_count = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
        acc = calculate_accuracy(correct_count, len(y_true))

        # Critical tier metrics
        crit_tp = per_tier_raw.get("CRITICAL", {}).get("tp", 0)
        crit_fn = per_tier_raw.get("CRITICAL", {}).get("fn", 0)
        crit_recall = calculate_critical_recall(crit_tp, crit_fn)
        crit_fnr = calculate_critical_false_negative_rate(crit_tp, crit_fn)

        per_tier_objs: dict[str, UrgencyTierMetrics] = {
            tier: UrgencyTierMetrics(
                tier=tier,
                tp=data["tp"],
                fp=data["fp"],
                fn=data["fn"],
                tn=data["tn"],
                precision=data["precision"],
                recall=data["recall"],
                f1=data["f1"],
                support=data["support"],
            )
            for tier, data in per_tier_raw.items()
        }

        return UrgencyEvaluationResult(
            fixture_name=fixture_name,
            sample_count=len(dataset),
            accuracy=acc,
            macro_precision=macro["macro_precision"],
            macro_recall=macro["macro_recall"],
            macro_f1=macro["macro_f1"],
            critical_recall=crit_recall,
            critical_false_negative_rate=crit_fnr,
            per_tier=per_tier_objs,
            confusion_matrix=matrix,
            canonical_tiers=self.canonical_tiers,
            elapsed_seconds=elapsed,
            mismatches=mismatches,
        )
