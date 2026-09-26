"""
Karen's Ear — Incident Classifier Evaluation & Benchmarking Suite.

Provides quantitative verification for incident classification approaches:
1. Keyword/Phrase Baseline
2. Semantic Prototype (all-MiniLM-L6-v2)
3. Hybrid Classifier (Keyword + Semantic)

EVALUATION SCOPE & INTEGRITY NOTICE:
- Benchmark Dataset: 63-sample curated engineering benchmark across 9 canonical classes.
- This is an internal smoke and engineering benchmark used to verify determinism,
  regression safety, and relative behavior across modes on CPU hardware.
- It is NOT evidence of real-world 100% classification accuracy on unseen, wild crisis distributions.
- A larger zero-shot transformer was not benchmarked because the implemented hybrid classifier
  already met the engineering requirements.

CONFIDENCE & METRIC DISTINCTIONS:
- Classification Confidence: An internal score proxy in [0.0, 1.0] reflecting evidence margin and certainty.
- Calibrated Probability: Distinct from raw similarity; calibration is a relative proxy.
- Operational Urgency: Categorical operational tier (CRITICAL/HIGH/MEDIUM/LOW) derived in Feature 4.
- Backend Priority: Deterministic 0.0-100.0 score calculated by backend business logic.
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.classification.incident_classifier import IncidentClassifier
from ml.classification.taxonomy import INCIDENT_TAXONOMY_CATALOG
from ml.config import CANONICAL_INCIDENT_TYPES, MLConfig, get_ml_config
from ml.tests.fixtures.incident_benchmark import INCIDENT_BENCHMARK_DATASET, BenchmarkItem


@dataclass
class ClassMetrics:
    """Per-class classification performance metrics."""

    label: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    support: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return round(self.true_positives / denom, 4) if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return round(self.true_positives / denom, 4) if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p = self.precision
        r = self.recall
        return round(2 * (p * r) / (p + r), 4) if (p + r) > 0 else 0.0


@dataclass
class EvaluationReport:
    """Consolidated classification benchmark evaluation report."""

    approach_name: str
    total_samples: int
    correct_samples: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_class: dict[str, ClassMetrics]
    confusion_matrix: dict[str, dict[str, int]]
    cold_init_latency_ms: float
    warm_avg_latency_ms: float
    p95_latency_ms: float
    batch_throughput_items_per_sec: float
    errors: list[dict[str, Any]] = field(default_factory=list)


class ClassifierEvaluator:
    """Executes quantitative benchmarks against curated incident fixtures."""

    def __init__(self, config: MLConfig | None = None) -> None:
        self.config = config or get_ml_config()

    def evaluate(
        self,
        classifier: IncidentClassifier,
        benchmark: Sequence[BenchmarkItem] = INCIDENT_BENCHMARK_DATASET,
        approach_name: str = "Classifier",
    ) -> EvaluationReport:
        """Runs the benchmark suite on a classifier instance and compiles metrics."""
        total = len(benchmark)
        if total == 0:
            raise ValueError("Benchmark dataset cannot be empty")

        per_class: dict[str, ClassMetrics] = {
            label: ClassMetrics(label=label) for label in CANONICAL_INCIDENT_TYPES
        }
        confusion_matrix: dict[str, dict[str, int]] = {
            true_lbl: dict.fromkeys(CANONICAL_INCIDENT_TYPES, 0)
            for true_lbl in CANONICAL_INCIDENT_TYPES
        }

        # Warm-up / cold start measurement
        cold_start = time.time()
        _ = classifier.predict("Warm up test emergency report text.")
        cold_init_ms = round((time.time() - cold_start) * 1000, 2)

        latencies_ms: list[float] = []
        correct = 0
        errors: list[dict[str, Any]] = []

        for item in benchmark:
            t0 = time.time()
            res = classifier.predict(item.text, report_id=item.id)
            lat_ms = (time.time() - t0) * 1000
            latencies_ms.append(lat_ms)

            true_label = item.expected_label
            pred_label = res.label or "OTHER_GENERAL_INCIDENT"

            # Record support and confusion
            if true_label in per_class:
                per_class[true_label].support += 1
            if true_label in confusion_matrix and pred_label in confusion_matrix[true_label]:
                confusion_matrix[true_label][pred_label] += 1

            if pred_label == true_label:
                correct += 1
                if true_label in per_class:
                    per_class[true_label].true_positives += 1
            else:
                if pred_label in per_class:
                    per_class[pred_label].false_positives += 1
                if true_label in per_class:
                    per_class[true_label].false_negatives += 1
                errors.append({
                    "id": item.id,
                    "text": item.text,
                    "expected": true_label,
                    "predicted": pred_label,
                    "confidence": res.confidence,
                    "top_candidates": res.evidence.get("top_candidates", []),
                })

        accuracy = round(correct / total, 4)

        # Macro averages across all classes with support
        valid_classes = [c for c in per_class.values() if c.support > 0]
        macro_p = round(sum(c.precision for c in valid_classes) / len(valid_classes), 4)
        macro_r = round(sum(c.recall for c in valid_classes) / len(valid_classes), 4)
        macro_f1 = round(sum(c.f1 for c in valid_classes) / len(valid_classes), 4)

        latencies_sorted = sorted(latencies_ms)
        warm_avg_ms = round(sum(latencies_ms) / len(latencies_ms), 2)
        p95_idx = int(len(latencies_sorted) * 0.95)
        p95_ms = round(latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)], 2)

        # Batch latency test
        batch_t0 = time.time()
        _ = classifier.predict_batch([item.text for item in benchmark])
        batch_elapsed = time.time() - batch_t0
        throughput = round(total / batch_elapsed, 2) if batch_elapsed > 0 else 0.0

        return EvaluationReport(
            approach_name=approach_name,
            total_samples=total,
            correct_samples=correct,
            accuracy=accuracy,
            macro_precision=macro_p,
            macro_recall=macro_r,
            macro_f1=macro_f1,
            per_class=per_class,
            confusion_matrix=confusion_matrix,
            cold_init_latency_ms=cold_init_ms,
            warm_avg_latency_ms=warm_avg_ms,
            p95_latency_ms=p95_ms,
            batch_throughput_items_per_sec=throughput,
            errors=errors,
        )


def run_benchmark_comparison() -> dict[str, EvaluationReport]:
    """
    Executes and prints comparison across the candidate classification approaches:
    A. Deterministic Keyword Baseline
    B. Semantic Prototype Similarity
    C. Hybrid Classifier (Keyword + Semantic)
    """
    print("\n" + "=" * 78)
    print("KAREN'S EAR — ML INCIDENT CLASSIFIER 63-SAMPLE CURATED ENGINEERING BENCHMARK")
    print(f"Benchmark Dataset: {len(INCIDENT_BENCHMARK_DATASET)} samples across 9 canonical classes")
    print("Hardware Target: Local CPU (sentence-transformers/all-MiniLM-L6-v2)")
    print("Notice: A larger zero-shot transformer was not benchmarked because the")
    print("        implemented hybrid classifier already met the engineering requirements.")
    print("=" * 78)

    evaluator = ClassifierEvaluator()
    reports: dict[str, EvaluationReport] = {}

    approaches = [
        ("Keyword Baseline", "keyword"),
        ("Semantic Prototype", "semantic"),
        ("Hybrid (Recommended)", "hybrid"),
    ]

    for name, mode in approaches:
        print(f"\nEvaluating: {name} (mode={mode})...")
        clf = IncidentClassifier(mode=mode)
        rep = evaluator.evaluate(clf, approach_name=name)
        reports[name] = rep

        print(f"  Accuracy:        {rep.accuracy * 100:.1f}% ({rep.correct_samples}/{rep.total_samples})")
        print(f"  Macro F1:        {rep.macro_f1:.4f}")
        print(f"  Macro Precision: {rep.macro_precision:.4f}")
        print(f"  Macro Recall:    {rep.macro_recall:.4f}")
        print(f"  Warm Latency:    {rep.warm_avg_latency_ms:.2f} ms (p95: {rep.p95_latency_ms:.2f} ms)")
        print(f"  Throughput:      {rep.batch_throughput_items_per_sec:.1f} reports/sec")
        if rep.errors:
            print(f"  Errors ({len(rep.errors)}):")
            for err in rep.errors[:3]:
                print(f"    - [{err['id']}] Expected: {err['expected']} | Predicted: {err['predicted']}")
            if len(rep.errors) > 3:
                print(f"    ... and {len(rep.errors) - 3} more")

    # Summary table
    print("\n" + "=" * 78)
    print(f"{'Approach':<24} | {'Accuracy':<10} | {'Macro F1':<10} | {'Latency (ms)':<14} | {'Throughput':<12}")
    print("-" * 78)
    for name, rep in reports.items():
        print(
            f"{name:<24} | {rep.accuracy*100:>8.1f}% | {rep.macro_f1:>10.4f} | "
            f"{rep.warm_avg_latency_ms:>10.2f} ms | {rep.batch_throughput_items_per_sec:>8.1f}/s"
        )
    print("=" * 78 + "\n")

    return reports


if __name__ == "__main__":
    _ = run_benchmark_comparison()
