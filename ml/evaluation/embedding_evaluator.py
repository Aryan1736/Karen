"""
Karen's Ear — Embedding Semantic Evaluation Module.

Feature 11 — Quantitative Evaluation Layer.
Evaluates the dense semantic embedding component (sentence-transformers/all-MiniLM-L6-v2)
against curated semantic pairs with positive and negative relationships:
    positive = semantically related (high similarity)
    negative = semantically unrelated or adversarial (lower similarity / state shift / negation)

Key Metrics:
- ROC Curve & ROC-AUC
- Precision @ configurable similarity threshold
- Recall @ configurable similarity threshold
- F1 @ configurable similarity threshold
- Confusion matrix @ threshold (TP, FP, FN, TN)
- Invariance & behavioral sanity (L2 unit norm, self-similarity, symmetry)

IMPORTANT INTEGRITY NOTICE:
- The similarity threshold is strictly configurable; it does NOT hardcode backend
  fusion or deduplication thresholds.
- Measures the embedding signal itself.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import numpy as np

from ml.embeddings.embedder import SentenceTransformerEmbedder
from ml.evaluation.metrics import (
    calculate_binary_metrics_at_threshold,
    calculate_roc_auc,
    calculate_roc_curve,
)
from ml.pipeline import inference_engine
from ml.pipeline.inference_engine import InferenceEngine
from ml.tests.fixtures.embedding_benchmark import (
    CURATED_SEMANTIC_PAIRS,
    SELF_SIMILARITY_TEXTS,
    SemanticPair,
)


@dataclass
class EmbeddingThresholdMetrics:
    """Classification metrics at a specific similarity threshold."""

    threshold: float
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    f1: float
    accuracy: float
    total_pairs: int


@dataclass
class EmbeddingEvaluationResult:
    """Consolidated quantitative results from semantic embedding evaluation."""

    fixture_name: str
    model_name: str
    embedding_dimension: int
    total_pairs_evaluated: int
    positive_pair_count: int
    negative_pair_count: int
    roc_auc: float
    configured_threshold: float
    metrics_at_threshold: EmbeddingThresholdMetrics
    roc_curve: dict[str, list[float]]
    norm_invariance_passed: bool
    self_similarity_passed: bool
    symmetry_passed: bool
    mean_positive_similarity: float
    mean_negative_similarity: float
    semantic_margin: float
    elapsed_seconds: float
    pair_details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converts results to a JSON-serializable dictionary."""
        return {
            "fixture_name": self.fixture_name,
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "total_pairs_evaluated": self.total_pairs_evaluated,
            "positive_pair_count": self.positive_pair_count,
            "negative_pair_count": self.negative_pair_count,
            "roc_auc": self.roc_auc,
            "configured_threshold": self.configured_threshold,
            "metrics_at_threshold": asdict(self.metrics_at_threshold),
            "roc_curve": self.roc_curve,
            "norm_invariance_passed": self.norm_invariance_passed,
            "self_similarity_passed": self.self_similarity_passed,
            "symmetry_passed": self.symmetry_passed,
            "mean_positive_similarity": round(self.mean_positive_similarity, 4),
            "mean_negative_similarity": round(self.mean_negative_similarity, 4),
            "semantic_margin": round(self.semantic_margin, 4),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "pair_details": self.pair_details,
        }


class EmbeddingEvaluator:
    """
    Evaluator for semantic embedding representations and thresholded discrimination.
    """

    def __init__(
        self,
        embedder: SentenceTransformerEmbedder | None = None,
        engine: InferenceEngine | None = None,
        default_threshold: float = 0.75,
    ) -> None:
        if embedder is not None:
            self.embedder = embedder
        elif engine is not None:
            self.embedder = engine.embedder
        else:
            self.embedder = inference_engine.embedder
        self.default_threshold = default_threshold

    def evaluate(
        self,
        pairs: Sequence[SemanticPair] = CURATED_SEMANTIC_PAIRS,
        self_texts: Sequence[str] = SELF_SIMILARITY_TEXTS,
        threshold: float | None = None,
        fixture_name: str = "CURATED_SEMANTIC_PAIRS",
    ) -> EmbeddingEvaluationResult:
        """
        Executes semantic pair evaluation, calculates ROC-AUC, threshold metrics,
        and verifies behavioral invariants.
        """
        if not pairs:
            raise ValueError("Pairs dataset cannot be empty")

        eval_threshold = threshold if threshold is not None else self.default_threshold
        t_start = time.perf_counter()

        # 1. Behavioral invariants
        norm_invariance_passed = True
        self_similarity_passed = True

        for text in self_texts:
            vec = self.embedder.encode_numpy(text)
            norm = float(np.linalg.norm(vec))
            if abs(norm - 1.0) > 1e-3:
                norm_invariance_passed = False

            sim = float(self.embedder.similarity(text, text))
            if abs(sim - 1.0) > 1e-3:
                self_similarity_passed = False

        # 2. Semantic Pairs Evaluation
        y_true: list[int] = []
        y_score: list[float] = []
        pair_details: list[dict[str, Any]] = []
        symmetry_passed = True

        pos_sims: list[float] = []
        neg_sims: list[float] = []

        for p in pairs:
            # Positive class: high_similarity
            is_pos = 1 if p.category == "high_similarity" else 0
            sim_ab = float(self.embedder.similarity(p.text_a, p.text_b))
            sim_ba = float(self.embedder.similarity(p.text_b, p.text_a))

            if abs(sim_ab - sim_ba) > 1e-4:
                symmetry_passed = False

            y_true.append(is_pos)
            y_score.append(sim_ab)

            if is_pos == 1:
                pos_sims.append(sim_ab)
            else:
                neg_sims.append(sim_ab)

            pair_details.append({
                "pair_id": p.pair_id,
                "category": p.category,
                "domain": p.domain,
                "similarity": round(sim_ab, 4),
                "is_positive": bool(is_pos),
                "predicted_positive_at_threshold": bool(sim_ab >= eval_threshold),
            })

        # 3. Compute ROC curve & ROC-AUC
        roc_auc = calculate_roc_auc(y_true, y_score)
        fpr, tpr, roc_thresholds = calculate_roc_curve(y_true, y_score)

        # 4. Compute binary metrics at configured threshold
        raw_metrics = calculate_binary_metrics_at_threshold(y_true, y_score, threshold=eval_threshold)
        metrics_obj = EmbeddingThresholdMetrics(
            threshold=eval_threshold,
            tp=raw_metrics["tp"],
            fp=raw_metrics["fp"],
            fn=raw_metrics["fn"],
            tn=raw_metrics["tn"],
            precision=raw_metrics["precision"],
            recall=raw_metrics["recall"],
            f1=raw_metrics["f1"],
            accuracy=raw_metrics["accuracy"],
            total_pairs=raw_metrics["total_pairs"],
        )

        mean_pos = float(np.mean(pos_sims)) if pos_sims else 0.0
        mean_neg = float(np.mean(neg_sims)) if neg_sims else 0.0
        margin = mean_pos - mean_neg

        elapsed = time.perf_counter() - t_start

        return EmbeddingEvaluationResult(
            fixture_name=fixture_name,
            model_name=self.embedder.config.embedding_model_name,
            embedding_dimension=self.embedder.config.embedding_dimension,
            total_pairs_evaluated=len(pairs),
            positive_pair_count=sum(y_true),
            negative_pair_count=len(y_true) - sum(y_true),
            roc_auc=roc_auc,
            configured_threshold=eval_threshold,
            metrics_at_threshold=metrics_obj,
            roc_curve={
                "fpr": fpr,
                "tpr": tpr,
                "thresholds": roc_thresholds,
            },
            norm_invariance_passed=norm_invariance_passed,
            self_similarity_passed=self_similarity_passed,
            symmetry_passed=symmetry_passed,
            mean_positive_similarity=mean_pos,
            mean_negative_similarity=mean_neg,
            semantic_margin=margin,
            elapsed_seconds=elapsed,
            pair_details=pair_details,
        )
