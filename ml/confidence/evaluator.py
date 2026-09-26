"""
Karen's Ear — Confidence & Quality Control Benchmark Evaluator.

Evaluates the ConfidenceEngine against core mathematical properties, behavioral
invariants, degradation scenarios, and threshold gating:
1. Formula Correctness: Verified against hand-calculated mathematical harmonic mean ground truths.
2. Zero-Confidence Invariant: Verified that zero-confidence collapses overall confidence to 0.0 without ZeroDivisionError.
3. Monotonicity Invariants: Increasing confidence increases overall; decreasing decreases overall.
4. Weight Sensitivity: Altering component weights shifts overall harmonic mean in the exact expected direction.
5. Invariant Invariance to Weight Scale: Multiplying all weights by scalar k preserves exact output.
6. Status Precedence Resolution: Strict verification of FAILED > NEEDS_REVIEW > PARTIAL > SUCCESS.
7. Threshold Boundary Verification: Strict verification of behaviour at < 0.60, == 0.60, and > 0.60.
8. Safe Degradation: Verifies that component extraction failure degrades gracefully to PARTIAL without crash.
9. Embedding Exclusion: Verifies that raw embedding vectors do not corrupt the harmonic mean.
10. Deterministic Reproducibility: Verifies identical repeated runs produce bitwise identical outputs.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from ml.confidence.confidence_engine import (
    ConfidenceEngine,
    ConfidenceResult,
    calculate_confidence,
)
from ml.config import ComponentResult, MLConfig


@dataclass
class ConfidenceEvaluationReport:
    """Standardized report emitted by ConfidenceEvaluator."""

    formula_correctness_passed: bool
    zero_collapse_passed: bool
    monotonicity_passed: bool
    weight_sensitivity_passed: bool
    weight_scale_invariance_passed: bool
    status_precedence_passed: bool
    threshold_boundary_passed: bool
    graceful_degradation_passed: bool
    embedding_exclusion_passed: bool
    determinism_passed: bool
    total_checks_run: int
    mean_latency_ms: float
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed_all_invariants(self) -> bool:
        """Returns True if all behavioral invariants and validation checks passed."""
        return (
            self.formula_correctness_passed
            and self.zero_collapse_passed
            and self.monotonicity_passed
            and self.weight_sensitivity_passed
            and self.weight_scale_invariance_passed
            and self.status_precedence_passed
            and self.threshold_boundary_passed
            and self.graceful_degradation_passed
            and self.embedding_exclusion_passed
            and self.determinism_passed
        )

    def summary(self) -> str:
        """Formats the evaluation results into a clean engineering summary."""
        lines = [
            "==================================================================",
            " Karen's Ear -- Feature 9: Confidence & Quality Engine Evaluation",
            " Method: Weighted Harmonic Mean (Provisional Baseline Weights)",
            "==================================================================",
            f" Total Invariant Checks Executed : {self.total_checks_run}",
            f" Mean Calculation Latency (CPU)  : {self.mean_latency_ms:.3f} ms",
            "",
            "--- Mathematical & Behavioral Invariants ---",
            f" 1. Formula Correctness (Hand-Solved) : {'PASSED' if self.formula_correctness_passed else 'FAILED'}",
            f" 2. Zero-Confidence Collapse (c=0->0) : {'PASSED' if self.zero_collapse_passed else 'FAILED'}",
            f" 3. Monotonicity (c_i up => C up)     : {'PASSED' if self.monotonicity_passed else 'FAILED'}",
            f" 4. Weight Sensitivity (w_i shift)    : {'PASSED' if self.weight_sensitivity_passed else 'FAILED'}",
            f" 5. Weight Scale Invariance (k*w)     : {'PASSED' if self.weight_scale_invariance_passed else 'FAILED'}",
            f" 6. Status Precedence Hierarchy       : {'PASSED' if self.status_precedence_passed else 'FAILED'}",
            f" 7. Review Threshold Boundary (0.60)  : {'PASSED' if self.threshold_boundary_passed else 'FAILED'}",
            f" 8. Graceful Degradation (PARTIAL)   : {'PASSED' if self.graceful_degradation_passed else 'FAILED'}",
            f" 9. Embedding Exclusion Invariant     : {'PASSED' if self.embedding_exclusion_passed else 'FAILED'}",
            f" 10. Deterministic Reproducibility     : {'PASSED' if self.determinism_passed else 'FAILED'}",
            "",
            f" Overall Evaluation Status: {'ALL INVARIANTS PASSED' if self.passed_all_invariants else 'VERIFICATION FAILED'}",
            "==================================================================",
        ]
        return "\n".join(lines)


class ConfidenceEvaluator:
    """
    Automated verification suite for the Confidence & Quality Control Engine.
    Executes rigorous invariant testing against hand-calculated analytical solutions.
    """

    def __init__(self, config: MLConfig | None = None) -> None:
        self.config = config or MLConfig()
        self.engine = ConfidenceEngine(config=self.config)

    def evaluate(self) -> ConfidenceEvaluationReport:
        """Runs the complete suite of mathematical and behavioral verifications."""
        details: dict[str, Any] = {}
        latencies: list[float] = []
        checks_count = 0

        # 1. Formula Correctness (Against Hand-Calculated Ground Truths)
        t0 = time.perf_counter()
        # Case 1A: Equal weights: c=[0.6, 0.9], w=[1.0, 1.0]
        # H = 2 / (1/0.6 + 1/0.9) = 2 / (1.666667 + 1.111111) = 2 / 2.777778 = 0.7200
        h1 = self.engine.compute_weighted_harmonic_mean([("a", 0.6, 1.0), ("b", 0.9, 1.0)])
        c1a_pass = h1 == 0.72

        # Case 1B: Unequal weights: c=[0.6, 0.9], w=[0.7, 0.3]
        # H = 1.0 / (0.7/0.6 + 0.3/0.9) = 1.0 / (1.166667 + 0.333333) = 1.0 / 1.5 = 0.6667
        h2 = self.engine.compute_weighted_harmonic_mean([("a", 0.6, 0.7), ("b", 0.9, 0.3)])
        c1b_pass = h2 == 0.6667

        # Case 1C: Single item: c=0.85, w=0.5 -> 0.85
        h3 = self.engine.compute_weighted_harmonic_mean([("a", 0.85, 0.5)])
        c1c_pass = h3 == 0.85

        # Case 1D: All 1.0 -> 1.0
        h4 = self.engine.compute_weighted_harmonic_mean([("a", 1.0, 0.3), ("b", 1.0, 0.7)])
        c1d_pass = h4 == 1.0

        formula_correctness = c1a_pass and c1b_pass and c1c_pass and c1d_pass
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 4
        details["formula_correctness"] = {
            "c1a_equal_weights": {"actual": h1, "expected": 0.72, "passed": c1a_pass},
            "c1b_unequal_weights": {"actual": h2, "expected": 0.6667, "passed": c1b_pass},
            "c1c_single_item": {"actual": h3, "expected": 0.85, "passed": c1c_pass},
            "c1d_perfect_confidence": {"actual": h4, "expected": 1.0, "passed": c1d_pass},
        }

        # 2. Zero-Confidence Collapse Invariant
        t0 = time.perf_counter()
        h_zero = self.engine.compute_weighted_harmonic_mean([("a", 0.9, 0.5), ("b", 0.0, 0.5)])
        res_zero = self.engine.calculate(incident_type=0.9, urgency=0.0)
        zero_collapse_passed = (
            h_zero == 0.0
            and res_zero.overall_confidence == 0.0
            and res_zero.status == "NEEDS_REVIEW"
            and res_zero.needs_review is True
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 2
        details["zero_collapse"] = {
            "h_zero": h_zero,
            "overall_confidence": res_zero.overall_confidence,
            "status": res_zero.status,
            "passed": zero_collapse_passed,
        }

        # 3. Monotonicity Invariants
        t0 = time.perf_counter()
        res_base = self.engine.calculate(incident_type=0.70, urgency=0.70)
        res_higher = self.engine.calculate(incident_type=0.85, urgency=0.70)
        res_lower = self.engine.calculate(incident_type=0.55, urgency=0.70)

        monotonicity_passed = (
            res_higher.overall_confidence is not None
            and res_base.overall_confidence is not None
            and res_lower.overall_confidence is not None
            and res_higher.overall_confidence > res_base.overall_confidence > res_lower.overall_confidence
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 3
        details["monotonicity"] = {
            "base": res_base.overall_confidence,
            "higher": res_higher.overall_confidence,
            "lower": res_lower.overall_confidence,
            "passed": monotonicity_passed,
        }

        # 4. Weight Sensitivity Invariant
        t0 = time.perf_counter()
        # Incident type = 0.50 (low), Urgency = 0.90 (high)
        # Increasing weight of incident type should pull overall downward
        res_heavy_low = self.engine.calculate(
            incident_type=0.50,
            urgency=0.90,
            override_weights={"incident_type": 0.80, "urgency": 0.20},
        )
        # Increasing weight of urgency should pull overall upward
        res_heavy_high = self.engine.calculate(
            incident_type=0.50,
            urgency=0.90,
            override_weights={"incident_type": 0.20, "urgency": 0.80},
        )
        weight_sensitivity_passed = (
            res_heavy_low.overall_confidence is not None
            and res_heavy_high.overall_confidence is not None
            and res_heavy_low.overall_confidence < res_heavy_high.overall_confidence
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 2
        details["weight_sensitivity"] = {
            "heavy_low_conf_result": res_heavy_low.overall_confidence,
            "heavy_high_conf_result": res_heavy_high.overall_confidence,
            "passed": weight_sensitivity_passed,
        }

        # 5. Weight Scale Invariance
        t0 = time.perf_counter()
        res_w1 = self.engine.calculate(
            incident_type=0.75,
            urgency=0.85,
            override_weights={"incident_type": 0.30, "urgency": 0.25},
        )
        res_w10 = self.engine.calculate(
            incident_type=0.75,
            urgency=0.85,
            override_weights={"incident_type": 3.0, "urgency": 2.5},
        )
        weight_scale_invariance_passed = res_w1.overall_confidence == res_w10.overall_confidence
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 2
        details["weight_scale_invariance"] = {
            "w_base": res_w1.overall_confidence,
            "w_scaled_x10": res_w10.overall_confidence,
            "passed": weight_scale_invariance_passed,
        }

        # 6. Status Precedence Hierarchy
        t0 = time.perf_counter()
        # SUCCESS: High confidence, no failures
        res_succ = self.engine.calculate(incident_type=0.90, urgency=0.85)
        # NEEDS_REVIEW: Low confidence (< 0.60), no failures
        res_nr1 = self.engine.calculate(incident_type=0.50, urgency=0.55)
        # PARTIAL: High confidence surviving, one failure
        res_part = self.engine.calculate(
            incident_type=0.90,
            urgency=0.85,
            location=ComponentResult(component="location_and_entities", status="FAILED"),
        )
        # NEEDS_REVIEW: Low confidence surviving + one failure
        res_nr2 = self.engine.calculate(
            incident_type=0.45,
            urgency=0.50,
            location=ComponentResult(component="location_and_entities", status="FAILED"),
        )
        # FAILED: All components failed
        res_fail = self.engine.calculate(
            incident_type=ComponentResult(component="classification", status="FAILED"),
            urgency=ComponentResult(component="urgency", status="FAILED"),
        )

        status_precedence_passed = (
            res_succ.status == "SUCCESS"
            and not res_succ.needs_review
            and res_nr1.status == "NEEDS_REVIEW"
            and res_nr1.needs_review
            and res_part.status == "PARTIAL"
            and not res_part.needs_review
            and res_nr2.status == "NEEDS_REVIEW"
            and res_nr2.needs_review
            and res_fail.status == "FAILED"
            and res_fail.needs_review
            and res_fail.overall_confidence is None
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 5
        details["status_precedence"] = {
            "success_case": res_succ.status,
            "needs_review_low_conf": res_nr1.status,
            "partial_high_conf": res_part.status,
            "needs_review_failure_plus_low_conf": res_nr2.status,
            "all_failed_case": res_fail.status,
            "passed": status_precedence_passed,
        }

        # 7. Threshold Boundary Verification (review_threshold = 0.60)
        t0 = time.perf_counter()
        res_below = self.engine.calculate(incident_type=0.59, urgency=0.59)
        res_exact = self.engine.calculate(incident_type=0.60, urgency=0.60)
        res_above = self.engine.calculate(incident_type=0.61, urgency=0.61)

        threshold_boundary_passed = (
            res_below.status == "NEEDS_REVIEW"
            and res_below.needs_review is True
            and res_exact.status == "SUCCESS"
            and res_exact.needs_review is False
            and res_above.status == "SUCCESS"
            and res_above.needs_review is False
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 3
        details["threshold_boundary"] = {
            "below_0.60": {"conf": res_below.overall_confidence, "status": res_below.status},
            "exact_0.60": {"conf": res_exact.overall_confidence, "status": res_exact.status},
            "above_0.60": {"conf": res_above.overall_confidence, "status": res_above.status},
            "passed": threshold_boundary_passed,
        }

        # 8. Graceful Degradation
        t0 = time.perf_counter()
        comp_class = ComponentResult(component="classification", status="SUCCESS", confidence=0.88)
        comp_urg = ComponentResult(component="urgency", status="SUCCESS", confidence=0.82)
        comp_loc_fail = ComponentResult(
            component="location_and_entities",
            status="FAILED",
            warnings=["Gazetteer timeout"],
        )

        res_deg = self.engine.calculate_from_component_results(
            [comp_class, comp_urg, comp_loc_fail]
        )
        graceful_degradation_passed = (
            res_deg.status == "PARTIAL"
            and not res_deg.needs_review
            and res_deg.overall_confidence is not None
            and res_deg.overall_confidence > 0.80
            and res_deg.components["location"].status == "FAILED"
            and not res_deg.components["location"].included
            and any("Gazetteer timeout" in w for w in res_deg.warnings)
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 2
        details["graceful_degradation"] = {
            "status": res_deg.status,
            "overall_confidence": res_deg.overall_confidence,
            "passed": graceful_degradation_passed,
        }

        # 9. Embedding Exclusion Invariant
        t0 = time.perf_counter()
        mock_embedding = [0.05] * 384
        res_with_emb = self.engine.calculate(
            incident_type=0.80,
            urgency=0.80,
            embedding=mock_embedding,
        )
        res_without_emb = self.engine.calculate(
            incident_type=0.80,
            urgency=0.80,
        )
        embedding_exclusion_passed = (
            res_with_emb.overall_confidence == res_without_emb.overall_confidence
            and "embeddings" in res_with_emb.components
            and not res_with_emb.components["embeddings"].included
            and res_with_emb.components["embeddings"].weight == 0.0
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 2
        details["embedding_exclusion"] = {
            "with_embedding": res_with_emb.overall_confidence,
            "without_embedding": res_without_emb.overall_confidence,
            "passed": embedding_exclusion_passed,
        }

        # 10. Determinism (100 repetitions)
        t0 = time.perf_counter()
        first_run = self.engine.calculate(
            incident_type=0.85,
            urgency=0.75,
            location={"text": "Patia", "confidence": 0.65},
            people_at_risk={"count": 2, "confidence": 0.80},
        )
        first_dict = first_run.to_dict()

        determinism_passed = True
        for _ in range(50):
            rep = self.engine.calculate(
                incident_type=0.85,
                urgency=0.75,
                location={"text": "Patia", "confidence": 0.65},
                people_at_risk={"count": 2, "confidence": 0.80},
            )
            if rep.to_dict() != first_dict:
                determinism_passed = False
                break

        latencies.append((time.perf_counter() - t0) * 1000.0)
        checks_count += 50
        details["determinism"] = {"passed": determinism_passed}

        mean_latency = sum(latencies) / len(latencies) if latencies else 0.0

        return ConfidenceEvaluationReport(
            formula_correctness_passed=formula_correctness,
            zero_collapse_passed=zero_collapse_passed,
            monotonicity_passed=monotonicity_passed,
            weight_sensitivity_passed=weight_sensitivity_passed,
            weight_scale_invariance_passed=weight_scale_invariance_passed,
            status_precedence_passed=status_precedence_passed,
            threshold_boundary_passed=threshold_boundary_passed,
            graceful_degradation_passed=graceful_degradation_passed,
            embedding_exclusion_passed=embedding_exclusion_passed,
            determinism_passed=determinism_passed,
            total_checks_run=checks_count,
            mean_latency_ms=round(mean_latency, 3),
            details=details,
        )


def run_confidence_evaluation() -> ConfidenceEvaluationReport:
    """Convenience functional interface to execute the full evaluation suite."""
    evaluator = ConfidenceEvaluator()
    return evaluator.evaluate()


if __name__ == "__main__":
    report = run_confidence_evaluation()
    print(report.summary())
