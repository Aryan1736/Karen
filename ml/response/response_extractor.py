"""
Karen's Ear — Required-Response Extractor.

Step 2E of the ML pipeline (architecture/ml-pipeline.md Section 3.6 and gemini.md Section 6.2).
Extracts zero, one, or multiple required emergency response categories from emergency dispatch text:
1. SEARCH_AND_RESCUE
2. MEDICAL_EMS
3. FIRE_HAZMAT
4. POLICE_SECURITY
5. PUBLIC_WORKS_UTILITY

CRITICAL ARCHITECTURAL PRINCIPLE:
Required-response extraction is ADVISORY ML OUTPUT.
It must NOT directly determine final operational priority, incident ranking,
dispatch ordering, emergency contact, or backend response orchestration.
It answers: "What response categories appear relevant from the report?"

Key Guarantees:
- Multi-label: Emits zero, one, or multiple canonical response categories.
- Strict canonical taxonomy: Only the 5 canonical categories are allowed.
- Evidence-based: Evaluates strong, supporting, negative, and negation patterns.
- Negation handling: Suppresses categories that are explicitly negated.
- Uncertainty preservation: Decreases confidence for hedged, suspected, or ambiguous reports.
- Deterministic: Output ordering and confidence values are 100% reproducible.
- Explainable: Rich internal evidence for auditing without exposing raw distress text in logs.
- Privacy-safe: Structured logging without dumping raw citizen text.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.config import (
    CANONICAL_RESPONSE_TYPES,
    ComponentResult,
    MLConfig,
    get_ml_config,
)
from ml.exceptions import MLInferenceError, MLInputError
from ml.logging_utils import get_ml_logger
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner
from ml.response.taxonomy import (
    RESPONSE_TAXONOMY_CATALOG,
    UNCERTAINTY_PATTERN,
    ResponseCategoryDefinition,
    get_response_definition,
    is_canonical_response_type,
)


# ==============================================================================
# Public Typed Output Structures
# ==============================================================================

@dataclass
class ResponseNeed:
    """
    Individual required response need matching ml/schemas/incident_output.json.
    """

    type: str  # One of CANONICAL_RESPONSE_TYPES
    confidence: float | None = None  # Bounded strictly in [0.0, 1.0]

    def to_canonical_dict(self) -> dict[str, Any]:
        """Serializes to dictionary adhering strictly to canonical schema."""
        return {
            "type": self.type,
            "confidence": self.confidence,
        }


@dataclass
class ResponseEvidence:
    """
    Internal explainability and audit evidence for an extracted response category.
    Not exposed through the canonical schema.
    """

    category: str
    matched_patterns: list[str] = field(default_factory=list)
    evidence_tier: str = "NONE"  # "STRONG", "SUPPORTING", "NONE", "NEGATED", "NEGATIVE_REJECTION"
    uncertainty_detected: bool = False
    uncertainty_tokens: list[str] = field(default_factory=list)
    negation_detected: bool = False
    negative_rejection_detected: bool = False
    confidence: float | None = None


@dataclass
class ResponseExtractionResult:
    """
    Standardized typed result emitted by RequiredResponseExtractor.
    """

    responses: list[ResponseNeed] = field(default_factory=list)
    evidence: dict[str, ResponseEvidence] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    processing_status: str = "SUCCESS"  # "SUCCESS", "PARTIAL", "NEEDS_REVIEW", "FAILED"

    def to_canonical_list(self) -> list[dict[str, Any]]:
        """Returns the canonical array of response objects for incident_output.json."""
        return [r.to_canonical_dict() for r in self.responses]

    def to_component_result(self) -> ComponentResult:
        """Converts into a standardized internal ComponentResult."""
        confidences = [r.confidence for r in self.responses if r.confidence is not None]
        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else None
        return ComponentResult(
            component="required_response",
            status=self.processing_status,
            data={"required_response": self.to_canonical_list()},
            confidence=avg_conf,
            warnings=self.warnings,
        )


# ==============================================================================
# Helper Sentence / Clause Segmentation
# ==============================================================================

_CLAUSE_SPLIT_REGEX = re.compile(
    r"[,;:\n\r]|\b(?:but|however|although|though|whereas|yet|with\s+no|without\s+any)\b",
    re.IGNORECASE,
)


def _split_into_clauses(text: str) -> list[tuple[str, int, int]]:
    """
    Splits text into clauses, returning list of (clause_text, start_idx, end_idx).
    Enables local clause-level negation and uncertainty detection.
    """
    clauses: list[tuple[str, int, int]] = []
    last_end = 0

    for match in _CLAUSE_SPLIT_REGEX.finditer(text):
        start = last_end
        end = match.start()
        clause_str = text[start:end].strip()
        if clause_str:
            clauses.append((clause_str, start, end))
        last_end = match.end()

    rem = text[last_end:].strip()
    if rem:
        clauses.append((rem, last_end, len(text)))

    if not clauses:
        clauses.append((text, 0, len(text)))

    return clauses


# ==============================================================================
# Main Response Extractor
# ==============================================================================

class RequiredResponseExtractor:
    """
    Deterministic, evidence-based multi-label required-response extractor.
    Identifies zero, one, or multiple needed responder agencies from emergency dispatches.
    """

    def __init__(
        self,
        config: MLConfig | None = None,
        min_confidence_threshold: float = 0.50,
    ) -> None:
        self.config = config or get_ml_config()
        self.min_confidence_threshold = min_confidence_threshold
        self.logger = get_ml_logger(
            name="karen.ml.response",
            component="required_response",
        )
        self.text_cleaner = TextCleaner(self.config)

    def extract(
        self,
        text: str | PreprocessedText,
        report_id: str | None = None,
        incident_type: str | None = None,
        people_at_risk_count: int | None = None,
    ) -> ResponseExtractionResult:
        """
        Extracts required response categories from an emergency report.

        Args:
            text: Raw report string or PreprocessedText from TextCleaner.
            report_id: Optional tracking identifier for observability.
            incident_type: Optional classified crisis category (Feature 3 context).
            people_at_risk_count: Optional extracted people-at-risk count (Feature 4 context).

        Returns:
            ResponseExtractionResult containing canonical responses, explainable evidence,
            processing status, and diagnostic warnings.
        """
        start_time = time.perf_counter()
        warnings: list[str] = []

        # Step 1: Input Validation & Preprocessing
        if not isinstance(text, (str, PreprocessedText)):
            raise MLInputError(
                f"Input text must be str or PreprocessedText, received {type(text).__name__}",
                details={"type": type(text).__name__},
            )

        try:
            if isinstance(text, PreprocessedText):
                preprocessed = text
                warnings.extend(text.warnings)
            else:
                preprocessed = self.text_cleaner.clean(text, report_id=report_id)
                warnings.extend(preprocessed.warnings)

            clean_text = preprocessed.normalized_text
        except MLInputError as exc:
            self.logger.warning(
                f"Input error in RequiredResponseExtractor: {exc.message}",
                extra={"report_id": report_id},
            )
            return ResponseExtractionResult(
                responses=[],
                evidence={},
                warnings=[f"Input error: {exc.message}"],
                processing_status="PARTIAL",
            )
        except Exception as exc:
            self.logger.error(
                f"Unexpected preprocessing failure: {exc}",
                extra={"report_id": report_id},
            )
            return ResponseExtractionResult(
                responses=[],
                evidence={},
                warnings=[f"Preprocessing failure: {exc}"],
                processing_status="PARTIAL",
            )

        if not clean_text:
            return ResponseExtractionResult(
                responses=[],
                evidence={},
                warnings=["Empty input report text."],
                processing_status="PARTIAL",
            )

        try:
            clauses = _split_into_clauses(clean_text)
            detected_responses: list[ResponseNeed] = []
            audit_evidence: dict[str, ResponseEvidence] = {}

            # Step 2: Evaluate Each Canonical Category Independently
            for category in CANONICAL_RESPONSE_TYPES:
                cat_def = RESPONSE_TAXONOMY_CATALOG.get(category)
                if cat_def is None:
                    continue

                evidence_obj = self._evaluate_category(
                    category=category,
                    cat_def=cat_def,
                    clean_text=clean_text,
                    clauses=clauses,
                    incident_type=incident_type,
                    people_at_risk_count=people_at_risk_count,
                )
                audit_evidence[category] = evidence_obj

                if (
                    evidence_obj.confidence is not None
                    and evidence_obj.confidence >= self.min_confidence_threshold
                    and not evidence_obj.negation_detected
                    and not evidence_obj.negative_rejection_detected
                ):
                    detected_responses.append(
                        ResponseNeed(
                            type=category,
                            confidence=evidence_obj.confidence,
                        )
                    )

            # Step 3: Enforce Deterministic Canonical Ordering
            # Sort strictly by CANONICAL_RESPONSE_TYPES definition order
            detected_responses.sort(key=lambda r: CANONICAL_RESPONSE_TYPES.index(r.type))

            # Step 4: Observability (Privacy-safe structured logging)
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.logger.info(
                "Extracted required emergency responses",
                extra={
                    "report_id": report_id,
                    "response_types": [r.type for r in detected_responses],
                    "response_count": len(detected_responses),
                    "latency_ms": round(latency_ms, 2),
                },
            )

            return ResponseExtractionResult(
                responses=detected_responses,
                evidence=audit_evidence,
                warnings=warnings,
                processing_status="SUCCESS",
            )

        except (MLInputError, MLInferenceError):
            raise
        except Exception as exc:
            self.logger.error(
                f"Unexpected failure in RequiredResponseExtractor: {type(exc).__name__}: {exc}",
                extra={"report_id": report_id},
            )
            raise MLInferenceError(
                f"Required response extraction failed: {type(exc).__name__}: {exc}",
                details={"report_id": report_id},
            ) from exc

    def _evaluate_category(
        self,
        category: str,
        cat_def: ResponseCategoryDefinition,
        clean_text: str,
        clauses: list[tuple[str, int, int]],
        incident_type: str | None = None,
        people_at_risk_count: int | None = None,
    ) -> ResponseEvidence:
        """
        Evaluates evidence, negation, uncertainty, and negative rejections for a category.
        """
        evidence = ResponseEvidence(category=category)

        # 1. Identify Negative Rejection Spans (False-positive patterns)
        negative_spans: list[tuple[int, int]] = []
        for pat in cat_def.negative_patterns:
            for match in pat.finditer(clean_text):
                negative_spans.append((match.start(), match.end()))

        # 2. Identify Negation Matches
        negation_matches: list[str] = []
        for pat in cat_def.negation_patterns:
            for match in pat.finditer(clean_text):
                negation_matches.append(match.group(0))

        if negation_matches:
            evidence.negation_detected = True

        # 3. Find Strong Pattern Matches
        strong_matches: list[tuple[str, int, int]] = []
        for pat in cat_def.strong_patterns:
            for match in pat.finditer(clean_text):
                m_start, m_end = match.start(), match.end()
                # Check if this match overlaps ANY negative rejection span
                if any(max(m_start, neg_s) < min(m_end, neg_e) for neg_s, neg_e in negative_spans):
                    continue
                strong_matches.append((match.group(0), m_start, m_end))

        # 4. Find Supporting Pattern Matches
        supporting_matches: list[tuple[str, int, int]] = []
        for pat in cat_def.supporting_patterns:
            for match in pat.finditer(clean_text):
                m_start, m_end = match.start(), match.end()
                # Check if this match overlaps ANY negative rejection span
                if any(max(m_start, neg_s) < min(m_end, neg_e) for neg_s, neg_e in negative_spans):
                    continue
                # Do not duplicate strong matches
                if not any(s_start <= m_start and m_end <= s_end for _, s_start, s_end in strong_matches):
                    supporting_matches.append((match.group(0), m_start, m_end))

        # 5. Check if all activity is suppressed by negative pattern matches
        if not strong_matches and not supporting_matches and negative_spans:
            evidence.negative_rejection_detected = True
            evidence.confidence = None
            evidence.evidence_tier = "NEGATIVE_REJECTION"
            return evidence

        # 6. Check if category is negated
        if evidence.negation_detected:
            # Check if there is an explicit independent positive clause overriding negation
            has_independent_positive = False
            for match_text, m_start, m_end in strong_matches:
                match_clause = next((c[0] for c in clauses if c[1] <= m_start and m_end <= c[2]), clean_text)
                if not any(pat.search(match_clause) for pat in cat_def.negation_patterns):
                    has_independent_positive = True
                    break

            if not has_independent_positive:
                evidence.confidence = None
                evidence.evidence_tier = "NEGATED"
                return evidence

        # 7. Calculate Confidence & Evidence Tier
        if strong_matches:
            evidence.evidence_tier = "STRONG"
            evidence.matched_patterns = [m[0] for m in strong_matches]
            base_conf = cat_def.base_strong_confidence

            # Boost slightly if multiple independent strong patterns match
            if len(strong_matches) >= 2:
                base_conf = min(0.96, base_conf + 0.02)

            # Check for uncertainty markers qualifying the strong matches
            uncertainty_tokens: list[str] = []
            for match_text, m_start, m_end in strong_matches:
                # Examine a window around the match
                window_start = max(0, m_start - 35)
                window_end = min(len(clean_text), m_end + 35)
                window_text = clean_text[window_start:window_end]
                for u_match in UNCERTAINTY_PATTERN.finditer(window_text):
                    uncertainty_tokens.append(u_match.group(0))

            # Also check clause-level uncertainty
            if not uncertainty_tokens:
                for match_text, m_start, m_end in strong_matches:
                    match_clause = next((c[0] for c in clauses if c[1] <= m_start and m_end <= c[2]), "")
                    for u_match in UNCERTAINTY_PATTERN.finditer(match_clause):
                        uncertainty_tokens.append(u_match.group(0))

            if uncertainty_tokens:
                evidence.uncertainty_detected = True
                evidence.uncertainty_tokens = list(set(uncertainty_tokens))
                # Deduct uncertainty penalty
                base_conf = max(0.55, base_conf - 0.22)

            evidence.confidence = round(base_conf, 2)
            return evidence

        elif supporting_matches:
            evidence.evidence_tier = "SUPPORTING"
            evidence.matched_patterns = [m[0] for m in supporting_matches]
            base_conf = cat_def.base_supporting_confidence

            # If corroborated by Feature 3 incident_type, slightly reinforce
            if incident_type and self._is_corroborating_incident_type(category, incident_type):
                base_conf = min(0.85, base_conf + 0.08)

            # Check for uncertainty markers
            uncertainty_tokens = []
            for match_text, m_start, m_end in supporting_matches:
                window_start = max(0, m_start - 30)
                window_end = min(len(clean_text), m_end + 30)
                window_text = clean_text[window_start:window_end]
                for u_match in UNCERTAINTY_PATTERN.finditer(window_text):
                    uncertainty_tokens.append(u_match.group(0))

            if uncertainty_tokens:
                evidence.uncertainty_detected = True
                evidence.uncertainty_tokens = list(set(uncertainty_tokens))
                base_conf = max(0.50, base_conf - 0.18)

            evidence.confidence = round(base_conf, 2)
            return evidence

        else:
            # No evidence found
            evidence.evidence_tier = "NONE"
            evidence.confidence = None
            return evidence

    def _is_corroborating_incident_type(self, response_category: str, incident_type: str) -> bool:
        """Checks if a Feature 3 incident type aligns with the response category."""
        mapping = {
            "SEARCH_AND_RESCUE": ("STRUCTURAL_COLLAPSE", "FLOOD_FLASH_FLOOD", "EARTHQUAKE_LANDSLIDE"),
            "MEDICAL_EMS": ("MEDICAL_EMERGENCY",),
            "FIRE_HAZMAT": ("FIRE_WILDFIRE_EXPLOSION",),
            "POLICE_SECURITY": ("CIVIL_UNREST_ACTIVE_THREAT",),
            "PUBLIC_WORKS_UTILITY": ("UTILITY_INFRASTRUCTURE_FAILURE",),
        }
        return incident_type in mapping.get(response_category, ())


# Backward-compatible and ergonomic aliases
ResponseExtractor = RequiredResponseExtractor


def extract_required_response(
    text: str | PreprocessedText,
    report_id: str | None = None,
    incident_type: str | None = None,
    people_at_risk_count: int | None = None,
    config: MLConfig | None = None,
    min_confidence_threshold: float = 0.50,
) -> ResponseExtractionResult:
    """
    Convenience function for extracting required response categories.
    Instantiates a temporary RequiredResponseExtractor with the specified configuration.
    """
    extractor = RequiredResponseExtractor(
        config=config,
        min_confidence_threshold=min_confidence_threshold,
    )
    return extractor.extract(
        text=text,
        report_id=report_id,
        incident_type=incident_type,
        people_at_risk_count=people_at_risk_count,
    )
