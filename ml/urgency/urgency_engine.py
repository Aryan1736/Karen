"""
Karen's Ear — Operational Urgency Engine.

Step 2B of the ML pipeline (architecture/ml-pipeline.md Section 3.3 and gemini.md Section 6.2).
Derives an explicit, deterministic operational urgency score, label, and explainable breakdown:
1. Urgency Score: 0.0 – 100.0
2. Urgency Label: CRITICAL (80–100), HIGH (60–79), MEDIUM (35–59), LOW (0–34)
3. Urgency Confidence: Deterministic calibration in [0.0, 1.0] reflecting signal explicitness
4. Explainable Breakdown: Life Safety (50%), Hazard Velocity (30%), Vulnerability (20%)

CRITICAL ARCHITECTURAL PRINCIPLES:
- ADR-003: Operational urgency is feature-derived and deterministic.
  CrisiText does NOT provide categorical operational urgency ground truth.
  No claims of CrisiText supervised urgency training or accuracy.
- ADR-004: Strict separation of ML confidence from operational priority.
  urgency != ML confidence.
  urgency_score != backend priority_score.
  confidence != score / 100.
  Do NOT rank incidents against one another.
- No-Inference Principle: Life safety is not inferred from category alone without report evidence.
- Safe Degradation: Operates robustly with or without upstream ML feature outputs.
- Privacy & Observability: Never leaks raw citizen distress text into logs.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.config import (
    CANONICAL_URGENCY_LEVELS,
    ComponentResult,
    MLConfig,
    get_ml_config,
)
from ml.exceptions import MLInferenceError, MLInputError
from ml.logging_utils import get_ml_logger
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner
from ml.urgency.taxonomy import (
    DISTRESS_PATTERNS,
    HAZARD_VELOCITY_SIGNALS,
    HEDGING_OR_UNCERTAINTY_PATTERNS,
    HISTORICAL_OR_CONTROLLED_PATTERNS,
    INFORMATIONAL_HELP_PATTERN,
    LABEL_CRITICAL,
    LABEL_HIGH,
    LABEL_LOW,
    LABEL_MEDIUM,
    LIFE_SAFETY_NEGATION_PATTERNS,
    LIFE_SAFETY_SIGNALS,
    PASSIVE_FACILITY_MENTION_PATTERN,
    SIGNAL_NEGATION_DEFINITIONS,
    TEMPORAL_ACTIVE_MARKERS,
    THRESHOLD_CRITICAL,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    VULNERABILITY_NEGATION_PATTERNS,
    VULNERABILITY_SIGNALS,
    WEIGHT_HAZARD_VELOCITY,
    WEIGHT_LIFE_SAFETY,
    WEIGHT_VULNERABILITY,
    is_canonical_urgency_label,
)

_NUMBER_WORD_MAP: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

_TEXT_COUNT_PATTERN = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
    r"(?:injured|trapped|unconscious|drowning|missing|workers|residents|passengers|victims|occupants|children|kids|people)\b",
    re.IGNORECASE,
)


# ==============================================================================
# Public Typed Output Structures
# ==============================================================================

@dataclass
class ComponentScore:
    """
    Standardized breakdown for one of the three primary urgency dimensions.
    """

    name: str  # "life_safety", "hazard_velocity", "vulnerability"
    score: float  # Normalized strictly in [0.0, 100.0]
    weight: float  # Component weight (0.50, 0.30, 0.20)
    weighted_contribution: float  # score * weight
    signals: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    negated: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serializes component breakdown to a structured dictionary."""
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "weight": self.weight,
            "weighted_contribution": round(self.weighted_contribution, 2),
            "signals": list(self.signals),
            "evidence": list(self.evidence),
            "negated": self.negated,
            "details": dict(self.details),
        }


@dataclass
class UrgencyBreakdown:
    """
    Complete explainable breakdown of all contributing urgency signal groups.
    """

    life_safety: ComponentScore
    hazard_velocity: ComponentScore
    vulnerability: ComponentScore

    def to_dict(self) -> dict[str, Any]:
        """Serializes breakdown to explainable dictionary."""
        return {
            "life_safety": self.life_safety.to_dict(),
            "hazard_velocity": self.hazard_velocity.to_dict(),
            "vulnerability": self.vulnerability.to_dict(),
        }


@dataclass
class UrgencyResult:
    """
    Standardized typed result emitted by UrgencyEngine.
    Adheres strictly to Step 2B of the ML pipeline (architecture/ml-pipeline.md Section 3.3)
    and canonical contract in ml/schemas/incident_output.json.
    """

    score: float  # Bounded strictly in [0.0, 100.0]
    label: str  # One of CANONICAL_URGENCY_LEVELS ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    confidence: float  # Bounded strictly in [0.0, 1.0], decoupled from score
    breakdown: UrgencyBreakdown
    signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    processing_status: str = "SUCCESS"  # SUCCESS, PARTIAL, NEEDS_REVIEW, FAILED
    method: str = "feature_derived_v1"

    def to_canonical_dict(self) -> dict[str, Any]:
        """
        Serializes to the canonical urgency dictionary strictly matching
        ml/schemas/incident_output.json:
        {
            "label": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | null,
            "confidence": float | null
        }
        """
        return {
            "label": self.label,
            "confidence": self.confidence,
        }

    def to_component_result(self) -> ComponentResult:
        """Converts into a standardized internal ComponentResult."""
        return ComponentResult(
            component="urgency",
            status=self.processing_status,
            data={
                "urgency": self.to_canonical_dict(),
                "urgency_score": round(self.score, 2),
                "breakdown": self.breakdown.to_dict(),
                "signals": list(self.signals),
                "method": self.method,
            },
            confidence=self.confidence,
            warnings=list(self.warnings),
        )


# ==============================================================================
# Core Urgency Scoring Engine
# ==============================================================================

class UrgencyEngine:
    """
    Deterministic Operational Urgency Engine.

    Evaluates incident dispatch evidence against explicit feature rules:
    - Life Safety (50%)
    - Hazard Velocity (30%)
    - Vulnerability (20%)

    Guarantees:
    - 100% deterministic repeatable scoring.
    - Zero external network or API calls.
    - Full explainability for operational dispatchers.
    - Strict decoupling of urgency score from ML inference confidence.
    """

    def __init__(self, config: MLConfig | None = None) -> None:
        self.config = config or get_ml_config()
        self.logger = get_ml_logger(
            name="karen.ml.urgency",
            component="urgency",
            model_version=self.config.model_version,
        )
        self.cleaner = TextCleaner(self.config)

    def score_urgency(
        self,
        text: str | PreprocessedText,
        incident_type: Any | None = None,
        people_at_risk: Any | None = None,
        required_response: Any | None = None,
        location_entities: Any | None = None,
    ) -> UrgencyResult:
        """
        Scores operational urgency from report text and optional upstream ML signals.

        Args:
            text: Raw string or PreprocessedText emergency dispatch.
            incident_type: Optional classified incident hazard type (str, ClassificationResult, dict).
            people_at_risk: Optional extracted people count or PeopleRiskResult.
            required_response: Optional extracted response categories (ResponseExtractionResult, list).
            location_entities: Optional extracted location/entity metadata.

        Returns:
            UrgencyResult containing score (0-100), label, confidence, and explainable breakdown.

        Raises:
            MLInputError: If text is empty, whitespace-only, or invalid type.
        """
        start_time = time.perf_counter()

        # 1. Input Validation and Preprocessing
        clean_text, warnings = self._validate_and_clean_text(text)

        # 2. Extract Upstream Signal Context (Safely degraded if missing)
        incident_label = self._extract_incident_label(incident_type)
        extracted_people_count, qualitative_people_signals = self._extract_people_signals(people_at_risk)

        # If count was not explicitly passed, inspect clean_text for cardinal number count
        if extracted_people_count is None:
            m_cnt = _TEXT_COUNT_PATTERN.search(clean_text)
            if m_cnt:
                token = m_cnt.group(1).lower()
                if token.isdigit():
                    extracted_people_count = int(token)
                elif token in _NUMBER_WORD_MAP:
                    extracted_people_count = _NUMBER_WORD_MAP[token]

        response_categories = self._extract_response_categories(required_response)

        # 3. Derive Signal Group 1: Life Safety (50%)
        life_safety = self._evaluate_life_safety(
            clean_text=clean_text,
            people_count=extracted_people_count,
            people_signals=qualitative_people_signals,
            response_categories=response_categories,
        )

        # 4. Derive Signal Group 2: Hazard Velocity (30%)
        hazard_velocity = self._evaluate_hazard_velocity(
            clean_text=clean_text,
            incident_label=incident_label,
            response_categories=response_categories,
        )

        # 5. Derive Signal Group 3: Vulnerability (20%)
        vulnerability = self._evaluate_vulnerability(
            clean_text=clean_text,
            people_signals=qualitative_people_signals,
            life_safety=life_safety,
            response_categories=response_categories,
        )

        # 6. Synthesize Weighted Score & Deterministic Clamping
        final_score = (
            (self.config.urgency_weight_life_safety * life_safety.score)
            + (self.config.urgency_weight_hazard_velocity * hazard_velocity.score)
            + (self.config.urgency_weight_vulnerability * vulnerability.score)
        )
        final_score = max(0.0, min(100.0, final_score))
        final_score = round(final_score, 2)

        # 7. Map Score to Operational Urgency Label (Deterministic Boundaries)
        label = self.map_score_to_label(final_score)

        # 8. Compute Independent ML Inference Confidence (Decoupled from Score)
        confidence = self._derive_confidence(
            clean_text=clean_text,
            final_score=final_score,
            life_safety=life_safety,
            hazard_velocity=hazard_velocity,
            vulnerability=vulnerability,
            people_count=extracted_people_count,
            incident_label=incident_label,
            response_categories=response_categories,
        )

        # 9. Aggregate All Extracted Signal Identifiers
        all_signals = sorted(
            set(life_safety.signals + hazard_velocity.signals + vulnerability.signals)
        )

        # 10. Determine Processing Status
        processing_status = "SUCCESS"
        if confidence < self.config.confidence_review_threshold:
            processing_status = "NEEDS_REVIEW"
            warnings.append(
                f"Low urgency inference confidence ({confidence:.2f} < {self.config.confidence_review_threshold:.2f}); marked for review"
            )

        breakdown = UrgencyBreakdown(
            life_safety=life_safety,
            hazard_velocity=hazard_velocity,
            vulnerability=vulnerability,
        )

        result = UrgencyResult(
            score=final_score,
            label=label,
            confidence=confidence,
            breakdown=breakdown,
            signals=all_signals,
            warnings=warnings,
            processing_status=processing_status,
            method="feature_derived_v1",
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        self.logger.info(
            "Urgency evaluated successfully",
            extra={
                "score": final_score,
                "label": label,
                "confidence": confidence,
                "duration_ms": round(duration_ms, 2),
                "signal_count": len(all_signals),
                "processing_status": processing_status,
            },
        )

        return result

    # ==========================================================================
    # Label Mapping & Boundary Logic
    # ==========================================================================

    def map_score_to_label(self, score: float) -> str:
        """
        Maps a clamped urgency score [0.0, 100.0] into a deterministic canonical tier.

        Boundaries (architecture/ml-pipeline.md Section 3.3):
        - score >= 80.0 -> CRITICAL
        - 60.0 <= score < 80.0 -> HIGH
        - 35.0 <= score < 60.0 -> MEDIUM
        - score < 35.0 -> LOW
        """
        clamped = max(0.0, min(100.0, score))
        if clamped >= self.config.urgency_threshold_critical:  # 80.0
            return LABEL_CRITICAL
        elif clamped >= self.config.urgency_threshold_high:  # 60.0
            return LABEL_HIGH
        elif clamped >= self.config.urgency_threshold_medium:  # 35.0
            return LABEL_MEDIUM
        else:
            return LABEL_LOW

    # ==========================================================================
    # Signal Group 1: Life Safety Evaluation (Weight: 50%)
    # ==========================================================================

    def _evaluate_life_safety(
        self,
        clean_text: str,
        people_count: int | None,
        people_signals: Sequence[str],
        response_categories: Sequence[str],
    ) -> ComponentScore:
        """
        Calculates life-safety dimension (0–100) based on victims, trapped status,
        injuries, distress language, count scaling, and negations.
        """
        signals: list[str] = []
        evidence: list[str] = []
        details: dict[str, Any] = {}

        # 1. Targeted signal-specific negation detection
        negated_signals: set[str] = set()
        negation_evidence: list[str] = []
        for defn in SIGNAL_NEGATION_DEFINITIONS:
            for match in defn.pattern.finditer(clean_text):
                # Guard: generic occupants safe does NOT override explicit affirmative trapped / drowning / threat statements
                if defn.negation_id == "NEGATION_GENERAL_OCCUPANTS_SAFE":
                    if re.search(r"\b(?:trapped|pinned|stuck|drowning|bleeding|shooter|attacker)\b", clean_text, re.IGNORECASE):
                        continue
                negated_signals.update(defn.target_signals)
                negation_evidence.append(match.group(0))
                signals.append(defn.negation_id)

        # 2. Match Life Safety Base Signals (Respecting signal-specific negation)
        matched_scores: list[float] = []
        for defn in LIFE_SAFETY_SIGNALS:
            # If this specific signal is negated, suppress it
            if defn.signal_id in negated_signals:
                continue

            for match in defn.pattern.finditer(clean_text):
                signals.append(defn.signal_id)
                evidence.append(match.group(0))
                matched_scores.append(defn.base_score)
                break  # Record once per pattern

        # Also incorporate qualitative signals from Feature 4 if passed (and not specifically negated)
        for sig in people_signals:
            if sig == "TRAPPED" and "TRAPPED" not in signals and "TRAPPED" not in negated_signals:
                signals.append("TRAPPED")
                matched_scores.append(85.0)
            elif sig in ("INJURED", "CASUALTY") and "INJURED" not in signals and "INJURED" not in negated_signals:
                signals.append("INJURED")
                matched_scores.append(50.0)
            elif sig == "UNCONSCIOUS" and "UNCONSCIOUS" not in signals and "UNCONSCIOUS" not in negated_signals:
                signals.append("UNCONSCIOUS")
                matched_scores.append(80.0)
            elif sig == "DROWNING" and "DROWNING" not in signals and "DROWNING" not in negated_signals:
                signals.append("DROWNING")
                matched_scores.append(85.0)
            elif sig == "MISSING" and "MISSING" not in signals and "MISSING" not in negated_signals:
                signals.append("MISSING")
                matched_scores.append(45.0)

        base_score = max(matched_scores) if matched_scores else 0.0

        # Multi-signal synergy boost (if multiple distinct unnegated life-safety signals are active)
        active_life_signals = {
            s for s in signals
            if not s.startswith("NEGATION_")
            and not s.startswith("DISTRESS_")
            and not s.endswith("_REQUIRED")
            and not s.startswith("PEOPLE_COUNT_")
            and not s.startswith("MULTIPLE_PEOPLE_")
        }
        multi_signal_boost = 0.0
        if len(active_life_signals) >= 2:
            multi_signal_boost = min(15.0, (len(active_life_signals) - 1) * 5.0)

        # 3. People-at-Risk Count Scaling (Bounded & Diminishing Returns)
        # Note: count boost applies only when active life peril exists (base_score > 0.0)
        count_boost = 0.0
        if base_score > 0.0:
            if people_count is not None and isinstance(people_count, int) and people_count > 0:
                if people_count == 1:
                    count_boost = 15.0
                elif 2 <= people_count <= 4:
                    count_boost = 25.0
                elif 5 <= people_count <= 9:
                    count_boost = 35.0
                elif 10 <= people_count <= 19:
                    count_boost = 45.0
                else:  # >= 20
                    count_boost = 50.0
                signals.append("PEOPLE_COUNT_ELEVATED")
                details["people_count"] = people_count
                details["count_boost"] = count_boost
            elif "MULTIPLE_PEOPLE" in people_signals or re.search(
                r"\b(?:multiple\s+people|several\s+people|group\s+of\s+people|many\s+people)\b",
                clean_text,
                re.IGNORECASE,
            ):
                count_boost = 20.0
                signals.append("MULTIPLE_PEOPLE_QUALITATIVE")
                details["qualitative_multiple_people"] = True

        # 4. Distress Language Detection (Contextualized)
        distress_boost = 0.0
        is_informational_help = bool(INFORMATIONAL_HELP_PATTERN.search(clean_text))
        if not is_informational_help:
            for distress_tag, distress_pat, boost_val in DISTRESS_PATTERNS:
                distress_match = distress_pat.search(clean_text)
                if distress_match:
                    signals.append(f"DISTRESS_{distress_tag}")
                    evidence.append(distress_match.group(0))
                    distress_boost = max(distress_boost, boost_val)
                    details["distress_match"] = distress_match.group(0)

        # 5. Upstream Response Service Context (Search & Rescue / Medical EMS)
        response_boost = 0.0
        if "SEARCH_AND_RESCUE" in response_categories:
            if "TRAPPED" not in negated_signals:
                if base_score < 60.0:
                    base_score = max(base_score, 60.0)
                response_boost = 20.0
                signals.append("SAR_RESPONSE_REQUIRED")
        elif "MEDICAL_EMS" in response_categories:
            if "INJURED" not in negated_signals:
                if base_score < 40.0:
                    base_score = max(base_score, 40.0)
                response_boost = 15.0
                signals.append("EMS_RESPONSE_REQUIRED")

        # Total Life Safety Score Calculation
        if base_score > 0.0 or count_boost > 0.0:
            raw_life_safety = (
                base_score + count_boost + multi_signal_boost + distress_boost + response_boost
            )
        else:
            raw_life_safety = max(0.0, distress_boost + response_boost)

        final_life_safety = max(0.0, min(100.0, raw_life_safety))

        if negated_signals:
            details["negated_signals"] = sorted(negated_signals)
            details["negation_evidence"] = negation_evidence
            evidence.extend(negation_evidence)

        # Component is considered fully negated only if signals were negated AND no active life safety base score remains
        is_component_negated = bool(negated_signals and base_score == 0.0)

        return ComponentScore(
            name="life_safety",
            score=round(final_life_safety, 2),
            weight=self.config.urgency_weight_life_safety,
            weighted_contribution=round(
                final_life_safety * self.config.urgency_weight_life_safety, 2
            ),
            signals=sorted(set(signals)),
            evidence=evidence,
            negated=is_component_negated,
            details=details,
        )

    # ==========================================================================
    # Signal Group 2: Hazard Velocity Evaluation (Weight: 30%)
    # ==========================================================================

    def _evaluate_hazard_velocity(
        self,
        clean_text: str,
        incident_label: str | None,
        response_categories: Sequence[str],
    ) -> ComponentScore:
        """
        Calculates hazard velocity dimension (0–100) based on hazard dynamics,
        propagation speed, temporal acceleration markers, and de-escalation/historical checks.
        """
        signals: list[str] = []
        evidence: list[str] = []
        details: dict[str, Any] = {}

        # 1. Check for Historical or Extinguished/Controlled markers
        is_historical = False
        is_extinguished = False
        for de_tag, de_pat in HISTORICAL_OR_CONTROLLED_PATTERNS:
            de_match = de_pat.search(clean_text)
            if de_match:
                if de_tag == "HISTORICAL_INCIDENT":
                    is_historical = True
                    signals.append("HISTORICAL_INCIDENT")
                elif de_tag == "EXTINGUISHED_OR_CONTAINED":
                    is_extinguished = True
                    signals.append("EXTINGUISHED_OR_CONTAINED")
                evidence.append(de_match.group(0))
                details["de_escalation_phrase"] = de_match.group(0)

        # 2. Match Hazard Velocity Base Signals
        matched_scores: list[float] = []
        for defn in HAZARD_VELOCITY_SIGNALS:
            for match in defn.pattern.finditer(clean_text):
                signals.append(defn.signal_id)
                evidence.append(match.group(0))
                matched_scores.append(defn.base_score)
                break

        # Check for medical emergency deterioration velocity
        if not is_historical:
            if (
                incident_label == "MEDICAL_EMERGENCY"
                or "MEDICAL_EMS" in response_categories
                or re.search(r"\b(?:unconscious|cardiac\s+arrest|stopped\s+breathing|bleeding\s+heavily)\b", clean_text, re.IGNORECASE)
            ):
                matched_scores.append(40.0)
                signals.append("MEDICAL_DETERIORATION_VELOCITY")

        base_score = max(matched_scores) if matched_scores else 0.0

        # Multi-hazard synergy boost
        unique_signals = set(signals) - {"HISTORICAL_INCIDENT", "EXTINGUISHED_OR_CONTAINED"}
        multi_hazard_boost = 0.0
        if len(unique_signals) >= 2:
            multi_hazard_boost = min(15.0, (len(unique_signals) - 1) * 5.0)

        # 3. Temporal Active Markers Acceleration ("now", "rapidly", "spreading")
        temporal_boost = 0.0
        if not is_historical and not is_extinguished:
            temp_match = TEMPORAL_ACTIVE_MARKERS.search(clean_text)
            if temp_match and base_score > 0.0:
                temporal_boost = 15.0
                signals.append("TEMPORAL_ACTIVE_MARKER")
                evidence.append(temp_match.group(0))
                details["temporal_active"] = temp_match.group(0)

        # 4. Upstream Incident Category and Response Alignment
        category_boost = 0.0
        if incident_label and not is_historical and not is_extinguished:
            if incident_label == "STRUCTURAL_COLLAPSE":
                base_score = max(base_score, 70.0)
                signals.append(f"UPSTREAM_HAZARD_{incident_label}")
            elif incident_label == "FIRE_WILDFIRE_EXPLOSION":
                base_score = max(base_score, 65.0)
                signals.append(f"UPSTREAM_HAZARD_{incident_label}")
            elif incident_label == "FLOOD_FLASH_FLOOD":
                base_score = max(base_score, 60.0)
                signals.append(f"UPSTREAM_HAZARD_{incident_label}")
            elif incident_label == "UTILITY_INFRASTRUCTURE_FAILURE" and not re.search(r"\b(?:routine|inspection|scheduled)\b", clean_text, re.IGNORECASE):
                base_score = max(base_score, 50.0)
                signals.append(f"UPSTREAM_HAZARD_{incident_label}")

        if "FIRE_HAZMAT" in response_categories and not is_extinguished and not is_historical:
            base_score = max(base_score, 65.0)
            signals.append("HAZMAT_RESPONSE_CONFIRMED")

        # Active obstruction/flooding/structural threat on thoroughfare or facility raises base velocity
        if (
            "ROAD_OBSTRUCTION" in signals
            or "ACTIVE_FLOODING" in signals
            or "UTILITY_FAILURE" in signals
            or "STRUCTURAL_DAMAGE" in signals
        ) and not is_historical:
            if re.search(
                r"\b(?:main\s+street|highway|water\s+main|transformer\s+blown|blackout|across\s+road|two\s+lanes|fell\s+across|parking\s+garage|supporting\s+pillar|basement\s+flooded)\b",
                clean_text,
                re.IGNORECASE,
            ):
                base_score = max(base_score, 75.0)

        raw_velocity = base_score + multi_hazard_boost + temporal_boost + category_boost

        # 5. Apply De-escalation Dampening
        if is_extinguished:
            raw_velocity = min(15.0, raw_velocity * 0.15)
            details["dampened_due_to_extinguished"] = True
        elif is_historical:
            raw_velocity = min(10.0, raw_velocity * 0.10)
            details["dampened_due_to_historical"] = True

        final_velocity = max(0.0, min(100.0, raw_velocity))

        return ComponentScore(
            name="hazard_velocity",
            score=round(final_velocity, 2),
            weight=self.config.urgency_weight_hazard_velocity,
            weighted_contribution=round(
                final_velocity * self.config.urgency_weight_hazard_velocity, 2
            ),
            signals=sorted(set(signals)),
            evidence=evidence,
            negated=is_extinguished or is_historical,
            details=details,
        )

    # ==========================================================================
    # Signal Group 3: Vulnerability Evaluation (Weight: 20%)
    # ==========================================================================

    def _evaluate_vulnerability(
        self,
        clean_text: str,
        people_signals: Sequence[str],
        life_safety: ComponentScore | None = None,
        response_categories: Sequence[str] = (),
    ) -> ComponentScore:
        """
        Calculates vulnerability dimension (0–100) based on demographic fragility
        (children, elderly, hospital patients, disabled persons, trapped victims, special care facilities).
        Strictly rejects passive location mentions without affected individuals.
        """
        signals: list[str] = []
        evidence: list[str] = []
        details: dict[str, Any] = {}

        # 1. Check for explicit vulnerability negation ("no children present", "school was empty")
        for neg_pat in VULNERABILITY_NEGATION_PATTERNS:
            neg_match = neg_pat.search(clean_text)
            if neg_match:
                signals.append("NEGATION_NO_VULNERABLE_POPULATION")
                evidence.append(neg_match.group(0))
                return ComponentScore(
                    name="vulnerability",
                    score=0.0,
                    weight=self.config.urgency_weight_vulnerability,
                    weighted_contribution=0.0,
                    signals=signals,
                    evidence=evidence,
                    negated=True,
                    details={"negation_phrase": neg_match.group(0)},
                )

        # 2. Check for passive facility mentions ("Hospital is nearby", "passing by school")
        is_passive_facility = bool(PASSIVE_FACILITY_MENTION_PATTERN.search(clean_text))
        if is_passive_facility:
            details["passive_facility_mention_detected"] = True

        # Check if life safety was negated (e.g. "no reports of people trapped")
        is_ls_negated = bool(life_safety and life_safety.negated)

        # 3. Match Vulnerability Base Signals
        matched_scores: list[float] = []
        for defn in VULNERABILITY_SIGNALS:
            # If life safety was negated, skip trapped/victim vulnerability
            if is_ls_negated and defn.signal_id == "PEOPLE_TRAPPED_VULNERABILITY":
                continue

            for match in defn.pattern.finditer(clean_text):
                # If the match is solely a facility name and it was marked passive with no affected persons, skip
                if is_passive_facility and defn.signal_id == "VULNERABLE_FACILITY_AFFECTED":
                    if not re.search(r"\b(?:patients?|children|residents?|trapped|inside|evacuat\w+)\b", clean_text, re.IGNORECASE):
                        continue

                signals.append(defn.signal_id)
                evidence.append(match.group(0))
                matched_scores.append(defn.base_score)
                break

        # Also incorporate demographic and trapped signals from Feature 4 and Life Safety
        for sig in people_signals:
            if sig == "CHILDREN" and "CHILDREN_AT_RISK" not in signals:
                signals.append("CHILDREN_AT_RISK")
                matched_scores.append(85.0)
            elif sig == "ELDERLY" and "ELDERLY_AT_RISK" not in signals:
                signals.append("ELDERLY_AT_RISK")
                matched_scores.append(80.0)
            elif sig == "PATIENTS" and "PATIENTS_AT_RISK" not in signals:
                signals.append("PATIENTS_AT_RISK")
                matched_scores.append(85.0)
            elif sig == "TRAPPED" and not is_ls_negated and "PEOPLE_TRAPPED_VULNERABILITY" not in signals:
                signals.append("PEOPLE_TRAPPED_VULNERABILITY")
                matched_scores.append(75.0)
            elif sig == "UNCONSCIOUS" and "DISABLED_OR_MOBILITY_IMPAIRED" not in signals:
                signals.append("INCAPACITATED_VICTIM_VULNERABILITY")
                matched_scores.append(55.0)

        # If life safety detected trapped or unconscious victims, they are vulnerable incapacitated victims
        if life_safety is not None and not life_safety.negated:
            if "TRAPPED" in life_safety.signals and "PEOPLE_TRAPPED_VULNERABILITY" not in signals:
                signals.append("PEOPLE_TRAPPED_VULNERABILITY")
                matched_scores.append(75.0)
            if "UNCONSCIOUS" in life_safety.signals and "DISABLED_OR_MOBILITY_IMPAIRED" not in signals:
                signals.append("INCAPACITATED_VICTIM_VULNERABILITY")
                matched_scores.append(55.0)

        if "SEARCH_AND_RESCUE" in response_categories and not is_ls_negated:
            matched_scores.append(65.0)
            signals.append("SAR_POPULATION_VULNERABILITY")

        base_score = max(matched_scores) if matched_scores else 0.0

        # Multi-vulnerability synergy boost
        unique_signals = set(signals)
        multi_vulnerability_boost = 0.0
        if len(unique_signals) >= 2:
            multi_vulnerability_boost = min(15.0, (len(unique_signals) - 1) * 5.0)

        raw_vulnerability = base_score + multi_vulnerability_boost
        final_vulnerability = max(0.0, min(100.0, raw_vulnerability))

        return ComponentScore(
            name="vulnerability",
            score=round(final_vulnerability, 2),
            weight=self.config.urgency_weight_vulnerability,
            weighted_contribution=round(
                final_vulnerability * self.config.urgency_weight_vulnerability, 2
            ),
            signals=sorted(set(signals)),
            evidence=evidence,
            negated=False,
            details=details,
        )

    # ==========================================================================
    # Independent ML Urgency Confidence Derivation
    # ==========================================================================

    def _derive_confidence(
        self,
        clean_text: str,
        final_score: float,
        life_safety: ComponentScore,
        hazard_velocity: ComponentScore,
        vulnerability: ComponentScore,
        people_count: int | None,
        incident_label: str | None,
        response_categories: Sequence[str],
    ) -> float:
        """
        Derives deterministic ML inference confidence strictly in [0.0, 1.0].

        CRITICAL ARCHITECTURAL DISTINCTION:
        Confidence measures model certainty in the extracted evidence, NOT incident severity.
        confidence != score / 100.
        A low urgency incident (e.g. routine road maintenance) can have 0.90 confidence,
        while a hedged critical incident (e.g. "someone said people might be trapped")
        can have 0.45 confidence.
        """
        conf = 0.70

        # 1. Explicitness Bonus: Confirmed numeric count (+0.10)
        if people_count is not None and people_count > 0:
            conf += 0.10

        # 2. Multi-Group Convergence Bonus (+0.08)
        active_groups = sum(
            1 for c in (life_safety, hazard_velocity, vulnerability) if c.score >= 50.0
        )
        if active_groups >= 2:
            conf += 0.08

        # 3. Upstream Alignment Bonus (+0.07)
        if incident_label and incident_label != "OTHER_GENERAL_INCIDENT":
            conf += 0.04
        if response_categories:
            conf += 0.03

        # 4. Distress Explicitness Bonus (+0.05)
        if any(s.startswith("DISTRESS_") for s in life_safety.signals):
            conf += 0.05

        # 5. Clear Negation Explicitness Bonus (+0.10)
        if life_safety.negated or hazard_velocity.negated:
            conf += 0.10

        # --- PENALTIES ---

        # 6. Uncertainty / Hedging Penalty (-0.20)
        has_hedging = False
        for hedge_pat in HEDGING_OR_UNCERTAINTY_PATTERNS:
            if hedge_pat.search(clean_text):
                has_hedging = True
                break
        if has_hedging:
            conf -= 0.20

        # 7. Extreme Brevity / Sparsity Penalty (-0.15)
        words = clean_text.split()
        if len(words) <= 3 or len(clean_text) < 20:
            conf -= 0.15

        # 8. Conflicting Signals Penalty (-0.10)
        if hazard_velocity.negated and any("ACTIVE" in s for s in hazard_velocity.signals):
            conf -= 0.10

        # Clamp strictly to [0.10, 0.98]
        conf = max(0.10, min(0.98, conf))
        return round(conf, 2)

    # ==========================================================================
    # Validation & Context Helpers
    # ==========================================================================

    def _validate_and_clean_text(
        self, text: str | PreprocessedText
    ) -> tuple[str, list[str]]:
        """Validates input text and returns cleaned string with any warnings."""
        if text is None:
            raise MLInputError("Input text cannot be None")

        if isinstance(text, PreprocessedText):
            cleaned = text.normalized_text
            warnings = list(text.warnings)
        elif isinstance(text, str):
            if not text or not text.strip():
                raise MLInputError("Input text cannot be empty or whitespace-only")
            preprocessed = self.cleaner.clean(text)
            cleaned = preprocessed.normalized_text
            warnings = list(preprocessed.warnings)
        else:
            raise MLInputError(f"Unsupported text type: {type(text).__name__}")

        if not cleaned or not cleaned.strip():
            raise MLInputError("Cleaned text is empty after sanitization")

        return cleaned, warnings

    @staticmethod
    def _extract_incident_label(incident_type: Any | None) -> str | None:
        """Extracts canonical incident label from diverse upstream types."""
        if incident_type is None:
            return None
        if isinstance(incident_type, str):
            return incident_type.strip()
        if hasattr(incident_type, "label"):
            return getattr(incident_type, "label")
        if isinstance(incident_type, dict):
            return incident_type.get("label")
        return None

    @staticmethod
    def _extract_people_signals(
        people_at_risk: Any | None,
    ) -> tuple[int | None, list[str]]:
        """Extracts people count and qualitative risk signals from diverse upstream types."""
        if people_at_risk is None:
            return None, []
        if isinstance(people_at_risk, (list, tuple, set)):
            return None, [str(s) for s in people_at_risk]
        if isinstance(people_at_risk, int):
            return people_at_risk, []
        count: int | None = None
        signals: list[str] = []

        if hasattr(people_at_risk, "count") and not callable(getattr(people_at_risk, "count")):
            raw_c = getattr(people_at_risk, "count")
            if isinstance(raw_c, int):
                count = raw_c
        if hasattr(people_at_risk, "signals") and not callable(getattr(people_at_risk, "signals")):
            signals = list(getattr(people_at_risk, "signals") or [])

        if isinstance(people_at_risk, dict):
            raw_c = people_at_risk.get("count")
            if isinstance(raw_c, int):
                count = raw_c
            signals = list(people_at_risk.get("signals") or [])

        return count, signals

    @staticmethod
    def _extract_response_categories(
        required_response: Any | None,
    ) -> list[str]:
        """Extracts response category strings from diverse upstream types."""
        if required_response is None:
            return []
        if isinstance(required_response, (list, tuple, set)):
            categories: list[str] = []
            for item in required_response:
                if isinstance(item, str):
                    categories.append(item)
                elif hasattr(item, "type"):
                    categories.append(getattr(item, "type"))
                elif isinstance(item, dict) and "type" in item:
                    categories.append(item["type"])
            return categories
        if hasattr(required_response, "responses"):
            responses = getattr(required_response, "responses") or []
            return [getattr(r, "type") for r in responses if hasattr(r, "type")]
        return []


# ==============================================================================
# Functional Convenience API
# ==============================================================================

_default_engine: UrgencyEngine | None = None


def extract_urgency(
    text: str | PreprocessedText,
    incident_type: Any | None = None,
    people_at_risk: Any | None = None,
    required_response: Any | None = None,
    location_entities: Any | None = None,
    config: MLConfig | None = None,
) -> UrgencyResult:
    """
    Functional convenience wrapper for UrgencyEngine.score_urgency().
    """
    global _default_engine
    if config is not None or _default_engine is None:
        engine = UrgencyEngine(config)
        if config is None:
            _default_engine = engine
        return engine.score_urgency(
            text=text,
            incident_type=incident_type,
            people_at_risk=people_at_risk,
            required_response=required_response,
            location_entities=location_entities,
        )
    return _default_engine.score_urgency(
        text=text,
        incident_type=incident_type,
        people_at_risk=people_at_risk,
        required_response=required_response,
        location_entities=location_entities,
    )
