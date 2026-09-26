"""
Karen's Ear — Entity & Location Extraction Evaluation Module.

Feature 11 — Quantitative Evaluation Layer.
Evaluates primary incident location extraction and named entity recognition
via the canonical public inference entry point:
    from ml.pipeline import inference_engine
    result = inference_engine.analyze(report_text)

Benchmark Fixture:
    NER_BENCHMARK_DATASET (30 samples: 20 positive crisis dispatches, 10 negative distractors)

Matching Methodologies (Explicitly Documented & Disaggregated):
1. Location Spans (Normalized Sub-Span Containment):
   Evaluates primary location text (result["location"]["text"]) against sample.expected_location.
   Matching Rule: "normalized sub-span containment" (lowercase, stripped, sub-span containment).
   - Negative samples (expected_location=None): predicted None is TN, non-null is FP.
   - Positive samples: sub-span containment match is TP, non-match is FN (and FP if predicted).

2. Location Spans (Exact Normalized):
   Evaluates primary location text against sample.expected_location.
   Matching Rule: "exact_normalized" (lowercase, stripped, exact equality).
   - Negative samples: predicted None is TN, non-null is FP.
   - Positive samples: exact normalized match is TP, non-match is FN (and FP if predicted).

3. Entity Type + Span Jointly:
   Evaluates extracted entities (result["entities"]) against sample.expected_entities.
   Matching Rule: Predicted entity matches expected entity iff:
       normalized(pred.text) == normalized(exp.text) AND pred.type == exp.type
   Greedy 1-to-1 alignment per sample.
   Reports overall TP, FP, FN, Precision, Recall, F1 and per-entity-type breakdown.

4. Entity Span Only:
   Evaluates extracted entities (result["entities"]) against sample.expected_entities
   ignoring entity category:
       normalized(pred.text) == normalized(exp.text)
   Reports overall TP, FP, FN, Precision, Recall, F1.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from ml.evaluation.metrics import (
    calculate_accuracy,
    calculate_f1,
    calculate_precision,
    calculate_recall,
)
from ml.pipeline import inference_engine
from ml.pipeline.inference_engine import InferenceEngine
from ml.tests.fixtures.ner_benchmark import (
    NER_BENCHMARK_DATASET,
    ExpectedEntity,
    NERBenchmarkSample,
)


def normalize_span(text: str | None) -> str:
    """Normalizes an entity or location text span for exact comparison."""
    if text is None:
        return ""
    cleaned = text.strip().lower()
    return re.sub(r"\s+", " ", cleaned)


@dataclass
class SpanMetrics:
    """Evaluation metrics for a specific span extraction task."""

    matching_rule: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    support: int = 0


@dataclass
class EntityEvaluationResult:
    """Consolidated quantitative results from evaluating entity & location extraction."""

    fixture_name: str
    sample_count: int
    positive_samples: int
    negative_samples: int
    location_subspan_metrics: SpanMetrics
    location_exact_metrics: SpanMetrics
    joint_entity_metrics: SpanMetrics
    span_only_entity_metrics: SpanMetrics
    per_entity_type_metrics: dict[str, SpanMetrics]
    elapsed_seconds: float
    mismatches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def location_span_metrics(self) -> SpanMetrics:
        """Alias for location_subspan_metrics for backward compatibility."""
        return self.location_subspan_metrics

    def to_dict(self) -> dict[str, Any]:
        """Converts results to a JSON-serializable dictionary."""
        return {
            "fixture_name": self.fixture_name,
            "sample_count": self.sample_count,
            "positive_samples": self.positive_samples,
            "negative_samples": self.negative_samples,
            "location_subspan_metrics": asdict(self.location_subspan_metrics),
            "location_exact_metrics": asdict(self.location_exact_metrics),
            "location_span_metrics": asdict(self.location_subspan_metrics),
            "joint_entity_metrics": asdict(self.joint_entity_metrics),
            "span_only_entity_metrics": asdict(self.span_only_entity_metrics),
            "per_entity_type_metrics": {k: asdict(v) for k, v in self.per_entity_type_metrics.items()},
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "mismatches": self.mismatches,
        }


class EntityEvaluator:
    """
    Evaluator for location and entity extraction via the unified inference pipeline.
    """

    def __init__(self, engine: InferenceEngine | None = None) -> None:
        self.engine = engine or inference_engine

    def evaluate(
        self,
        dataset: Sequence[NERBenchmarkSample] = NER_BENCHMARK_DATASET,
        fixture_name: str = "NER_BENCHMARK_DATASET",
    ) -> EntityEvaluationResult:
        """
        Executes complete entity extraction evaluation across all benchmark samples.
        """
        if not dataset:
            raise ValueError("Evaluation dataset cannot be empty")

        t_start = time.perf_counter()

        # Location subspan metrics accumulators (normalized sub-span containment)
        loc_subspan_tp = 0
        loc_subspan_fp = 0
        loc_subspan_fn = 0
        loc_subspan_tn = 0
        loc_support = 0

        # Location exact normalized metrics accumulators
        loc_exact_tp = 0
        loc_exact_fp = 0
        loc_exact_fn = 0
        loc_exact_tn = 0

        # Joint entity metrics accumulators
        joint_tp = 0
        joint_fp = 0
        joint_fn = 0
        joint_support = 0

        # Span-only entity metrics accumulators
        span_tp = 0
        span_fp = 0
        span_fn = 0
        span_support = 0

        # Per-entity-type accumulators: {type: {"tp": 0, "fp": 0, "fn": 0, "support": 0}}
        per_type_counts: dict[str, dict[str, int]] = {}

        mismatches: list[dict[str, Any]] = []

        n_pos = 0
        n_neg = 0

        for sample in dataset:
            if sample.is_negative:
                n_neg += 1
            else:
                n_pos += 1

            # Run inference through canonical pipeline
            res = self.engine.analyze(sample.text, report_id=sample.sample_id)
            pred_location_dict = res.get("location", {})
            pred_location_text = pred_location_dict.get("text")
            pred_entities = res.get("entities", [])

            # ------------------------------------------------------------------
            # 1. Location Span Matching (Sub-Span Containment & Exact Normalized)
            # ------------------------------------------------------------------
            norm_exp_loc = normalize_span(sample.expected_location)
            norm_pred_loc = normalize_span(pred_location_text)

            if sample.expected_location is not None:
                loc_support += 1
                # Normalized sub-span containment
                is_subspan_match = bool(
                    norm_pred_loc
                    and (
                        norm_pred_loc == norm_exp_loc
                        or norm_exp_loc in norm_pred_loc
                        or norm_pred_loc in norm_exp_loc
                    )
                )
                if is_subspan_match:
                    loc_subspan_tp += 1
                else:
                    loc_subspan_fn += 1
                    if norm_pred_loc:
                        loc_subspan_fp += 1
                    mismatches.append({
                        "sample_id": sample.sample_id,
                        "type": "location_subspan_mismatch",
                        "expected": sample.expected_location,
                        "predicted": pred_location_text,
                    })

                # Exact normalized span match
                is_exact_match = bool(norm_pred_loc and norm_pred_loc == norm_exp_loc)
                if is_exact_match:
                    loc_exact_tp += 1
                else:
                    loc_exact_fn += 1
                    if norm_pred_loc:
                        loc_exact_fp += 1
            else:
                # Negative sample for location
                if not norm_pred_loc:
                    loc_subspan_tn += 1
                    loc_exact_tn += 1
                else:
                    loc_subspan_fp += 1
                    loc_exact_fp += 1
                    mismatches.append({
                        "sample_id": sample.sample_id,
                        "type": "location_false_positive",
                        "expected": None,
                        "predicted": pred_location_text,
                    })

            # ------------------------------------------------------------------
            # 2. Joint Entity Matching (Type + Span)
            # ------------------------------------------------------------------
            exp_entities = list(sample.expected_entities)
            joint_support += len(exp_entities)

            # Register expected types in per_type_counts
            for exp in exp_entities:
                if exp.type not in per_type_counts:
                    per_type_counts[exp.type] = {"tp": 0, "fp": 0, "fn": 0, "support": 0}
                per_type_counts[exp.type]["support"] += 1

            matched_exp_joint: set[int] = set()
            for pred in pred_entities:
                p_text = normalize_span(pred.get("text"))
                p_type = pred.get("type", "")

                if p_type not in per_type_counts:
                    per_type_counts[p_type] = {"tp": 0, "fp": 0, "fn": 0, "support": 0}

                match_found = False
                for idx, exp in enumerate(exp_entities):
                    if idx in matched_exp_joint:
                        continue
                    e_text = normalize_span(exp.text)
                    # Joint match: text overlap/exact + compatible/exact type
                    text_match = (p_text == e_text) or (e_text in p_text) or (p_text in e_text)
                    type_match = (p_type == exp.type) or (
                        p_type in ("LOCATION", "LANDMARK", "FACILITY", "ROAD")
                        and exp.type in ("LOCATION", "LANDMARK", "FACILITY", "ROAD")
                    )
                    if text_match and type_match:
                        matched_exp_joint.add(idx)
                        joint_tp += 1
                        per_type_counts[exp.type]["tp"] += 1
                        match_found = True
                        break

                if not match_found:
                    joint_fp += 1
                    per_type_counts[p_type]["fp"] += 1

            unmatched_exp_joint = len(exp_entities) - len(matched_exp_joint)
            joint_fn += unmatched_exp_joint
            for idx, exp in enumerate(exp_entities):
                if idx not in matched_exp_joint:
                    per_type_counts[exp.type]["fn"] += 1

            # ------------------------------------------------------------------
            # 3. Span-Only Entity Matching (ignoring type)
            # ------------------------------------------------------------------
            span_support += len(exp_entities)
            matched_exp_span: set[int] = set()
            for pred in pred_entities:
                p_text = normalize_span(pred.get("text"))
                match_found = False
                for idx, exp in enumerate(exp_entities):
                    if idx in matched_exp_span:
                        continue
                    e_text = normalize_span(exp.text)
                    if (p_text == e_text) or (e_text in p_text) or (p_text in e_text):
                        matched_exp_span.add(idx)
                        span_tp += 1
                        match_found = True
                        break
                if not match_found:
                    span_fp += 1

            span_fn += len(exp_entities) - len(matched_exp_span)

        elapsed = time.perf_counter() - t_start

        # Package location subspan metrics (normalized sub-span containment)
        subspan_prec = calculate_precision(loc_subspan_tp, loc_subspan_fp)
        subspan_rec = calculate_recall(loc_subspan_tp, loc_subspan_fn)
        subspan_f1 = calculate_f1(subspan_prec, subspan_rec)
        loc_subspan_metrics = SpanMetrics(
            matching_rule="normalized sub-span containment",
            tp=loc_subspan_tp,
            fp=loc_subspan_fp,
            fn=loc_subspan_fn,
            tn=loc_subspan_tn,
            precision=subspan_prec,
            recall=subspan_rec,
            f1=subspan_f1,
            support=loc_support,
        )

        # Package location exact normalized metrics
        exact_prec = calculate_precision(loc_exact_tp, loc_exact_fp)
        exact_rec = calculate_recall(loc_exact_tp, loc_exact_fn)
        exact_f1 = calculate_f1(exact_prec, exact_rec)
        loc_exact_metrics = SpanMetrics(
            matching_rule="exact_normalized",
            tp=loc_exact_tp,
            fp=loc_exact_fp,
            fn=loc_exact_fn,
            tn=loc_exact_tn,
            precision=exact_prec,
            recall=exact_rec,
            f1=exact_f1,
            support=loc_support,
        )

        # Package joint entity metrics
        j_prec = calculate_precision(joint_tp, joint_fp)
        j_rec = calculate_recall(joint_tp, joint_fn)
        j_f1 = calculate_f1(j_prec, j_rec)
        joint_metrics = SpanMetrics(
            matching_rule="Joint span + taxonomy type match (greedy 1-to-1 alignment)",
            tp=joint_tp,
            fp=joint_fp,
            fn=joint_fn,
            tn=0,
            precision=j_prec,
            recall=j_rec,
            f1=j_f1,
            support=joint_support,
        )

        # Package span-only entity metrics
        s_prec = calculate_precision(span_tp, span_fp)
        s_rec = calculate_recall(span_tp, span_fn)
        s_f1 = calculate_f1(s_prec, s_rec)
        span_metrics = SpanMetrics(
            matching_rule="Span-only match ignoring entity category (greedy 1-to-1 alignment)",
            tp=span_tp,
            fp=span_fp,
            fn=span_fn,
            tn=0,
            precision=s_prec,
            recall=s_rec,
            f1=s_f1,
            support=span_support,
        )

        # Package per-entity-type metrics
        per_type_objs: dict[str, SpanMetrics] = {}
        for ent_type, c in sorted(per_type_counts.items()):
            tp_c = c["tp"]
            fp_c = c["fp"]
            fn_c = c["fn"]
            supp_c = c["support"]
            p_c = calculate_precision(tp_c, fp_c)
            r_c = calculate_recall(tp_c, fn_c)
            f_c = calculate_f1(p_c, r_c)
            per_type_objs[ent_type] = SpanMetrics(
                matching_rule=f"Joint type={ent_type} and span match",
                tp=tp_c,
                fp=fp_c,
                fn=fn_c,
                tn=0,
                precision=p_c,
                recall=r_c,
                f1=f_c,
                support=supp_c,
            )

        return EntityEvaluationResult(
            fixture_name=fixture_name,
            sample_count=len(dataset),
            positive_samples=n_pos,
            negative_samples=n_neg,
            location_subspan_metrics=loc_subspan_metrics,
            location_exact_metrics=loc_exact_metrics,
            joint_entity_metrics=joint_metrics,
            span_only_entity_metrics=span_metrics,
            per_entity_type_metrics=per_type_objs,
            elapsed_seconds=elapsed,
            mismatches=mismatches,
        )
