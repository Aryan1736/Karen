"""
Karen's Ear — Deterministic Priority Engine
Pure business logic for continuous operational emergency triage prioritization.

Authority:
- architecture/priority-engine.md (Strict Source of Truth for Formulas & Thresholds)
- docs/data-schema.md Section 2.3
- docs/api-contract.md Section 5.1
- gemini.md Section 6.4

Invariants:
1. Deterministic: Same input ALWAYS produces identical priority score, level, factors, and explanation.
2. No side-effects: Zero database writes, zero network calls, zero ML calls, zero global mutable state.
3. No hallucination: Missing or unverified values strictly follow documented fallback defaults.
4. Bounded: Final priority score is strictly constrained to [0.0, 100.0].
5. Explainable: Plain-language, rule-based audit breakdown matching canonical PriorityBlock schema.
"""
from enum import Enum
import math
from typing import Any, Optional, Union
from pydantic import Field

from backend.app.schemas.common import IncidentStatus, IncidentType, PriorityLevel, UrgencyLevel
from backend.app.schemas.incident import ConfidenceBlock, PriorityBlock, PriorityFactor

# Engine Calculation Version Descriptor
PRIORITY_CALCULATION_VERSION: str = "v1.0-deterministic"

# Configurable Baseline Factor Weights (Section 5.1)
DEFAULT_WEIGHT_URGENCY: float = 0.35
DEFAULT_WEIGHT_RISK: float = 0.30
DEFAULT_WEIGHT_CORROB: float = 0.20
DEFAULT_WEIGHT_HAZARD: float = 0.15

DEFAULT_WEIGHTS: dict[str, float] = {
    "urgency": DEFAULT_WEIGHT_URGENCY,
    "risk": DEFAULT_WEIGHT_RISK,
    "corroboration": DEFAULT_WEIGHT_CORROB,
    "hazard": DEFAULT_WEIGHT_HAZARD,
}

# Factor 1: Operational Urgency Normalization Mapping (Section 4.1)
URGENCY_SCORES: dict[str, float] = {
    UrgencyLevel.CRITICAL.value: 100.0,
    UrgencyLevel.HIGH.value: 75.0,
    UrgencyLevel.MEDIUM.value: 40.0,
    UrgencyLevel.LOW.value: 15.0,
}
# Default neutral urgency score for null/unknown (Section 4.1)
DEFAULT_URGENCY_SCORE: float = 30.0

# Factor 2: People at Risk Normalization Constants (Section 4.2)
PEOPLE_AT_RISK_BASE: float = 40.0
PEOPLE_AT_RISK_PER_PERSON: float = 12.0
PEOPLE_AT_RISK_AMBIGUOUS_SCORE: float = 70.0
PEOPLE_AT_RISK_NONE_SCORE: float = 10.0

# Factor 3: Corroboration Decay Constant (Section 4.3 & incident-correlation.md Section 6.3)
CORROBORATION_LAMBDA: float = 0.45

# Factor 4: Hazard Severity Normalization Mapping (Section 4.4 & Decision #1)
HAZARD_SCORES: dict[str, float] = {
    IncidentType.STRUCTURAL_COLLAPSE.value: 100.0,
    IncidentType.FIRE_WILDFIRE_EXPLOSION.value: 90.0,
    IncidentType.FLOOD_FLASH_FLOOD.value: 85.0,
    IncidentType.CIVIL_UNREST_ACTIVE_THREAT.value: 80.0,
    IncidentType.EARTHQUAKE_LANDSLIDE.value: 75.0,
    IncidentType.MEDICAL_EMERGENCY.value: 70.0,
    IncidentType.UTILITY_INFRASTRUCTURE_FAILURE.value: 45.0,
    IncidentType.OTHER_GENERAL_INCIDENT.value: 25.0,
    # NOTE: architecture/priority-engine.md Section 4.4 currently omits a dedicated hazard score
    # for SEVERE_WEATHER_STORM. Per backend implementation decision, temporarily mapped to 25.0
    # (same baseline as OTHER_GENERAL_INCIDENT) so it remains isolated and easily updated later.
    IncidentType.SEVERE_WEATHER_STORM.value: 25.0,
}
# Fallback hazard score for null / unknown / unrecognized incident types (Decision #2)
DEFAULT_HAZARD_SCORE: float = 25.0

# Dynamic Modifiers (Section 5.2 & Decision #5)
LOW_CONFIDENCE_THRESHOLD: float = 0.50
LOW_CONFIDENCE_PENALTY: float = -10.0
STATUS_MODIFIER_ESCALATED: float = 15.0
STATUS_MODIFIER_VERIFIED: float = 10.0

STATUS_MODIFIERS: dict[str, float] = {
    IncidentStatus.ESCALATED.value: STATUS_MODIFIER_ESCALATED,
    IncidentStatus.VERIFIED.value: STATUS_MODIFIER_VERIFIED,
}

# Priority Tier Thresholds (Section 6)
LEVEL_THRESHOLDS: list[tuple[float, PriorityLevel]] = [
    (80.0, PriorityLevel.CRITICAL),
    (60.0, PriorityLevel.HIGH),
    (35.0, PriorityLevel.MEDIUM),
    (0.0, PriorityLevel.LOW),
]


class PriorityCalculationResult(PriorityBlock):
    """
    Deterministic priority calculation result adhering strictly to canonical PriorityBlock.
    Includes additional audit metadata (calc_version, raw_score, modifiers_applied).
    """
    calc_version: str = Field(
        default=PRIORITY_CALCULATION_VERSION,
        description="Priority engine formula version descriptor",
    )
    raw_score: float = Field(
        ...,
        description="Unclamped multi-factor sum before bounding and status forced overrides",
    )
    modifiers_applied: list[str] = Field(
        default_factory=list,
        description="Summary list of dynamic modifiers applied during calculation",
    )


def normalize_urgency_factor(
    urgency: Optional[Union[UrgencyLevel, str]],
) -> tuple[float, str]:
    """
    Factor 1: Operational Urgency (S_urgency).
    Section 4.1:
      CRITICAL -> 100.0
      HIGH     -> 75.0
      MEDIUM   -> 40.0
      LOW      -> 15.0
      null/unk -> 30.0 (neutral default with review flag)
    """
    if urgency is None:
        return DEFAULT_URGENCY_SCORE, "UNKNOWN"

    urgency_str = urgency.value if isinstance(urgency, Enum) else str(urgency).strip().upper()
    if urgency_str in URGENCY_SCORES:
        return URGENCY_SCORES[urgency_str], urgency_str

    return DEFAULT_URGENCY_SCORE, f"UNKNOWN ({urgency_str})" if urgency_str else "UNKNOWN"


def normalize_people_at_risk_factor(
    count: Optional[int],
    has_trapped_indication: bool = False,
) -> tuple[float, str]:
    """
    Factor 2: People at Risk (S_risk).
    Section 4.2 & Decision #3:
      - Positive count (count > 0): min(100.0, 40.0 + 12.0 * count)
      - Ambiguous trapped/casualty mention without exact count: 70.0
      - count <= 0 or None: 10.0 ("No indication of people at risk")
    """
    if count is not None and count > 0:
        score = min(100.0, PEOPLE_AT_RISK_BASE + (PEOPLE_AT_RISK_PER_PERSON * count))
        person_str = "person" if count == 1 else "persons"
        return score, f"{count} trapped {person_str}"

    if has_trapped_indication:
        return PEOPLE_AT_RISK_AMBIGUOUS_SCORE, "Ambiguous trapped/casualty indication"

    # count <= 0 or count is None -> 10.0 (Decision #3)
    return PEOPLE_AT_RISK_NONE_SCORE, "No indication of people at risk"


def normalize_corroboration_factor(
    independent_sources: Optional[int] = None,
    corroboration_score: Optional[float] = None,
) -> tuple[float, str]:
    """
    Factor 3: Corroboration & Verification (S_corrob).
    Section 4.3, incident-correlation.md Section 6.3 & Decision #4:
      score_0_to_1 = round(1.0 - exp(-0.45 * independent_source_count), 2)
      priority_factor = score_0_to_1 * 100.0
      Intentionally produces:
        N=1 -> 36.0
        N=2 -> 59.0
        N=3 -> 74.0
        N=5 -> 89.0
        Satisfies testing.md where N=2 contributes 11.8 and total score is 82.35.
      If corroboration_score [0.0, 1.0] is provided directly, priority_factor = corroboration_score * 100.0.
    """
    if corroboration_score is not None:
        clamped_score = max(0.0, min(1.0 if corroboration_score <= 1.0 else 100.0, corroboration_score))
        scaled = clamped_score * 100.0 if corroboration_score <= 1.0 else clamped_score
        scaled = round(scaled, 1)
        val_str = f"Corroboration metric {clamped_score:.2f}"
        return scaled, val_str

    if independent_sources is not None and independent_sources > 0:
        score_0_to_1 = round(1.0 - math.exp(-CORROBORATION_LAMBDA * independent_sources), 2)
        priority_factor = score_0_to_1 * 100.0
        report_str = "report" if independent_sources == 1 else "reports"
        return priority_factor, f"{independent_sources} independent {report_str}"

    return 0.0, "0 independent reports"


def normalize_hazard_factor(
    incident_type: Optional[Union[IncidentType, str]],
) -> tuple[float, str]:
    """
    Factor 4: Hazard Severity & Type (S_hazard).
    Section 4.4 & Decisions #1 and #2:
      STRUCTURAL_COLLAPSE            -> 100.0
      FIRE_WILDFIRE_EXPLOSION        -> 90.0
      FLOOD_FLASH_FLOOD              -> 85.0
      CIVIL_UNREST_ACTIVE_THREAT     -> 80.0
      EARTHQUAKE_LANDSLIDE           -> 75.0
      MEDICAL_EMERGENCY              -> 70.0
      UTILITY_INFRASTRUCTURE_FAILURE -> 45.0
      OTHER_GENERAL_INCIDENT         -> 25.0
      SEVERE_WEATHER_STORM           -> 25.0 (Decision #1 fallback)
      null / unknown / unrecognized  -> 25.0 (Decision #2 fallback)
    """
    if incident_type is None:
        return DEFAULT_HAZARD_SCORE, "UNKNOWN"

    hazard_str = incident_type.value if isinstance(incident_type, Enum) else str(incident_type).strip().upper()
    if hazard_str in HAZARD_SCORES:
        return HAZARD_SCORES[hazard_str], hazard_str

    return DEFAULT_HAZARD_SCORE, hazard_str if hazard_str else "UNKNOWN"


def resolve_average_confidence(
    ml_confidence: Optional[Union[float, ConfidenceBlock, dict[str, Any]]],
) -> Optional[float]:
    """
    Extracts or computes the effective average model confidence.
    Returns float in [0.0, 1.0], or None if confidence is absent/unknown.
    """
    if ml_confidence is None:
        return None

    if isinstance(ml_confidence, (int, float)):
        return max(0.0, min(1.0, float(ml_confidence)))

    if isinstance(ml_confidence, ConfidenceBlock):
        if ml_confidence.overall is not None:
            return ml_confidence.overall
        if ml_confidence.components:
            valid_vals = [v for v in ml_confidence.components.values() if v is not None]
            if valid_vals:
                return sum(valid_vals) / len(valid_vals)
        return None

    if isinstance(ml_confidence, dict):
        if "overall" in ml_confidence and ml_confidence["overall"] is not None:
            return float(ml_confidence["overall"])
        components = ml_confidence.get("components")
        if isinstance(components, dict):
            valid_vals = [float(v) for v in components.values() if v is not None]
            if valid_vals:
                return sum(valid_vals) / len(valid_vals)

    return None


def map_priority_level(score: float) -> PriorityLevel:
    """
    Maps priority score [0.0, 100.0] to discrete operator triage level.
    Section 6:
      80.0 – 100.0 -> CRITICAL
      60.0 – 79.9  -> HIGH
      35.0 – 59.9  -> MEDIUM
       0.0 – 34.9  -> LOW
    """
    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return PriorityLevel.LOW


def generate_deterministic_explanation(
    *,
    level: PriorityLevel,
    final_score: float,
    factors: list[PriorityFactor],
    status: str,
    modifiers_applied: list[str],
) -> str:
    """
    Generates a deterministic, explainable plain-language justification string.
    Follows Section 7 format without generative LLM probabilistic drift.
    """
    if status == IncidentStatus.RESOLVED.value:
        return "Incident marked RESOLVED: priority forced to 0.00 (LOW) and cleared from active dispatch."

    factor_details = ", ".join(
        f"{f.factor}: {f.value} (+{f.contribution:.2f})"
        for f in factors
    )

    modifiers_clause = ""
    if modifiers_applied:
        modifiers_clause = f" [{'; '.join(modifiers_applied)}]"

    prefix = {
        PriorityLevel.CRITICAL: "Elevated to CRITICAL priority",
        PriorityLevel.HIGH: "Classified as HIGH priority",
        PriorityLevel.MEDIUM: "Classified as MEDIUM priority",
        PriorityLevel.LOW: "Assigned LOW priority",
    }.get(level, f"Assigned {level.value} priority")

    return f"{prefix} ({final_score:.2f}) driven by {factor_details}.{modifiers_clause}"


def calculate_priority(
    *,
    incident: Optional[Any] = None,
    urgency: Optional[Union[UrgencyLevel, str]] = None,
    people_at_risk_count: Optional[int] = None,
    has_trapped_indication: bool = False,
    independent_sources: Optional[int] = None,
    corroboration_score: Optional[float] = None,
    incident_type: Optional[Union[IncidentType, str]] = None,
    status: Optional[Union[IncidentStatus, str]] = None,
    ml_confidence: Optional[Union[float, ConfidenceBlock, dict[str, Any]]] = None,
    weight_urgency: Optional[float] = None,
    weight_risk: Optional[float] = None,
    weight_corrob: Optional[float] = None,
    weight_hazard: Optional[float] = None,
) -> PriorityCalculationResult:
    """
    Pure deterministic multi-factor emergency priority calculation.

    Scoring formula:
      Raw = (w1 * S_urgency) + (w2 * S_risk) + (w3 * S_corrob) + (w4 * S_hazard)
            + State_Modifiers - Low_Confidence_Penalty
      Final = Clamp(Raw, 0.0, 100.0) [Forced to 0.0 if RESOLVED]

    Returns canonical PriorityCalculationResult (valid PriorityBlock).
    """
    # -------------------------------------------------------------------------
    # Step 1: Input Resolution & Extraction
    # -------------------------------------------------------------------------
    if incident is not None:
        # Extract from ORM model, Pydantic model, or dict if not explicitly overridden
        if urgency is None:
            urgency = getattr(incident, "urgency", None) or (incident.get("urgency") if isinstance(incident, dict) else None)

        if people_at_risk_count is None:
            if hasattr(incident, "people_at_risk_count"):
                people_at_risk_count = getattr(incident, "people_at_risk_count")
            elif hasattr(incident, "people_at_risk"):
                par = getattr(incident, "people_at_risk")
                people_at_risk_count = getattr(par, "count", None) if par is not None else None
            elif isinstance(incident, dict):
                par = incident.get("people_at_risk")
                if isinstance(par, dict):
                    people_at_risk_count = par.get("count")
                else:
                    people_at_risk_count = incident.get("people_at_risk_count")

        if independent_sources is None:
            if hasattr(incident, "independent_source_count"):
                independent_sources = getattr(incident, "independent_source_count")
            elif hasattr(incident, "corroboration"):
                corrob = getattr(incident, "corroboration")
                independent_sources = getattr(corrob, "independent_source_count", None) if corrob is not None else None
            elif isinstance(incident, dict):
                corrob = incident.get("corroboration")
                if isinstance(corrob, dict):
                    independent_sources = corrob.get("independent_source_count")
                else:
                    independent_sources = incident.get("independent_source_count")

        if corroboration_score is None:
            if hasattr(incident, "corroboration_score"):
                corroboration_score = getattr(incident, "corroboration_score")
            elif hasattr(incident, "corroboration"):
                corrob = getattr(incident, "corroboration")
                corroboration_score = getattr(corrob, "score", None) if corrob is not None else None
            elif isinstance(incident, dict):
                corrob = incident.get("corroboration")
                if isinstance(corrob, dict):
                    corroboration_score = corrob.get("score")
                else:
                    corroboration_score = incident.get("corroboration_score")

        if incident_type is None:
            incident_type = getattr(incident, "incident_type", None) or (incident.get("incident_type") if isinstance(incident, dict) else None)

        if status is None:
            status = getattr(incident, "status", None) or (incident.get("status") if isinstance(incident, dict) else None)

        if ml_confidence is None:
            ml_confidence = getattr(incident, "ml_confidence", None) or (incident.get("ml_confidence") if isinstance(incident, dict) else None)

    # Normalize status string
    status_str = (status.value if isinstance(status, Enum) else str(status).strip().upper()) if status else IncidentStatus.ACTIVE.value

    # Weight resolution
    w_urgency = weight_urgency if weight_urgency is not None else DEFAULT_WEIGHT_URGENCY
    w_risk = weight_risk if weight_risk is not None else DEFAULT_WEIGHT_RISK
    w_corrob = weight_corrob if weight_corrob is not None else DEFAULT_WEIGHT_CORROB
    w_hazard = weight_hazard if weight_hazard is not None else DEFAULT_WEIGHT_HAZARD

    # -------------------------------------------------------------------------
    # Step 2: Factor Normalization [0.0, 100.0]
    # -------------------------------------------------------------------------
    s_urgency, val_urgency = normalize_urgency_factor(urgency)
    s_risk, val_risk = normalize_people_at_risk_factor(people_at_risk_count, has_trapped_indication)
    s_corrob, val_corrob = normalize_corroboration_factor(independent_sources, corroboration_score)
    s_hazard, val_hazard = normalize_hazard_factor(incident_type)

    # Calculate individual factor contributions
    contrib_urgency = round(w_urgency * s_urgency, 2)
    contrib_risk = round(w_risk * s_risk, 2)
    contrib_corrob = round(w_corrob * s_corrob, 2)
    contrib_hazard = round(w_hazard * s_hazard, 2)

    factors = [
        PriorityFactor(
            factor="Urgency (Life-Safety)",
            value=val_urgency,
            weight=w_urgency,
            contribution=contrib_urgency,
        ),
        PriorityFactor(
            factor="People at Risk",
            value=val_risk,
            weight=w_risk,
            contribution=contrib_risk,
        ),
        PriorityFactor(
            factor="Corroboration",
            value=val_corrob,
            weight=w_corrob,
            contribution=contrib_corrob,
        ),
        PriorityFactor(
            factor="Hazard Type",
            value=val_hazard,
            weight=w_hazard,
            contribution=contrib_hazard,
        ),
    ]

    base_score = contrib_urgency + contrib_risk + contrib_corrob + contrib_hazard

    # -------------------------------------------------------------------------
    # Step 3: Modifiers and Penalties (Decision #5: Pure engine applies only penalty)
    # -------------------------------------------------------------------------
    modifiers_applied: list[str] = []
    modifier_sum = 0.0

    # Low Confidence Penalty: average ML confidence < 0.50
    avg_confidence = resolve_average_confidence(ml_confidence)
    if avg_confidence is not None and avg_confidence < LOW_CONFIDENCE_THRESHOLD:
        modifier_sum += LOW_CONFIDENCE_PENALTY
        modifiers_applied.append(f"Low ML confidence penalty: {LOW_CONFIDENCE_PENALTY:+.1f} (confidence={avg_confidence:.2f})")

    # State Modifiers: ESCALATED (+15.0), VERIFIED (+10.0)
    if status_str in STATUS_MODIFIERS:
        boost = STATUS_MODIFIERS[status_str]
        modifier_sum += boost
        modifiers_applied.append(f"Status modifier: {status_str} ({boost:+.1f})")

    raw_score = base_score + modifier_sum

    # -------------------------------------------------------------------------
    # Step 4: Special Status Handling, Level Mapping & Clamping
    # -------------------------------------------------------------------------
    if status_str == IncidentStatus.RESOLVED.value:
        final_score = 0.0
        modifiers_applied.append("Status RESOLVED: forced to 0.0")
    else:
        # Clamped strictly to [0.0, 100.0] and rounded to 2 decimals
        clamped = max(0.0, min(100.0, raw_score))
        final_score = round(clamped, 2)

    level = map_priority_level(final_score)

    # -------------------------------------------------------------------------
    # Step 5: Deterministic Explainability Generation
    # -------------------------------------------------------------------------
    explanation = generate_deterministic_explanation(
        level=level,
        final_score=final_score,
        factors=factors,
        status=status_str,
        modifiers_applied=modifiers_applied,
    )

    return PriorityCalculationResult(
        score=final_score,
        level=level,
        explanation=explanation,
        factors=factors,
        calc_version=PRIORITY_CALCULATION_VERSION,
        raw_score=round(raw_score, 2),
        modifiers_applied=modifiers_applied,
    )
