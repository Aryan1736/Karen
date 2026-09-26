"""
Karen's Ear — Required-Response Multi-Label Evaluator & Benchmark Runner.

Evaluates RequiredResponseExtractor against curated engineering benchmarks:
1. Exact-set match rate (prediction set == ground-truth set).
2. Micro precision, recall, and F1 across all label decisions.
3. Macro precision, recall, and F1 across canonical categories.
4. Per-category metrics (TP, FP, FN, TN, Precision, Recall, F1).
5. False-positive rate on negative / no-response dispatches.
6. Latency metrics (mean, p95, min, max).
7. Benchmark leakage check (verifies test sentences are not copied from implementation rules).
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.config import CANONICAL_RESPONSE_TYPES
from ml.response.response_extractor import RequiredResponseExtractor
from ml.response.taxonomy import RESPONSE_TAXONOMY_CATALOG
from ml.tests.fixtures.response_benchmark import (
    RESPONSE_BENCHMARK_DATASET,
    ResponseBenchmarkSample,
)


@dataclass
class CategoryMetrics:
    """Precision, recall, and F1 for an individual response category."""

    category: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return round(self.tp / denom, 4) if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return round(self.tp / denom, 4) if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return round(2 * (p * r) / (p + r), 4) if (p + r) > 0 else 0.0


@dataclass
class MultiLabelEvaluationReport:
    """Consolidated multi-label benchmark evaluation report."""

    total_samples: int
    exact_set_matches: int
    exact_set_match_rate: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    false_positive_rate: float
    per_category: dict[str, CategoryMetrics] = field(default_factory=dict)
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    leakage_check_passed: bool = True
    mismatches: list[dict[str, Any]] = field(default_factory=list)

    def format_summary_table(self) -> str:
        """Formats per-category metrics into a Markdown table."""
        lines = [
            "| Category | TP | FP | FN | Precision | Recall | F1-Score |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for cat in CANONICAL_RESPONSE_TYPES:
            m = self.per_category.get(cat, CategoryMetrics(category=cat))
            lines.append(
                f"| `{m.category}` | {m.tp} | {m.fp} | {m.fn} | "
                f"{m.precision:.4f} | {m.recall:.4f} | {m.f1:.4f} |"
            )
        return "\n".join(lines)


class ResponseEvaluator:
    """
    Evaluates RequiredResponseExtractor on multi-label benchmark datasets.
    """

    def __init__(self, extractor: RequiredResponseExtractor | None = None) -> None:
        self.extractor = extractor or RequiredResponseExtractor()

    def run_leakage_check(
        self,
        dataset: Sequence[ResponseBenchmarkSample] = RESPONSE_BENCHMARK_DATASET,
    ) -> dict[str, Any]:
        """
        Verifies benchmark integrity by checking if any benchmark sample sentences
        were directly copied verbatim from taxonomy pattern definitions.
        """
        leakages: list[str] = []
        for sample in dataset:
            text_lower = sample.text.lower()
            for cat, cat_def in RESPONSE_TAXONOMY_CATALOG.items():
                for pat in cat_def.strong_patterns:
                    # If pattern equals entire text exactly, flag as potential leakage
                    exact_match = pat.fullmatch(text_lower)
                    if exact_match and len(text_lower.split()) > 3:
                        leakages.append(f"Sample '{sample.id}' exactly matches regex '{pat.pattern}'")

        return {
            "passed": len(leakages) == 0,
            "leakages_found": len(leakages),
            "details": leakages,
        }

    def evaluate(
        self,
        dataset: Sequence[ResponseBenchmarkSample] = RESPONSE_BENCHMARK_DATASET,
    ) -> MultiLabelEvaluationReport:
        """
        Executes multi-label benchmark evaluation across the provided dataset.
        """
        exact_matches = 0
        latencies_ms: list[float] = []
        per_category: dict[str, CategoryMetrics] = {
            cat: CategoryMetrics(category=cat) for cat in CANONICAL_RESPONSE_TYPES
        }
        mismatches: list[dict[str, Any]] = []

        # For negative samples false-positive tracking
        neg_total = 0
        neg_false_positives = 0

        for sample in dataset:
            t0 = time.perf_counter()
            result = self.extractor.extract(sample.text, report_id=sample.id)
            lat_ms = (time.perf_counter() - t0) * 1000
            latencies_ms.append(lat_ms)

            predicted_set = set(r.type for r in result.responses)
            expected_set = set(sample.expected_categories)

            # Exact-set match
            if predicted_set == expected_set:
                exact_matches += 1
            else:
                mismatches.append({
                    "id": sample.id,
                    "text": sample.text,
                    "expected": sorted(list(expected_set)),
                    "predicted": sorted(list(predicted_set)),
                    "scenario_type": sample.scenario_type,
                })

            # Negative sample false positive tracking
            if not expected_set:
                neg_total += 1
                if predicted_set:
                    neg_false_positives += 1

            # Per-category binary evaluation
            for cat in CANONICAL_RESPONSE_TYPES:
                is_predicted = cat in predicted_set
                is_expected = cat in expected_set

                if is_predicted and is_expected:
                    per_category[cat].tp += 1
                elif is_predicted and not is_expected:
                    per_category[cat].fp += 1
                elif not is_predicted and is_expected:
                    per_category[cat].fn += 1
                else:
                    per_category[cat].tn += 1

        total_samples = len(dataset)
        exact_match_rate = round(exact_matches / total_samples, 4) if total_samples > 0 else 0.0

        # Micro Precision, Recall, F1
        total_tp = sum(m.tp for m in per_category.values())
        total_fp = sum(m.fp for m in per_category.values())
        total_fn = sum(m.fn for m in per_category.values())

        micro_prec = round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else 0.0
        micro_rec = round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else 0.0
        micro_f1 = (
            round(2 * (micro_prec * micro_rec) / (micro_prec + micro_rec), 4)
            if (micro_prec + micro_rec) > 0
            else 0.0
        )

        # Macro Precision, Recall, F1
        macro_prec = round(sum(m.precision for m in per_category.values()) / len(CANONICAL_RESPONSE_TYPES), 4)
        macro_rec = round(sum(m.recall for m in per_category.values()) / len(CANONICAL_RESPONSE_TYPES), 4)
        macro_f1 = (
            round(2 * (macro_prec * macro_rec) / (macro_prec + macro_rec), 4)
            if (macro_prec + macro_rec) > 0
            else 0.0
        )

        # False positive rate on negative/no-response dispatches
        fpr = round(neg_false_positives / neg_total, 4) if neg_total > 0 else 0.0

        # Latency metrics
        avg_lat = round(statistics.mean(latencies_ms), 3) if latencies_ms else 0.0
        min_lat = round(min(latencies_ms), 3) if latencies_ms else 0.0
        max_lat = round(max(latencies_ms), 3) if latencies_ms else 0.0
        sorted_lat = sorted(latencies_ms)
        p95_idx = int(0.95 * len(sorted_lat))
        p95_lat = round(sorted_lat[min(p95_idx, len(sorted_lat) - 1)], 3) if sorted_lat else 0.0

        leakage_res = self.run_leakage_check(dataset)

        return MultiLabelEvaluationReport(
            total_samples=total_samples,
            exact_set_matches=exact_matches,
            exact_set_match_rate=exact_match_rate,
            micro_precision=micro_prec,
            micro_recall=micro_rec,
            micro_f1=micro_f1,
            macro_precision=macro_prec,
            macro_recall=macro_rec,
            macro_f1=macro_f1,
            false_positive_rate=fpr,
            per_category=per_category,
            average_latency_ms=avg_lat,
            p95_latency_ms=p95_lat,
            min_latency_ms=min_lat,
            max_latency_ms=max_lat,
            leakage_check_passed=leakage_res["passed"],
            mismatches=mismatches,
        )
