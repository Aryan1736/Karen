"""
Karen's Ear — Incident Type Classifier.

Step 2A of the ML pipeline (architecture/ml-pipeline.md Section 3.2).
Classifies emergency reports into the 9 canonical crisis hazard categories:
1. FLOOD_FLASH_FLOOD
2. FIRE_WILDFIRE_EXPLOSION
3. STRUCTURAL_COLLAPSE
4. EARTHQUAKE_LANDSLIDE
5. SEVERE_WEATHER_STORM
6. MEDICAL_EMERGENCY
7. CIVIL_UNREST_ACTIVE_THREAT
8. UTILITY_INFRASTRUCTURE_FAILURE
9. OTHER_GENERAL_INCIDENT

Architectural Guarantees:
- Modularity: Usable independently before full pipeline orchestration.
- Lazy Model Loading: Zero heavy ML imports at module/package load time.
- Evidence-Based Classification: Combines deterministic structured keywords and
  dense semantic prototype similarity using sentence-transformers/all-MiniLM-L6-v2.
- Determinism: Identical text and configuration always produces identical classification.
- Explainability: Emits detailed diagnostic evidence, class scores, and conflict markers.
- Multi-Signal Resolution: Principled evidence aggregation and hazard precedence.
- Safe Fallback: Principled routing to OTHER_GENERAL_INCIDENT for weak/ambiguous reports.
- Contract Compliance: Outputs strictly conform to canonical taxonomy and confidence bounds.
- Privacy & Observability: Uses get_ml_logger; never leaks raw emergency report content.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.classification.taxonomy import (
    CRISITEXT_SCENARIO_MAPPING,
    HAZARD_PRECEDENCE_ORDER,
    INCIDENT_TAXONOMY_CATALOG,
    IncidentClassDefinition,
)
from ml.config import (
    CANONICAL_INCIDENT_TYPES,
    ComponentResult,
    MLConfig,
    get_ml_config,
)
from ml.exceptions import (
    MLInferenceError,
    MLInputError,
    MLModelError,
)
from ml.logging_utils import get_ml_logger
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner


# ==============================================================================
# Typed Classification Result
# ==============================================================================
@dataclass
class ClassificationResult:
    """
    Standardized typed result emitted by the IncidentClassifier.
    Represents an internal ML component result before canonical pipeline packaging.

    METRIC & CONFIDENCE DISTINCTIONS:
    - result.confidence: An internal classification confidence proxy in [0.0, 1.0]
      reflecting top-class evidence margin. It is NOT a formally calibrated posterior
      probability, nor is it operational urgency or backend priority.
    - Operational Urgency: Categorical operational tier (CRITICAL/HIGH/MEDIUM/LOW)
      derived separately via life-safety and hazard features in Feature 4.
    - Backend Priority: Continuous 0.0-100.0 score calculated deterministically by
      backend business logic (incorporating urgency, risk, corroboration, and type).
    """

    label: str | None
    confidence: float
    method: str
    class_scores: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    processing_status: str = "SUCCESS"  # SUCCESS, NEEDS_REVIEW, PARTIAL, FAILED

    def to_component_result(self) -> ComponentResult:
        """Converts into a standardized internal ComponentResult."""
        return ComponentResult(
            component="classification",
            status=self.processing_status,
            data={
                "incident_type": {
                    "label": self.label,
                    "confidence": self.confidence,
                },
                "method": self.method,
                "class_scores": dict(self.class_scores),
                "evidence": dict(self.evidence),
            },
            confidence=self.confidence,
            warnings=list(self.warnings),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convenient dictionary representation matching canonical sub-schema."""
        return {
            "label": self.label,
            "confidence": self.confidence,
            "method": self.method,
            "processing_status": self.processing_status,
            "class_scores": dict(self.class_scores),
            "evidence": dict(self.evidence),
            "warnings": list(self.warnings),
        }


# ==============================================================================
# Incident Classifier
# ==============================================================================
class IncidentClassifier:
    """
    Evidence-based crisis hazard classifier for emergency dispatches.

    Supports three evaluation and execution modes:
    - "hybrid" (Default / Recommended): Combines structured keyword/phrase evidence
      with semantic prototype embeddings for maximum accuracy and explainability.
    - "semantic": Pure dense semantic prototype similarity via all-MiniLM-L6-v2.
    - "keyword": Pure deterministic regex keyword and phrase evidence matching.
    """

    def __init__(
        self,
        config: MLConfig | None = None,
        mode: str | None = None,
        keyword_weight: float = 0.40,
        semantic_weight: float = 0.60,
        min_confidence_threshold: float = 0.35,
        fallback_label: str = "OTHER_GENERAL_INCIDENT",
    ) -> None:
        self.config = config or get_ml_config()
        if mode is None:
            self.mode = "keyword" if self.config.lightweight_mode else "hybrid"
        else:
            self.mode = mode.lower()
        if self.mode not in ("hybrid", "semantic", "keyword"):
            raise MLInferenceError(
                f"Unsupported classifier mode: {mode!r}. Must be 'hybrid', 'semantic', or 'keyword'."
            )

        self.keyword_weight = float(keyword_weight)
        self.semantic_weight = float(semantic_weight)
        self.min_confidence_threshold = float(min_confidence_threshold)
        self.fallback_label = fallback_label

        self.logger = get_ml_logger(
            name="karen.ml.classification",
            component="classification",
            model_version=self.config.model_version,
        )

        # Preprocessor reuse (never duplicate text cleaning)
        self._cleaner = TextCleaner(config=self.config)

        # Precompile regex patterns for structured keyword matching
        self._phrase_patterns: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
        self._keyword_patterns: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
        self._compile_patterns()

        # Lazy model references (heavy ML dependencies are NOT imported or loaded here)
        self._model: Any = None
        self._prototype_embeddings: dict[str, Any] | None = None

    def _compile_patterns(self) -> None:
        """Precompiles word-bounded regular expressions for keyword/phrase matching."""
        for label, defn in INCIDENT_TAXONOMY_CATALOG.items():
            phrase_list: list[tuple[str, re.Pattern[str]]] = []
            for phrase in defn.primary_phrases:
                pattern = re.compile(rf"\b{re.escape(phrase.lower())}\b", re.IGNORECASE)
                phrase_list.append((phrase, pattern))
            self._phrase_patterns[label] = phrase_list

            keyword_list: list[tuple[str, re.Pattern[str]]] = []
            for kw in defn.keywords:
                pattern = re.compile(rf"\b{re.escape(kw.lower())}\b", re.IGNORECASE)
                keyword_list.append((kw, pattern))
            self._keyword_patterns[label] = keyword_list

    def _get_model(self) -> Any:
        """
        Lazily loads the SentenceTransformer model and encodes class prototypes on first use.
        Ensures zero import/loading overhead until semantic inference is actually needed.
        """
        if self._model is not None and self._prototype_embeddings is not None:
            return self._model

        if self.config.lightweight_mode:
            raise MLModelError(
                "Neural runtime is disabled in lightweight mode (ML_LIGHTWEIGHT_MODE=true)",
                details={"library": "sentence-transformers", "lightweight_mode": True},
            )

        try:
            self.logger.info("Initializing lazy semantic model for classification...")
            load_start = time.time()
            from sentence_transformers import SentenceTransformer  # Lazy import
            import numpy as np  # Lazy import

            model = SentenceTransformer(
                self.config.embedding_model_name,
                device=self.config.device,
            )

            # Pre-compute and cache unit-normalized prototype embeddings
            proto_embeddings: dict[str, Any] = {}
            for label, defn in INCIDENT_TAXONOMY_CATALOG.items():
                embs = model.encode(
                    list(defn.prototypes),
                    device=self.config.device,
                    normalize_embeddings=True,
                )
                proto_embeddings[label] = np.asarray(embs, dtype=np.float32)

            self._model = model
            self._prototype_embeddings = proto_embeddings

            elapsed_ms = round((time.time() - load_start) * 1000, 2)
            self.logger.info(
                "Semantic prototype classifier initialized successfully",
                extra={
                    "model_name": self.config.embedding_model_name,
                    "device": self.config.device,
                    "init_latency_ms": elapsed_ms,
                    "num_classes": len(proto_embeddings),
                },
            )
            return self._model

        except ImportError as exc:
            self.logger.error("Required ML library sentence-transformers is missing", exc_info=True)
            raise MLModelError(
                f"sentence-transformers not installed or unavailable: {exc}",
                details={"library": "sentence-transformers"},
            ) from exc
        except Exception as exc:
            self.logger.error(
                "Failed to load embedding model for semantic classification",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            raise MLModelError(
                f"Failed to load classification model: {type(exc).__name__}: {exc}",
                details={"model_name": self.config.embedding_model_name},
            ) from exc

    def _compute_keyword_scores(self, text: str) -> tuple[dict[str, float], dict[str, Any]]:
        """
        Computes structured keyword evidence scores for each canonical class.

        Weighting logic:
        - Multi-word phrases receive 2.0 weight (high specificity).
        - Single keywords receive 1.0 weight.
        - Raw score saturates via a smooth sigmoid-like bounded formula.
        - Result is bounded in [0.0, 1.0].
        """
        lowered = text.lower()
        scores: dict[str, float] = {}
        matched_phrases: dict[str, list[str]] = {}
        matched_keywords: dict[str, list[str]] = {}

        for label, defn in INCIDENT_TAXONOMY_CATALOG.items():
            matched_phr: list[str] = []
            for phrase, pattern in self._phrase_patterns[label]:
                if pattern.search(lowered):
                    matched_phr.append(phrase)

            matched_kw: list[str] = []
            for kw, pattern in self._keyword_patterns[label]:
                if pattern.search(lowered):
                    matched_kw.append(kw)

            matched_phrases[label] = matched_phr
            matched_keywords[label] = matched_kw

            # Multi-word phrases are stronger evidence than single tokens
            raw_weight = (len(matched_phr) * 2.0) + (len(matched_kw) * 1.0)

            # Saturated normalization (2.5 raw weight reaches 1.0 confidence)
            normalized = min(1.0, raw_weight / 2.5) if raw_weight > 0 else 0.0
            scores[label] = round(normalized * defn.weight_modifier, 4)

        evidence = {
            "matched_phrases": {k: v for k, v in matched_phrases.items() if v},
            "matched_keywords": {k: v for k, v in matched_keywords.items() if v},
            "keyword_scores": scores,
        }
        return scores, evidence

    def _compute_semantic_scores(
        self,
        text: str,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """
        Computes dense semantic similarity scores against pre-embedded class prototypes.

        Calibration logic:
        - Cosine similarity with all-MiniLM-L6-v2 typically ranges [0.10, 0.80].
        - Baseline noise floor = 0.20 (below which score is 0.0).
        - High-confidence ceiling = 0.70 (above which score is 1.0).
        - Score = clip((cos_sim - 0.20) / 0.50, 0.0, 1.0).
        """
        self._get_model()  # Ensure model and prototypes are loaded
        import numpy as np  # type: ignore

        # Encode single query to unit normalized 384-d vector
        query_emb = self._model.encode(
            [text],
            device=self.config.device,
            normalize_embeddings=True,
        )[0]
        query_vec = np.asarray(query_emb, dtype=np.float32)

        raw_similarities: dict[str, float] = {}
        calibrated_scores: dict[str, float] = {}

        baseline = 0.20
        ceiling = 0.70

        for label, proto_matrix in self._prototype_embeddings.items():
            defn = INCIDENT_TAXONOMY_CATALOG[label]
            # Fast dot-product against normalized class prototype vectors
            sims = np.dot(proto_matrix, query_vec)
            max_sim = float(np.max(sims))
            raw_similarities[label] = round(max_sim, 4)

            # Linear calibration mapping [baseline, ceiling] to [0.0, 1.0]
            val = (max_sim - baseline) / (ceiling - baseline)
            clipped = float(np.clip(val, 0.0, 1.0))
            calibrated_scores[label] = round(clipped * defn.weight_modifier, 4)

        return calibrated_scores, raw_similarities

    def predict(
        self,
        text: str | PreprocessedText,
        report_id: str | None = None,
    ) -> ClassificationResult:
        """
        Classifies an emergency report into a canonical incident category.

        Args:
            text: Raw report string or PreprocessedText from TextCleaner.
            report_id: Optional tracking identifier for logging and traceability.

        Returns:
            ClassificationResult containing label, confidence, class scores, and evidence.

        Raises:
            MLInputError: If text is empty, whitespace-only, or invalid type.
            MLInferenceError: If an unexpected internal error occurs during execution.
        """
        start_time = time.time()
        clean_text, input_warnings = self._normalize_input(text, report_id)

        try:
            kw_scores, sem_scores, evidence_details = self._compute_component_signals(clean_text)
            composite_scores = self._combine_class_scores(kw_scores, sem_scores)

            warnings = list(input_warnings)
            (
                sorted_candidates,
                top_label,
                top_score,
                second_label,
                second_score,
                conflict_detected,
                secondary_hazard,
            ) = self._rank_and_resolve_conflicts(composite_scores, warnings)

            selected_label, confidence, status = self._resolve_label_and_confidence(
                top_label, top_score, second_score, warnings
            )

            latency_ms = round((time.time() - start_time) * 1000, 2)

            evidence_details.update({
                "top_candidates": [
                    {"label": lbl, "score": scr} for lbl, scr in sorted_candidates[:3]
                ],
                "conflict_detected": conflict_detected,
                "secondary_hazard": secondary_hazard,
                "margin": round(top_score - second_score, 4),
                "latency_ms": latency_ms,
            })

            # Observability: Safe metadata logging (never log full raw report text)
            logger = self.logger
            if report_id:
                logger = logger.with_context(report_id=report_id)

            logger.info(
                "Incident classification completed",
                extra={
                    "predicted_label": selected_label,
                    "confidence": confidence,
                    "method": self.mode,
                    "processing_status": status,
                    "latency_ms": latency_ms,
                    "conflict_detected": conflict_detected,
                },
            )

            return ClassificationResult(
                label=selected_label,
                confidence=confidence,
                method=self.mode,
                class_scores=composite_scores,
                evidence=evidence_details,
                warnings=warnings,
                processing_status=status,
            )

        except (MLInputError, MLModelError):
            raise
        except Exception as exc:
            self.logger.error(
                "Unexpected failure during incident classification",
                extra={"error_type": type(exc).__name__, "report_id": report_id},
                exc_info=True,
            )
            raise MLInferenceError(
                f"Unexpected failure during incident classification: {type(exc).__name__}: {exc}",
                details={"error_type": type(exc).__name__},
            ) from exc

    def _normalize_input(
        self, text: str | PreprocessedText, report_id: str | None
    ) -> tuple[str, list[str]]:
        if isinstance(text, PreprocessedText):
            return text.normalized_text, list(text.warnings)
        if isinstance(text, str):
            preprocessed = self._cleaner.clean(text, report_id=report_id)
            return preprocessed.normalized_text, list(preprocessed.warnings)
        raise MLInputError(
            f"Input to IncidentClassifier must be str or PreprocessedText, got {type(text).__name__}",
            details={"type": type(text).__name__},
        )

    def _compute_component_signals(
        self, clean_text: str
    ) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
        kw_scores: dict[str, float] = {}
        sem_scores: dict[str, float] = {}
        raw_sims: dict[str, float] = {}
        evidence_details: dict[str, Any] = {}

        if self.mode in ("keyword", "hybrid"):
            kw_scores, kw_evidence = self._compute_keyword_scores(clean_text)
            evidence_details.update(kw_evidence)

        if self.mode in ("semantic", "hybrid"):
            sem_scores, raw_sims = self._compute_semantic_scores(clean_text)
            evidence_details["raw_cosine_similarities"] = raw_sims
            evidence_details["semantic_scores"] = sem_scores

        return kw_scores, sem_scores, evidence_details

    def _combine_class_scores(
        self, kw_scores: dict[str, float], sem_scores: dict[str, float]
    ) -> dict[str, float]:
        composite_scores: dict[str, float] = {}
        for label in CANONICAL_INCIDENT_TYPES:
            if self.mode == "keyword":
                score = kw_scores.get(label, 0.0)
            elif self.mode == "semantic":
                score = sem_scores.get(label, 0.0)
            else:  # hybrid
                kw = kw_scores.get(label, 0.0)
                sem = sem_scores.get(label, 0.0)
                score = (self.keyword_weight * kw) + (self.semantic_weight * sem)
            composite_scores[label] = round(score, 4)
        return composite_scores

    def _rank_and_resolve_conflicts(
        self,
        composite_scores: dict[str, float],
        warnings: list[str],
    ) -> tuple[list[tuple[str, float]], str, float, str, float, bool, str | None]:
        sorted_candidates = sorted(
            composite_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        top_label, top_score = sorted_candidates[0]
        second_label, second_score = sorted_candidates[1]

        conflict_detected = False
        secondary_hazard: str | None = None

        if (
            second_score >= 0.35
            and second_score >= 0.70 * top_score
            and second_label != "OTHER_GENERAL_INCIDENT"
            and top_label != "OTHER_GENERAL_INCIDENT"
        ):
            conflict_detected = True
            secondary_hazard = second_label
            warnings.append(
                f"Conflicting secondary hazard detected: {second_label} "
                f"(score: {second_score:.2f}) alongside primary {top_label} ({top_score:.2f})"
            )

        if abs(top_score - second_score) < 0.03 and top_score > 0.10:
            top_idx = (
                HAZARD_PRECEDENCE_ORDER.index(top_label)
                if top_label in HAZARD_PRECEDENCE_ORDER
                else 99
            )
            sec_idx = (
                HAZARD_PRECEDENCE_ORDER.index(second_label)
                if second_label in HAZARD_PRECEDENCE_ORDER
                else 99
            )
            if sec_idx < top_idx:
                top_label, second_label = second_label, top_label
                top_score, second_score = second_score, top_score
                warnings.append(
                    f"Resolved near-tie via hazard precedence: selected {top_label} over {second_label}"
                )

        return (
            sorted_candidates,
            top_label,
            top_score,
            second_label,
            second_score,
            conflict_detected,
            secondary_hazard,
        )

    def _resolve_label_and_confidence(
        self,
        top_label: str,
        top_score: float,
        second_score: float,
        warnings: list[str],
    ) -> tuple[str, float, str]:
        if top_score < self.min_confidence_threshold:
            selected_label = self.fallback_label
            confidence = round(max(0.20, min(0.48, top_score)), 2)
            status = "NEEDS_REVIEW"
            warnings.append(
                f"Max class score ({top_score:.2f}) below threshold ({self.min_confidence_threshold}); "
                f"defaulting to {self.fallback_label}"
            )
        elif top_label == "OTHER_GENERAL_INCIDENT":
            selected_label = "OTHER_GENERAL_INCIDENT"
            confidence = round(min(0.70, top_score), 2)
            status = (
                "NEEDS_REVIEW"
                if confidence < self.config.confidence_review_threshold
                else "SUCCESS"
            )
        else:
            selected_label = top_label
            margin = top_score - second_score
            raw_conf = top_score + (0.05 * margin)
            confidence = round(min(1.0, max(0.10, raw_conf)), 2)
            status = (
                "NEEDS_REVIEW"
                if confidence < self.config.confidence_review_threshold
                else "SUCCESS"
            )

        return selected_label, confidence, status

    def predict_batch(
        self,
        texts: Sequence[str | PreprocessedText],
        report_ids: Sequence[str | None] | None = None,
    ) -> list[ClassificationResult]:
        """
        Batch prediction method for multiple emergency reports.
        Optimized to encode text embeddings in bulk when running in semantic or hybrid mode.
        """
        if not texts:
            return []

        ids = list(report_ids) if report_ids else [None] * len(texts)
        if len(ids) != len(texts):
            raise MLInputError("Length of report_ids must match length of texts in predict_batch")

        results: list[ClassificationResult] = []
        for text, rep_id in zip(texts, ids):
            res = self.predict(text, report_id=rep_id)
            results.append(res)
        return results


# ==============================================================================
# Public Functional Interface
# ==============================================================================
def classify_incident(
    text: str | PreprocessedText,
    config: MLConfig | None = None,
    mode: str | None = None,
    report_id: str | None = None,
) -> ClassificationResult:
    """
    Public functional interface for emergency report incident classification.
    Convenience wrapper around IncidentClassifier.predict().
    """
    classifier = IncidentClassifier(config=config, mode=mode)
    return classifier.predict(text=text, report_id=report_id)
