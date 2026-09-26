"""
Karen's Ear — Confidence & Quality Control Engine.

Step 4 of the ML pipeline (architecture/ml-pipeline.md Section 4).
Responsible for:
1. Validating and extracting component-level confidence signals in [0.0, 1.0].
2. Aggregating component confidences into an overall ML confidence via a weighted harmonic mean.
3. Deterministically resolving pipeline operational status (SUCCESS, PARTIAL, FAILED, NEEDS_REVIEW).
4. Providing transparent, auditable quality breakdowns without fabricating missing confidence.

ARCHITECTURAL SPECIFICATION & WEIGHT POLICY NOTICE:
---------------------------------------------------
- The project architecture (architecture/ml-pipeline.md Section 4.2) specifies that
  Overall Model Confidence is calculated as the "weighted harmonic mean of component confidences."
- HOWEVER, component weights were NOT architecturally specified in repo ADRs, contracts, or schemas.
- As an explicit, documented implementation decision, this engine defines a provisional baseline:
    DEFAULT_CONFIDENCE_WEIGHTS = {
        "incident_type": 0.30,      # Core hazard identification facet
        "urgency": 0.25,            # Operational time-criticality facet
        "location": 0.20,           # Physical grounding facet
        "people_at_risk": 0.15,     # Direct human vulnerability indicator
        "required_response": 0.10,  # Tactical resource assignment indicator
    }
- These weights are fully configurable via MLConfig, constructor overrides, and per-call arguments.
- Embeddings are explicitly EXCLUDED from harmonic mean aggregation as dense vectors have no
  intrinsic confidence score (Feature 8 / ADR-001).
- Proxy confidence != calibrated probability; overall ML confidence != backend priority score.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.config import (
    DEFAULT_CONFIDENCE_WEIGHTS,
    ComponentResult,
    MLConfig,
    get_ml_config,
)
from ml.exceptions import MLConfigurationError, MLInputError
from ml.logging_utils import get_ml_logger

logger = get_ml_logger("ml.confidence")


# ==============================================================================
# Confidence Contract Validation Helpers
# ==============================================================================

def validate_confidence_value(conf: Any, component_name: str = "component") -> float | None:
    """
    Validates a confidence value against the strict confidence contract:
    - Must be None (when undetermined / not applicable) or a float in [0.0, 1.0].
    - Explicitly rejects booleans, strings, NaN, infinity, and out-of-range numbers.
    """
    if conf is None:
        return None

    # Python booleans are instances of int; reject explicitly
    if isinstance(conf, bool):
        raise MLInputError(
            f"Confidence for '{component_name}' must be numeric or None, got bool: {conf!r}"
        )

    if not isinstance(conf, (int, float)):
        raise MLInputError(
            f"Confidence for '{component_name}' must be numeric or None, got {type(conf).__name__}: {conf!r}"
        )

    val = float(conf)
    if math.isnan(val) or math.isinf(val):
        raise MLInputError(
            f"Confidence for '{component_name}' cannot be NaN or infinity, got: {conf}"
        )

    if not (0.0 <= val <= 1.0):
        raise MLInputError(
            f"Confidence for '{component_name}' must be bounded in [0.0, 1.0], got: {conf}"
        )

    return val


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class ComponentConfidenceDetail:
    """
    Detailed audit information for an individual component's confidence contribution.
    Provides complete transparency into whether a component contributed, its status,
    its applied weight, and any diagnostic warnings.
    """

    name: str
    confidence: float | None
    weight: float
    status: str = "SUCCESS"  # SUCCESS, PARTIAL, FAILED, NEEDS_REVIEW, UNAVAILABLE, SKIPPED
    included: bool = True
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Converts into a structured audit dictionary for serialization."""
        res: dict[str, Any] = {
            "confidence": self.confidence,
            "weight": self.weight,
            "status": self.status,
            "included": self.included,
        }
        if self.reason:
            res["reason"] = self.reason
        if self.warnings:
            res["warnings"] = list(self.warnings)
        return res


@dataclass
class ConfidenceResult:
    """
    Standardized typed result emitted by ConfidenceEngine.
    Combines the aggregated overall ML confidence signal, individual component
    breakdown, deterministic operational status, and traceability diagnostics.
    """

    overall_confidence: float | None  # Bounded strictly in [0.0, 1.0], or None if no evidence
    status: str  # SUCCESS, PARTIAL, FAILED, NEEDS_REVIEW
    needs_review: bool  # True if overall_confidence < threshold or review triggered
    components: dict[str, ComponentConfidenceDetail] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    method: str = "weighted_harmonic_mean_v1"
    review_threshold: float = 0.60

    def to_dict(self) -> dict[str, Any]:
        """
        Converts to a comprehensive quality and audit report.
        Exposes full explainability matching Step 11 of the specification.
        """
        return {
            "overall_confidence": self.overall_confidence,
            "status": self.status,
            "needs_review": self.needs_review,
            "components": {
                name: detail.to_dict() for name, detail in self.components.items()
            },
            "warnings": list(self.warnings),
            "method": self.method,
            "review_threshold": self.review_threshold,
        }

    def to_canonical_ml_confidence(self) -> dict[str, Any]:
        """
        Converts to the canonical ml_confidence structure defined in
        gemini.md Section 6.3, docs/api-contract.md, and frontend/src/types/incident.ts:
        {
            "overall": float | None,
            "components": {
                "incident_type": float | None,
                "urgency": float | None,
                "location": float | None, ...
            }
        }
        """
        return {
            "overall": self.overall_confidence,
            "components": {
                name: detail.confidence for name, detail in self.components.items()
            },
        }

    def to_component_result(self) -> ComponentResult:
        """Converts into a standardized internal ComponentResult."""
        return ComponentResult(
            component="confidence_engine",
            status=self.status,
            data=self.to_dict(),
            confidence=self.overall_confidence,
            warnings=list(self.warnings),
        )


# ==============================================================================
# Confidence Engine
# ==============================================================================

class ConfidenceEngine:
    """
    Confidence & Quality Control Engine for Karen's Ear ML Pipeline.

    Step 4 of the ML pipeline (architecture/ml-pipeline.md Section 4).
    Aggregates component-level confidence signals into an overall ML confidence
    via a weighted harmonic mean and resolves deterministic operational status.
    """

    def __init__(
        self,
        config: MLConfig | None = None,
        weights: dict[str, float] | None = None,
        review_threshold: float | None = None,
    ) -> None:
        """
        Initializes ConfidenceEngine with configuration and component weights.

        Args:
            config: Central ML configuration instance (default: get_ml_config()).
            weights: Optional dictionary of component weights overriding config defaults.
            review_threshold: Optional threshold below which status becomes NEEDS_REVIEW.
        """
        self.config = config or get_ml_config()
        raw_weights = weights if weights is not None else self.config.confidence_weights
        self.weights = self._validate_and_copy_weights(raw_weights)
        self.review_threshold = (
            float(review_threshold)
            if review_threshold is not None
            else float(self.config.confidence_review_threshold)
        )
        if not (0.0 <= self.review_threshold <= 1.0):
            raise MLConfigurationError(
                f"review_threshold must be bounded in [0.0, 1.0], got {self.review_threshold}"
            )

    @staticmethod
    def _validate_and_copy_weights(weights: dict[str, float]) -> dict[str, float]:
        """Validates that weights is a non-empty mapping with strictly positive numbers."""
        if not isinstance(weights, dict):
            raise MLConfigurationError(f"weights must be a dict, got {type(weights).__name__}")
        if not weights:
            raise MLConfigurationError("weights dictionary cannot be empty")

        validated: dict[str, float] = {}
        for k, v in weights.items():
            if not isinstance(k, str) or not k.strip():
                raise MLConfigurationError("Weight component names must be non-empty strings")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise MLConfigurationError(
                    f"Weight for '{k}' must be a positive number, got {type(v).__name__}: {v!r}"
                )
            val = float(v)
            if math.isnan(val) or math.isinf(val) or val <= 0.0:
                raise MLConfigurationError(
                    f"Weight for '{k}' must be strictly positive (> 0.0), got: {v}"
                )
            validated[k.strip()] = val
        return validated

    @staticmethod
    def compute_weighted_harmonic_mean(
        items: Sequence[tuple[str, float, float]],
    ) -> float | None:
        """
        Computes the weighted harmonic mean for a sequence of (name, confidence, weight) tuples.

        Formula:
            C_overall = (Σ w_i) / (Σ (w_i / c_i))
            where 0 < c_i <= 1.0

        Mathematical Properties & Edge Cases:
        - If items is empty: returns None.
        - If any c_i == 0.0: mathematically lim_{c_i -> 0+} H = 0.0. Returns 0.0
          strictly without ZeroDivisionError.
        - If all c_i == 1.0: returns 1.0.
        - Weights are relative: scaling all weights by a constant factor does not alter the result.
        - Result is rounded to 4 decimal places.
        """
        if not items:
            return None

        # Exact mathematical limit check: any zero confidence collapses harmonic mean to 0.0
        if any(conf == 0.0 for _, conf, _ in items):
            return 0.0

        sum_weights = sum(w for _, _, w in items)
        if sum_weights <= 0.0:
            return None

        sum_weighted_inverses = sum(w / conf for _, conf, w in items)
        if sum_weighted_inverses <= 0.0:
            return None

        result = sum_weights / sum_weighted_inverses
        # Guard against minor floating point overflow / precision quirks
        result = max(0.0, min(1.0, result))
        return round(result, 4)

    def _extract_component_info(
        self,
        name: str,
        value: Any,
        weight: float,
    ) -> ComponentConfidenceDetail:
        """
        Extracts confidence, operational status, warnings, and payload from diverse
        component input types (dataclasses, ComponentResult, dicts, primitives, None).
        """
        if value is None:
            return ComponentConfidenceDetail(
                name=name,
                confidence=None,
                weight=weight,
                status="UNAVAILABLE",
                included=False,
                reason="component not provided / unavailable",
            )

        if isinstance(value, bool):
            raise MLInputError(
                f"Confidence for '{name}' must be numeric or None, got bool: {value!r}"
            )

        # Raw numeric confidence shorthand
        if isinstance(value, (int, float)):
            conf = validate_confidence_value(value, component_name=name)
            return ComponentConfidenceDetail(
                name=name,
                confidence=conf,
                weight=weight,
                status="SUCCESS",
                included=True,
            )

        # Standard ComponentResult container
        if isinstance(value, ComponentResult):
            conf = validate_confidence_value(value.confidence, component_name=name)
            status = value.status or "SUCCESS"
            warnings = list(value.warnings)
            raw_data = dict(value.data)

            if status == "FAILED":
                return ComponentConfidenceDetail(
                    name=name,
                    confidence=conf,
                    weight=weight,
                    status="FAILED",
                    included=False,
                    reason="component status is FAILED",
                    warnings=warnings,
                    raw_data=raw_data,
                )

            if conf is None:
                return ComponentConfidenceDetail(
                    name=name,
                    confidence=None,
                    weight=weight,
                    status=status,
                    included=False,
                    reason="confidence is null / not applicable",
                    warnings=warnings,
                    raw_data=raw_data,
                )

            return ComponentConfidenceDetail(
                name=name,
                confidence=conf,
                weight=weight,
                status=status,
                included=True,
                warnings=warnings,
                raw_data=raw_data,
            )

        # Objects with to_component_result() method (e.g. ClassificationResult, UrgencyResult)
        if hasattr(value, "to_component_result") and callable(value.to_component_result):
            comp_res = value.to_component_result()
            return self._extract_component_info(name, comp_res, weight)

        # LocationEntityResult or objects with location child object
        if hasattr(value, "location") and hasattr(value.location, "confidence"):
            status = getattr(value, "processing_status", "SUCCESS")
            warnings = list(getattr(value, "warnings", []))
            loc_conf = getattr(value.location, "confidence", None)
            conf = validate_confidence_value(loc_conf, component_name=name)

            if status == "FAILED":
                return ComponentConfidenceDetail(
                    name=name,
                    confidence=conf,
                    weight=weight,
                    status="FAILED",
                    included=False,
                    reason="component status is FAILED",
                    warnings=warnings,
                )

            included = conf is not None
            reason = None if included else "confidence is null / not applicable"
            return ComponentConfidenceDetail(
                name=name,
                confidence=conf,
                weight=weight,
                status=status,
                included=included,
                reason=reason,
                warnings=warnings,
            )

        # Dictionary input (e.g. canonical schema fragments or custom test dicts)
        if isinstance(value, dict):
            status = value.get("processing_status", value.get("status", "SUCCESS"))
            warnings = list(value.get("warnings", []))
            raw_conf = value.get("confidence")

            # Check if this is an envelope containing the field (e.g., {"incident_type": {...}})
            if raw_conf is None and name in value and isinstance(value[name], dict):
                inner = value[name]
                raw_conf = inner.get("confidence")
                if "status" in inner or "processing_status" in inner:
                    status = inner.get("processing_status", inner.get("status", status))

            conf = validate_confidence_value(raw_conf, component_name=name)
            if status == "FAILED":
                return ComponentConfidenceDetail(
                    name=name,
                    confidence=conf,
                    weight=weight,
                    status="FAILED",
                    included=False,
                    reason="component status is FAILED",
                    warnings=warnings,
                    raw_data=dict(value),
                )

            included = conf is not None
            reason = None if included else "confidence is null / not applicable"
            return ComponentConfidenceDetail(
                name=name,
                confidence=conf,
                weight=weight,
                status=status,
                included=included,
                reason=reason,
                warnings=warnings,
                raw_data=dict(value),
            )

        # Array of items (e.g., required_response list)
        if isinstance(value, list):
            confidences: list[float] = []
            for idx, item in enumerate(value):
                item_conf: Any = None
                if isinstance(item, dict):
                    item_conf = item.get("confidence")
                elif hasattr(item, "confidence"):
                    item_conf = getattr(item, "confidence")

                if item_conf is not None:
                    validated_item_conf = validate_confidence_value(
                        item_conf, component_name=f"{name}[{idx}]"
                    )
                    if validated_item_conf is not None:
                        confidences.append(validated_item_conf)

            avg_conf = (
                round(sum(confidences) / len(confidences), 4) if confidences else None
            )
            included = avg_conf is not None
            reason = None if included else "confidence is null / no response items with confidence"
            return ComponentConfidenceDetail(
                name=name,
                confidence=avg_conf,
                weight=weight,
                status="SUCCESS",
                included=included,
                reason=reason,
                raw_data={"items": value},
            )

        # Direct confidence attribute on object
        if hasattr(value, "confidence"):
            status = getattr(value, "processing_status", getattr(value, "status", "SUCCESS"))
            warnings = list(getattr(value, "warnings", []))
            conf = validate_confidence_value(getattr(value, "confidence"), component_name=name)
            if status == "FAILED":
                return ComponentConfidenceDetail(
                    name=name,
                    confidence=conf,
                    weight=weight,
                    status="FAILED",
                    included=False,
                    reason="component status is FAILED",
                    warnings=warnings,
                )
            included = conf is not None
            reason = None if included else "confidence is null / not applicable"
            return ComponentConfidenceDetail(
                name=name,
                confidence=conf,
                weight=weight,
                status=status,
                included=included,
                reason=reason,
                warnings=warnings,
            )

        raise MLInputError(
            f"Unsupported component value type for '{name}': {type(value).__name__}"
        )

    def _resolve_status(
        self,
        overall_confidence: float | None,
        components: dict[str, ComponentConfidenceDetail],
        has_conflict: bool,
        review_threshold: float,
        warnings: list[str],
    ) -> tuple[str, bool]:
        """
        Deterministically resolves pipeline operational status and needs_review flag.

        Precedence Hierarchy:
        1. FAILED:
           Triggered when all provided inference components failed, or zero meaningful
           inferences succeeded (e.g. infrastructure crash or complete runtime failure).
        2. NEEDS_REVIEW:
           Triggered when overall confidence < review_threshold (0.60) OR when critical
           conflicts/contradictions are detected. Human safety requires dispatcher review.
        3. PARTIAL:
           Triggered when one or more components failed extraction, but remaining evidence
           achieves overall confidence >= review_threshold. Usable intelligence is preserved.
        4. SUCCESS:
           Triggered when all components executed without failure and overall confidence >= review_threshold.
        """
        # Distinguish failed vs active/successful components
        failed_components = [c for c in components.values() if c.status == "FAILED"]
        successful_components = [
            c
            for c in components.values()
            if c.status in ("SUCCESS", "PARTIAL", "NEEDS_REVIEW")
        ]

        # 1. Total infrastructure or component failure
        if not successful_components and failed_components:
            warnings.append("All inference components failed; pipeline status marked FAILED.")
            return "FAILED", True

        if not successful_components and not failed_components:
            # Empty inputs or all components unavailable
            warnings.append("No active inference components provided or available; status marked FAILED.")
            return "FAILED", True

        # 2. Critical contradiction or conflict detected
        if has_conflict:
            warnings.append(
                "Critical conflict detected among extracted components; routed to NEEDS_REVIEW."
            )
            return "NEEDS_REVIEW", True

        # 3. Overall confidence is below the review threshold
        if overall_confidence is not None and overall_confidence < review_threshold:
            warnings.append(
                f"Overall ML confidence ({overall_confidence:.4f}) is below review threshold "
                f"({review_threshold:.2f}); routed to NEEDS_REVIEW."
            )
            for fc in failed_components:
                warnings.append(f"Component '{fc.name}' failed extraction.")
            return "NEEDS_REVIEW", True

        # 4. Overall confidence is sufficient (>= review_threshold)
        if overall_confidence is not None and overall_confidence >= review_threshold:
            if failed_components:
                # Partial failure occurred, but surviving components are confident
                for fc in failed_components:
                    warnings.append(
                        f"Component '{fc.name}' failed extraction; pipeline degraded gracefully to PARTIAL."
                    )
                return "PARTIAL", False
            return "SUCCESS", False

        # 5. Overall confidence is None (no component produced numeric confidence)
        if failed_components:
            warnings.append(
                "Component extraction failures detected and no numeric confidence available; status PARTIAL."
            )
            return "PARTIAL", True

        warnings.append(
            "No numeric confidence available to aggregate; routed to NEEDS_REVIEW for operator verification."
        )
        return "NEEDS_REVIEW", True

    def calculate(
        self,
        incident_type: Any = None,
        urgency: Any = None,
        location: Any = None,
        people_at_risk: Any = None,
        required_response: Any = None,
        entities: Any = None,
        embedding: Any = None,
        has_conflict: bool = False,
        override_weights: dict[str, float] | None = None,
        **extra_components: Any,
    ) -> ConfidenceResult:
        """
        Calculates overall ML confidence and operational quality signals across components.

        Args:
            incident_type: Classification result, ComponentResult, dict, or float.
            urgency: Urgency result, ComponentResult, dict, or float.
            location: Location result, ComponentResult, dict, or float.
            people_at_risk: People at risk result, ComponentResult, dict, or float.
            required_response: Response extraction result, list of dicts, or float.
            entities: Named entities list (optional auxiliary evidence).
            embedding: Raw dense embedding vector or EmbeddingResult.
                       Explicitly EXCLUDED from harmonic mean aggregation.
            has_conflict: Boolean flag indicating contradictory signals.
            override_weights: Optional dictionary overriding component weights for this call.
            **extra_components: Additional component results.

        Returns:
            ConfidenceResult with overall confidence, component details, status, and audit notes.
        """
        start_time = time.perf_counter()
        active_weights = (
            self._validate_and_copy_weights(override_weights)
            if override_weights is not None
            else dict(self.weights)
        )

        all_inputs: dict[str, Any] = {
            "incident_type": incident_type,
            "urgency": urgency,
            "location": location,
            "people_at_risk": people_at_risk,
            "required_response": required_response,
        }
        all_inputs.update(extra_components)

        parsed_components: dict[str, ComponentConfidenceDetail] = {}
        pipeline_warnings: list[str] = []

        # 1. Parse standard confidence-bearing components
        for name, val in all_inputs.items():
            comp_weight = active_weights.get(name, 0.0)
            detail = self._extract_component_info(name, val, comp_weight)

            # Check if component is in active weights
            if name not in active_weights:
                detail.included = False
                detail.reason = f"component '{name}' is not in configured confidence weights"

            parsed_components[name] = detail
            if detail.warnings:
                pipeline_warnings.extend(detail.warnings)

        # 2. Explicitly handle embeddings (Feature 8): Exclude from harmonic mean
        if embedding is not None:
            emb_status = "SUCCESS"
            emb_warnings: list[str] = []
            if isinstance(embedding, ComponentResult):
                emb_status = embedding.status
                emb_warnings = list(embedding.warnings)

            parsed_components["embeddings"] = ComponentConfidenceDetail(
                name="embeddings",
                confidence=None,
                weight=0.0,
                status=emb_status,
                included=False,
                reason="embeddings provide dense representation and similarity; excluded from confidence aggregation",
                warnings=emb_warnings,
            )
            if emb_warnings:
                pipeline_warnings.extend(emb_warnings)

        # 3. Optional auxiliary entities mention check
        if entities is not None:
            parsed_components["entities"] = ComponentConfidenceDetail(
                name="entities",
                confidence=None,
                weight=0.0,
                status="SUCCESS",
                included=False,
                reason="auxiliary entity mentions; excluded from primary harmonic mean",
            )

        # 4. Collect included components for weighted harmonic mean
        harmonic_items: list[tuple[str, float, float]] = []
        for name, detail in parsed_components.items():
            if detail.included and detail.confidence is not None and detail.weight > 0.0:
                harmonic_items.append((name, detail.confidence, detail.weight))

        # Check for zero confidence pull
        zero_pull = any(conf == 0.0 for _, conf, _ in harmonic_items)
        if zero_pull:
            zero_names = [name for name, conf, _ in harmonic_items if conf == 0.0]
            pipeline_warnings.append(
                f"Zero confidence in component(s) {zero_names}; overall harmonic mean collapses to 0.0."
            )

        # 5. Compute overall weighted harmonic mean
        overall_confidence = self.compute_weighted_harmonic_mean(harmonic_items)

        # 6. Resolve deterministic status and review requirement
        status, needs_review = self._resolve_status(
            overall_confidence=overall_confidence,
            components=parsed_components,
            has_conflict=has_conflict,
            review_threshold=self.review_threshold,
            warnings=pipeline_warnings,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Structured logging adheres to safety guidelines (no raw report text logged)
        logger.info(
            "Confidence & quality evaluation completed",
            extra={
                "overall_confidence": overall_confidence,
                "status": status,
                "needs_review": needs_review,
                "included_components": [name for name, _, _ in harmonic_items],
                "latency_ms": round(latency_ms, 2),
            },
        )

        return ConfidenceResult(
            overall_confidence=overall_confidence,
            status=status,
            needs_review=needs_review,
            components=parsed_components,
            warnings=pipeline_warnings,
            method="weighted_harmonic_mean_v1",
            review_threshold=self.review_threshold,
        )

    def calculate_from_component_results(
        self,
        results: Sequence[ComponentResult],
        has_conflict: bool = False,
        override_weights: dict[str, float] | None = None,
    ) -> ConfidenceResult:
        """
        Convenience adapter to calculate overall confidence from a sequence of ComponentResult objects.
        Maps canonical pipeline component names to confidence engine fields.
        """
        mapping: dict[str, Any] = {}
        for r in results:
            if not isinstance(r, ComponentResult):
                continue
            if r.component == "classification":
                mapping["incident_type"] = r
            elif r.component == "urgency":
                mapping["urgency"] = r
            elif r.component == "location_and_entities":
                mapping["location"] = r
            elif r.component == "people_at_risk":
                mapping["people_at_risk"] = r
            elif r.component == "required_response":
                mapping["required_response"] = r
            elif r.component == "embeddings":
                mapping["embedding"] = r
            else:
                mapping[r.component] = r

        return self.calculate(
            has_conflict=has_conflict,
            override_weights=override_weights,
            **mapping,
        )

    def calculate_from_ml_output(
        self,
        ml_output: dict[str, Any],
        has_conflict: bool = False,
        override_weights: dict[str, float] | None = None,
    ) -> ConfidenceResult:
        """
        Calculates confidence and quality signals directly from a canonical ML output dictionary
        conforming to ml/schemas/incident_output.json.
        """
        if not isinstance(ml_output, dict):
            raise MLInputError(f"ml_output must be a dict, got {type(ml_output).__name__}")

        return self.calculate(
            incident_type=ml_output.get("incident_type"),
            urgency=ml_output.get("urgency"),
            location=ml_output.get("location"),
            people_at_risk=ml_output.get("people_at_risk"),
            required_response=ml_output.get("required_response"),
            entities=ml_output.get("entities"),
            embedding=ml_output.get("embedding"),
            has_conflict=has_conflict,
            override_weights=override_weights,
        )


# ==============================================================================
# Public Functional Interface
# ==============================================================================

def calculate_confidence(
    incident_type: Any = None,
    urgency: Any = None,
    location: Any = None,
    people_at_risk: Any = None,
    required_response: Any = None,
    entities: Any = None,
    embedding: Any = None,
    has_conflict: bool = False,
    config: MLConfig | None = None,
    weights: dict[str, float] | None = None,
    review_threshold: float | None = None,
    **extra_components: Any,
) -> ConfidenceResult:
    """
    Public functional interface to evaluate confidence and quality signals.
    """
    engine = ConfidenceEngine(
        config=config,
        weights=weights,
        review_threshold=review_threshold,
    )
    return engine.calculate(
        incident_type=incident_type,
        urgency=urgency,
        location=location,
        people_at_risk=people_at_risk,
        required_response=required_response,
        entities=entities,
        embedding=embedding,
        has_conflict=has_conflict,
        **extra_components,
    )
