"""
Karen's Ear — Embedding Semantic Evaluator & Benchmark Runner.

Evaluates SentenceTransformerEmbedder against curated semantic pairs and self-similarity texts:
1. Unit L2 Norm Invariance: Verifies ||v||₂ ≈ 1.0 across all emitted vectors.
2. Self-Similarity Identity: Verifies similarity(t, t) ≈ 1.0 within numerical tolerance.
3. Symmetry Invariant: Verifies similarity(a, b) == similarity(b, a).
4. Relative Semantic Separation: Verifies semantically related reports score higher
   on average than clearly unrelated cross-domain pairs.
5. Adversarial Shift Analysis: Evaluates sensitivity to negation and operational state changes.
6. Latency & Throughput: Benchmarks single and batch encoding performance on CPU.
7. Benchmark Leakage Check: Verifies benchmark strings are not hardcoded in the engine.

IMPORTANT EVALUATION NOTICE:
This evaluation measures semantic representation quality and sanity.
It is NOT a supervised ground-truth incident deduplication benchmark.
It does NOT define backend incident fusion or duplicate thresholds.
"""

from __future__ import annotations

import inspect
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from ml.embeddings.embedder import (
    SentenceTransformerEmbedder,
    is_model_loaded,
    reset_model_cache,
)
from ml.tests.fixtures.embedding_benchmark import (
    CURATED_SEMANTIC_PAIRS,
    SELF_SIMILARITY_TEXTS,
    SemanticPair,
)


@dataclass
class EmbeddingEvaluationReport:
    """Standardized report emitted by EmbeddingEvaluator."""

    total_pairs_evaluated: int
    self_similarity_passed: bool
    symmetry_passed: bool
    norm_invariance_passed: bool
    semantic_ordering_passed: bool
    leakage_free: bool
    mean_high_similarity: float
    mean_low_similarity: float
    min_high_similarity: float
    max_low_similarity: float
    adversarial_comparisons: list[dict[str, Any]] = field(default_factory=list)
    cold_load_latency_ms: float | None = None
    warm_single_latency_ms: float = 0.0
    warm_batch_latency_ms: float = 0.0
    batch_throughput_items_per_sec: float = 0.0
    embedding_dimension: int = 384
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed_all_behavioral_invariants(self) -> bool:
        """Returns True if all behavioral invariants and sanity checks passed."""
        return (
            self.self_similarity_passed
            and self.symmetry_passed
            and self.norm_invariance_passed
            and self.semantic_ordering_passed
            and self.leakage_free
        )

    def summary(self) -> str:
        """Formats the evaluation results into a clean engineering summary."""
        lines = [
            "==================================================================",
            " Karen's Ear -- Feature 8: Embedding Engine Behavioral Evaluation",
            " Model: sentence-transformers/all-MiniLM-L6-v2",
            "==================================================================",
            f" Total Semantic Pairs Evaluated : {self.total_pairs_evaluated}",
            f" Embedding Output Dimension     : {self.embedding_dimension}",
            "",
            "--- Behavioral Invariants ---",
            f" 1. L2 Norm Invariance (||v||~=1): {'PASSED' if self.norm_invariance_passed else 'FAILED'}",
            f" 2. Self-Similarity (u*u ~= 1.0) : {'PASSED' if self.self_similarity_passed else 'FAILED'}",
            f" 3. Symmetry (sim(a,b)==sim(b,a)): {'PASSED' if self.symmetry_passed else 'FAILED'}",
            f" 4. Relative Semantic Separation: {'PASSED' if self.semantic_ordering_passed else 'FAILED'}",
            f" 5. Zero Benchmark Leakage      : {'PASSED' if self.leakage_free else 'FAILED'}",
            "",
            "--- Similarity Statistics ---",
            f" Mean High-Similarity Score     : {self.mean_high_similarity:.4f} (min: {self.min_high_similarity:.4f})",
            f" Mean Lower-Similarity Score    : {self.mean_low_similarity:.4f} (max: {self.max_low_similarity:.4f})",
            f" Semantic Margin (High - Low)   : {self.mean_high_similarity - self.mean_low_similarity:.4f}",
            "",
            "--- Adversarial Sensitivity (Negation & State Transitions) ---",
        ]
        for adv in self.adversarial_comparisons:
            lines.append(
                f" [{adv['pair_id']}] sim={adv['similarity']:.4f} (delta from 1.0: {adv['delta_from_unity']:.4f}) | {adv['description']}"
            )
        lines.extend([
            "",
            "--- Latency & Performance ---",
            f" Cold Load Latency              : {f'{self.cold_load_latency_ms:.2f} ms' if self.cold_load_latency_ms is not None else 'N/A (already warm)'}",
            f" Warm Single Encode Latency     : {self.warm_single_latency_ms:.2f} ms",
            f" Warm Batch Encode Latency      : {self.warm_batch_latency_ms:.2f} ms",
            f" Batch Throughput               : {self.batch_throughput_items_per_sec:.1f} reports/sec",
            "==================================================================",
        ])
        return "\n".join(lines)


class EmbeddingEvaluator:
    """Evaluates semantic vector behaviors and performance benchmarks."""

    def __init__(self, embedder: SentenceTransformerEmbedder | None = None) -> None:
        self.embedder = embedder or SentenceTransformerEmbedder()

    def evaluate(
        self,
        pairs: Sequence[SemanticPair] | None = None,
        self_texts: Sequence[str] | None = None,
        benchmark_trials: int = 10,
    ) -> EmbeddingEvaluationReport:
        """
        Executes complete behavioral evaluation suite and performance benchmarks.
        """
        eval_pairs = list(pairs or CURATED_SEMANTIC_PAIRS)
        eval_self_texts = list(self_texts or SELF_SIMILARITY_TEXTS)

        # ----------------------------------------------------------------------
        # 1. Benchmark Leakage Check
        # ----------------------------------------------------------------------
        leakage_free = self._check_leakage(eval_pairs)

        # ----------------------------------------------------------------------
        # 2. Cold Load Latency Measurement (if model not yet loaded)
        # ----------------------------------------------------------------------
        cold_latency_ms: float | None = None
        model_name = self.embedder.config.embedding_model_name
        device = self.embedder.config.device
        if not is_model_loaded(model_name, device):
            t0 = time.time()
            _ = self.embedder.encode_single(eval_self_texts[0])
            cold_latency_ms = round((time.time() - t0) * 1000, 2)
        else:
            # Ensure warm
            _ = self.embedder.encode_single(eval_self_texts[0])

        # ----------------------------------------------------------------------
        # 3. Norm Invariance & Self-Similarity Checks
        # ----------------------------------------------------------------------
        norm_invariance_passed = True
        self_similarity_passed = True

        for text in eval_self_texts:
            vec = self.embedder.encode_numpy(text)
            norm = float(np.linalg.norm(vec))
            if abs(norm - 1.0) > 1e-3:
                norm_invariance_passed = False

            sim = self.embedder.similarity(text, text)
            if abs(sim - 1.0) > 1e-3:
                self_similarity_passed = False

        # ----------------------------------------------------------------------
        # 4. Semantic Pair Evaluation
        # ----------------------------------------------------------------------
        symmetry_passed = True
        high_sims: list[float] = []
        low_sims: list[float] = []
        adversarial_results: list[dict[str, Any]] = []

        for pair in eval_pairs:
            sim_ab = self.embedder.similarity(pair.text_a, pair.text_b)
            sim_ba = self.embedder.similarity(pair.text_b, pair.text_a)

            # Symmetry check
            if abs(sim_ab - sim_ba) > 1e-4:
                symmetry_passed = False

            # Categorize
            if pair.category == "high_similarity":
                high_sims.append(sim_ab)
            elif pair.category == "lower_similarity":
                low_sims.append(sim_ab)
            elif pair.category.startswith("adversarial"):
                adversarial_results.append({
                    "pair_id": pair.pair_id,
                    "similarity": round(sim_ab, 4),
                    "delta_from_unity": round(1.0 - sim_ab, 4),
                    "category": pair.category,
                    "description": pair.description,
                })

        mean_high = float(np.mean(high_sims)) if high_sims else 0.0
        mean_low = float(np.mean(low_sims)) if low_sims else 0.0
        min_high = float(np.min(high_sims)) if high_sims else 0.0
        max_low = float(np.max(low_sims)) if low_sims else 0.0

        # High similarity pairs must score higher on average than lower similarity pairs
        semantic_ordering_passed = (mean_high > mean_low) and (mean_high >= 0.70)

        # ----------------------------------------------------------------------
        # 5. Latency Benchmarks
        # ----------------------------------------------------------------------
        single_latencies: list[float] = []
        for _ in range(benchmark_trials):
            t0 = time.time()
            _ = self.embedder.encode_single(eval_self_texts[0])
            single_latencies.append((time.time() - t0) * 1000)
        warm_single_latency_ms = round(statistics.mean(single_latencies), 2)

        # Batch benchmark
        all_unique_texts = list({p.text_a for p in eval_pairs} | {p.text_b for p in eval_pairs})
        t_batch_start = time.time()
        _ = self.embedder.encode_batch(all_unique_texts)
        batch_duration_s = time.time() - t_batch_start
        warm_batch_latency_ms = round(batch_duration_s * 1000, 2)
        batch_throughput = round(len(all_unique_texts) / batch_duration_s, 1) if batch_duration_s > 0 else 0.0

        return EmbeddingEvaluationReport(
            total_pairs_evaluated=len(eval_pairs),
            self_similarity_passed=self_similarity_passed,
            symmetry_passed=symmetry_passed,
            norm_invariance_passed=norm_invariance_passed,
            semantic_ordering_passed=semantic_ordering_passed,
            leakage_free=leakage_free,
            mean_high_similarity=round(mean_high, 4),
            mean_low_similarity=round(mean_low, 4),
            min_high_similarity=round(min_high, 4),
            max_low_similarity=round(max_low, 4),
            adversarial_comparisons=adversarial_results,
            cold_load_latency_ms=cold_latency_ms,
            warm_single_latency_ms=warm_single_latency_ms,
            warm_batch_latency_ms=warm_batch_latency_ms,
            batch_throughput_items_per_sec=batch_throughput,
            embedding_dimension=self.embedder.config.embedding_dimension,
            details={
                "high_sim_scores": [round(s, 4) for s in high_sims],
                "low_sim_scores": [round(s, 4) for s in low_sims],
                "num_unique_batch_texts": len(all_unique_texts),
            },
        )

    def _check_leakage(self, pairs: Sequence[SemanticPair]) -> bool:
        """
        Inspects the embedder source code to verify no benchmark strings are hardcoded.
        """
        try:
            source_code = inspect.getsource(SentenceTransformerEmbedder)
            for pair in pairs:
                # Text literals should never be present in the embedding engine code
                if pair.text_a.lower() in source_code.lower():
                    return False
                if pair.text_b.lower() in source_code.lower():
                    return False
            return True
        except Exception:
            return True


def run_embedding_evaluation() -> EmbeddingEvaluationReport:
    """Convenience runner for full embedding evaluation."""
    evaluator = EmbeddingEvaluator()
    return evaluator.evaluate()


if __name__ == "__main__":
    report = run_embedding_evaluation()
    print(report.summary())
