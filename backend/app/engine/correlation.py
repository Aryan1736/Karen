"""
Karen's Ear — Deterministic Incident Correlation & Deduplication Engine
Pure business logic for three-dimensional incident triangulation and fusion.

Authority:
- architecture/incident-correlation.md (Strict Source of Truth for Triangulation, Formulas & Thresholds)
- architecture/database.md
- architecture/failure-handling.md
- architecture/testing.md
- docs/data-schema.md Section 2.4
- docs/api-contract.md Section 3 & 4.2
- gemini.md Section 6.4

Invariants:
1. Deterministic: Same input vectors, times, and locations ALWAYS produce identical correlation scores.
2. No side-effects: Zero database queries/writes, zero network calls, zero ML pipeline calls.
3. No hallucination: Missing coordinates remain strictly None; never guessed or geocoded.
4. Bounded: All computed similarity components and composite scores remain strictly bounded.
5. Dynamic Thresholding: Configurable similarity thresholds loaded from environment, never hard-coded.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import os
from typing import Any, Optional, Sequence, Union

from backend.app.schemas.common import RelationshipType

# Engine Calculation Version Descriptor
CORRELATION_ENGINE_VERSION: str = "v1.0-deterministic"

# Earth radius in kilometers for Haversine distance
EARTH_RADIUS_KM: float = 6371.0

# Expected ML dense embedding vector dimensionality (all-MiniLM-L6-v2)
EMBEDDING_DIMENSION: int = 384

# Baseline Triangulation Component Weights (Section 4.4)
DEFAULT_WEIGHT_SEMANTIC: float = 0.55
DEFAULT_WEIGHT_TEMPORAL: float = 0.20
DEFAULT_WEIGHT_SPATIAL: float = 0.25

DEFAULT_WEIGHTS: dict[str, float] = {
    "semantic": DEFAULT_WEIGHT_SEMANTIC,
    "temporal": DEFAULT_WEIGHT_TEMPORAL,
    "spatial": DEFAULT_WEIGHT_SPATIAL,
}

# Dynamic Thresholding Baselines (Section 5)
# Environment variable overrides with documented fallbacks
DEFAULT_DUPLICATE_THRESHOLD: float = float(
    os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.85")
)
DEFAULT_CORROBORATION_THRESHOLD: float = float(
    os.getenv("CORROBORATION_SIMILARITY_THRESHOLD", "0.70")
)

# Temporal Proximity Constants (Section 4.2)
DEFAULT_TEMPORAL_DECAY_HOURS: float = float(
    os.getenv("TEMPORAL_DECAY_HOURS", "3.0")
)
DEFAULT_TEMPORAL_CUTOFF_HOURS: float = float(
    os.getenv("TEMPORAL_CUTOFF_HOURS", "6.0")
)

# Spatial Geographic Cluster Radius (Section 4.3)
DEFAULT_SPATIAL_CLUSTER_RADIUS_KM: float = float(
    os.getenv("SPATIAL_CLUSTER_RADIUS_KM", "2.5")
)

# Textual Spatial Similarity Constants (Section 4.3 Case B)
SPATIAL_TEXT_EXACT: float = 0.90
SPATIAL_TEXT_SUBSTRING: float = 0.60
SPATIAL_TEXT_NEUTRAL: float = 0.50
SPATIAL_TEXT_CONFLICT: float = 0.0

# Corroboration Decay Constant (Section 6.3 & priority-engine.md Section 4.3)
CORROBORATION_LAMBDA: float = 0.45


@dataclass(frozen=True)
class TriangulationScores:
    """Breakdown of the three evidence dimensions and composite correlation score."""
    semantic_similarity: Optional[float]
    temporal_similarity: float
    spatial_similarity: Optional[float]
    composite_score: float
    time_delta_hours: float
    spatial_distance_km: Optional[float]
    spatial_match_type: str
    is_reweighted: bool
    weights_used: dict[str, float]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CorrelationResult:
    """Complete deterministic correlation result for report-to-incident candidate evaluation."""
    relationship: RelationshipType
    is_match: bool
    composite_score: float
    triangulation: TriangulationScores
    independent_sources_count: int
    corroboration_score: float
    corroboration_explanation: str
    explanation: str
    warnings: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Dimension 1: Dense Semantic Similarity (Section 4.1)
# -----------------------------------------------------------------------------
def calculate_cosine_similarity(
    v1: Optional[Sequence[float]],
    v2: Optional[Sequence[float]],
    expected_dim: int = EMBEDDING_DIMENSION,
) -> tuple[Optional[float], list[str]]:
    """
    Computes cosine similarity between two dense embedding vectors.
    Section 4.1:
      S_sem = (v_report . v_incident) / (||v_report||_2 * ||v_incident||_2)
      Bounded strictly in [-1.0, 1.0].

    Invariants:
    - Missing embedding (None) safely returns (None, warnings) without crashing.
    - Dimension mismatch (!= expected_dim) fails safely with warning.
    - Zero vectors return (0.0, warnings).
    - Pure standard Python math; zero ML or external library dependencies.
    """
    warnings: list[str] = []

    if v1 is None or v2 is None:
        warnings.append("Missing embedding vector for semantic comparison")
        return None, warnings

    len1 = len(v1)
    len2 = len(v2)

    if len1 != expected_dim or len2 != expected_dim:
        warnings.append(
            f"Invalid embedding dimension: expected {expected_dim}, "
            f"got report={len1}, incident={len2}"
        )
        return None, warnings

    dot_product = 0.0
    norm1_sq = 0.0
    norm2_sq = 0.0

    for a, b in zip(v1, v2):
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            warnings.append("Embedding vector contains non-numeric values")
            return None, warnings
        if math.isnan(a) or math.isnan(b) or math.isinf(a) or math.isinf(b):
            warnings.append("Embedding vector contains NaN or infinite values")
            return None, warnings

        dot_product += a * b
        norm1_sq += a * a
        norm2_sq += b * b

    if norm1_sq <= 0.0 or norm2_sq <= 0.0:
        warnings.append("Zero-norm embedding vector encountered; similarity set to 0.0")
        return 0.0, warnings

    denominator = math.sqrt(norm1_sq) * math.sqrt(norm2_sq)
    if denominator <= 0.0:
        return 0.0, warnings

    cos_sim = dot_product / denominator
    # Clamp strictly to [-1.0, 1.0] to absorb tiny floating point imprecision
    cos_sim = max(-1.0, min(1.0, cos_sim))
    return round(cos_sim, 4), warnings


# -----------------------------------------------------------------------------
# Dimension 2: Temporal Proximity (Section 4.2)
# -----------------------------------------------------------------------------
def parse_and_normalize_timestamp(
    ts: Optional[Union[datetime, str, int, float]],
) -> tuple[Optional[datetime], list[str]]:
    """
    Parses and normalizes timestamps to strict timezone-aware UTC datetime.
    Handles datetime objects, ISO-8601 strings, and unix timestamps.
    """
    warnings: list[str] = []
    if ts is None:
        return None, ["Missing timestamp"]

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            warnings.append("Naive timestamp provided; assumed UTC")
            return ts.replace(tzinfo=timezone.utc), warnings
        return ts.astimezone(timezone.utc), warnings

    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc), warnings
        except (ValueError, OverflowError, OSError) as e:
            warnings.append(f"Invalid numeric timestamp {ts}: {e}")
            return None, warnings

    if isinstance(ts, str):
        cleaned = ts.strip()
        if not cleaned:
            return None, ["Empty timestamp string"]
        try:
            # Handle ISO-8601 UTC 'Z' suffix
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                warnings.append("Naive ISO timestamp provided; assumed UTC")
                return dt.replace(tzinfo=timezone.utc), warnings
            return dt.astimezone(timezone.utc), warnings
        except ValueError as e:
            warnings.append(f"Failed to parse ISO timestamp '{ts}': {e}")
            return None, warnings

    warnings.append(f"Unsupported timestamp type: {type(ts)}")
    return None, warnings


def calculate_temporal_similarity(
    t_report: Optional[Union[datetime, str, int, float]],
    t_incident: Optional[Union[datetime, str, int, float]],
    tau_decay_hours: float = DEFAULT_TEMPORAL_DECAY_HOURS,
    cutoff_hours: float = DEFAULT_TEMPORAL_CUTOFF_HOURS,
) -> tuple[float, float, list[str]]:
    """
    Computes temporal proximity decay between report and incident.
    Section 4.2:
      Delta t = |t_report - t_incident_last_active|
      S_temp = exp(- Delta t / tau_decay)
      Where tau_decay is configurable baseline (3.0 hours).
      If Delta t > 6.0 hours, S_temp -> 0.0.

    Returns:
      (s_temp, delta_hours, warnings)
    """
    warnings: list[str] = []
    dt_report, warn_rep = parse_and_normalize_timestamp(t_report)
    dt_incident, warn_inc = parse_and_normalize_timestamp(t_incident)
    warnings.extend(warn_rep)
    warnings.extend(warn_inc)

    if dt_report is None or dt_incident is None:
        warnings.append("Temporal similarity evaluated without valid timestamps; default S_temp=0.0")
        return 0.0, 0.0, warnings

    delta_seconds = abs((dt_report - dt_incident).total_seconds())
    delta_hours = delta_seconds / 3600.0

    if tau_decay_hours <= 0.0:
        warnings.append(f"Invalid tau_decay_hours {tau_decay_hours}; using default {DEFAULT_TEMPORAL_DECAY_HOURS}")
        tau_decay_hours = DEFAULT_TEMPORAL_DECAY_HOURS

    # Section 4.2 Invariant: If Delta t > 6 hours, S_temp -> 0
    if delta_hours > cutoff_hours:
        return 0.0, round(delta_hours, 4), warnings

    s_temp = math.exp(-delta_hours / tau_decay_hours)
    s_temp = max(0.0, min(1.0, s_temp))
    return round(s_temp, 4), round(delta_hours, 4), warnings


# -----------------------------------------------------------------------------
# Dimension 3: Spatial Proximity (Section 4.3)
# -----------------------------------------------------------------------------
def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Computes great-circle distance between two geographic coordinates in kilometers.
    Pure standard library math implementation.
    """
    if not (-90.0 <= lat1 <= 90.0 and -90.0 <= lat2 <= 90.0):
        raise ValueError(f"Latitude out of bounds [-90.0, 90.0]: lat1={lat1}, lat2={lat2}")
    if not (-180.0 <= lon1 <= 180.0 and -180.0 <= lon2 <= 180.0):
        raise ValueError(f"Longitude out of bounds [-180.0, 180.0]: lon1={lon1}, lon2={lon2}")

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    a = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def normalize_location_text(text: Optional[str]) -> Optional[str]:
    """Clean and normalize location string for exact/substring matching."""
    if text is None:
        return None
    cleaned = text.strip().lower()
    if not cleaned or cleaned in {"unknown", "none", "null", "n/a", "unspecified"}:
        return None
    return cleaned


def calculate_spatial_similarity(
    *,
    lat_report: Optional[float] = None,
    lon_report: Optional[float] = None,
    lat_incident: Optional[float] = None,
    lon_incident: Optional[float] = None,
    text_report: Optional[str] = None,
    text_incident: Optional[str] = None,
    d_max_km: float = DEFAULT_SPATIAL_CLUSTER_RADIUS_KM,
) -> tuple[Optional[float], Optional[float], str, list[str]]:
    """
    Computes spatial proximity between report and incident.
    Section 4.3:
      Case A: Both entities have verified coordinates:
        d = HaversineDistance(L_report, L_incident)
        S_spatial = max(0.0, 1.0 - d / d_max)
      Case B: Textual locations only:
        - Exact landmark match: S_spatial = 0.90
        - Partial substring match: S_spatial = 0.60
        - Both unknown: S_spatial = 0.50 (neutral, relies strictly on semantics)
        - Explicitly conflicting locations: S_spatial = 0.0 (hard veto against fusion)
        - One unknown: S_spatial = 0.50 (neutral fallback without hallucination)

    Returns:
      (s_spatial, distance_km, match_type, warnings)
    """
    warnings: list[str] = []

    has_coords_report = (
        lat_report is not None
        and lon_report is not None
        and -90.0 <= lat_report <= 90.0
        and -180.0 <= lon_report <= 180.0
    )
    has_coords_incident = (
        lat_incident is not None
        and lon_incident is not None
        and -90.0 <= lat_incident <= 90.0
        and -180.0 <= lon_incident <= 180.0
    )

    # -------------------------------------------------------------------------
    # Case A: Both entities have verified coordinates
    # -------------------------------------------------------------------------
    if has_coords_report and has_coords_incident:
        try:
            d_km = haversine_distance_km(
                lat_report,  # type: ignore[arg-type]
                lon_report,  # type: ignore[arg-type]
                lat_incident,  # type: ignore[arg-type]
                lon_incident,  # type: ignore[arg-type]
            )
            d_max = max(0.001, d_max_km)
            raw_s = max(0.0, 1.0 - (d_km / d_max))
            s_spatial = round(min(1.0, raw_s), 4)
            return s_spatial, round(d_km, 4), "COORDINATES", warnings
        except ValueError as e:
            warnings.append(f"Coordinate computation failed: {e}; falling back to text")

    # -------------------------------------------------------------------------
    # Case B: Textual locations only (or coordinate fallback)
    # -------------------------------------------------------------------------
    t_rep = normalize_location_text(text_report)
    t_inc = normalize_location_text(text_incident)

    # Both unknown -> S_spatial = 0.50 (Section 4.3)
    if t_rep is None and t_inc is None:
        return SPATIAL_TEXT_NEUTRAL, None, "BOTH_UNKNOWN", warnings

    # One unknown -> Neutral 0.50 without hallucination
    if t_rep is None or t_inc is None:
        warnings.append(
            "One location entity is unknown; applying neutral spatial score 0.50 without hallucination"
        )
        return SPATIAL_TEXT_NEUTRAL, None, "ONE_UNKNOWN", warnings

    # Exact landmark match -> S_spatial = 0.90 (Section 4.3)
    if t_rep == t_inc:
        return SPATIAL_TEXT_EXACT, None, "EXACT_TEXT", warnings

    # Partial substring match -> S_spatial = 0.60 (Section 4.3)
    # Substring check with minimum meaningful token length (>= 3 chars)
    if (len(t_rep) >= 3 and t_rep in t_inc) or (len(t_inc) >= 3 and t_inc in t_rep):
        return SPATIAL_TEXT_SUBSTRING, None, "SUBSTRING_TEXT", warnings

    # Token overlap check (e.g. "patia square" vs "patia station")
    tokens_rep = set(t_rep.split())
    tokens_inc = set(t_inc.split())
    common_tokens = {t for t in (tokens_rep & tokens_inc) if len(t) >= 3}
    if common_tokens:
        return SPATIAL_TEXT_SUBSTRING, None, "SUBSTRING_TEXT", warnings

    # Explicitly conflicting locations -> S_spatial = 0.0 (Section 4.3: hard veto)
    return SPATIAL_TEXT_CONFLICT, None, "CONFLICTING_TEXT", warnings


# -----------------------------------------------------------------------------
# Combined Correlation Score (Section 4.4)
# -----------------------------------------------------------------------------
def calculate_composite_score(
    *,
    s_sem: Optional[float],
    s_temp: float,
    s_spatial: Optional[float],
    weights: Optional[dict[str, float]] = None,
    reweight_missing: bool = True,
) -> tuple[float, bool, dict[str, float], list[str]]:
    """
    Computes composite correlation score (C_score).
    Section 4.4:
      C_score = w_1 S_sem + w_2 S_temp + w_3 S_spatial
      Baseline weights: w_1 = 0.55, w_2 = 0.20, w_3 = 0.25.

    Missing Dimension Reweighting:
    - If s_sem is None (e.g. missing ML embedding), non-vector triangulation dimensions
      (s_temp, s_spatial) are reweighted proportionally so absence of ML vector does
      not unfairly force a non-match (docs/api-contract.md Line 181).
    - If reweight_missing is False, missing dimensions default to contribution 0.0.

    Returns:
      (composite_score, is_reweighted, weights_used, warnings)
    """
    warnings: list[str] = []
    w_sem = weights.get("semantic", DEFAULT_WEIGHT_SEMANTIC) if weights else DEFAULT_WEIGHT_SEMANTIC
    w_temp = weights.get("temporal", DEFAULT_WEIGHT_TEMPORAL) if weights else DEFAULT_WEIGHT_TEMPORAL
    w_spatial = weights.get("spatial", DEFAULT_WEIGHT_SPATIAL) if weights else DEFAULT_WEIGHT_SPATIAL

    available_dims: dict[str, tuple[float, float]] = {}
    if s_sem is not None:
        available_dims["semantic"] = (s_sem, w_sem)
    else:
        warnings.append("Semantic similarity unavailable; omitted from composite calculation")

    available_dims["temporal"] = (s_temp, w_temp)

    if s_spatial is not None:
        available_dims["spatial"] = (s_spatial, w_spatial)
    else:
        warnings.append("Spatial similarity unavailable; omitted from composite calculation")

    is_reweighted = False
    weights_used: dict[str, float] = {}

    if reweight_missing and len(available_dims) < 3:
        sum_weights = sum(w for _, w in available_dims.values())
        if sum_weights > 0.0:
            is_reweighted = True
            for dim, (score, w) in available_dims.items():
                weights_used[dim] = round(w / sum_weights, 4)
        else:
            return 0.0, False, {}, warnings
    else:
        for dim, (_, w) in available_dims.items():
            weights_used[dim] = w

    c_score = 0.0
    for dim, (score, _) in available_dims.items():
        w = weights_used[dim]
        c_score += w * score

    # Clamp composite score strictly to [0.0, 1.0]
    c_score = max(0.0, min(1.0, c_score))
    return round(c_score, 4), is_reweighted, weights_used, warnings


# -----------------------------------------------------------------------------
# Relationship Classification & Independence Rules (Section 6)
# -----------------------------------------------------------------------------
def classify_relationship(
    *,
    c_score: float,
    s_sem: Optional[float],
    s_temp: float,
    s_spatial: Optional[float],
    spatial_match_type: str,
    delta_hours: float,
    is_first_report: bool = False,
    report_text: Optional[str] = None,
    report_source_id: Optional[str] = None,
    candidate_texts: Optional[Sequence[str]] = None,
    candidate_source_ids: Optional[Sequence[str]] = None,
    is_secondary_effect: bool = False,
    duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    corroboration_threshold: float = DEFAULT_CORROBORATION_THRESHOLD,
    cutoff_hours: float = DEFAULT_TEMPORAL_CUTOFF_HOURS,
) -> tuple[RelationshipType, bool, str]:
    """
    Assigns an explicit, frozen relationship type adhering strictly to Section 6.1:
    - INITIAL: First dispatch spawning a new incident.
    - DUPLICATE: Identical/near-verbatim text from same or indeterminate sender; echo/re-transmission.
    - CORROBORATING: Distinct source reporting consistent facts from scene; +1 to independent sources.
    - RELATED: Mentions incident or secondary effect (e.g. traffic jam from flood); minimal corroboration.
    - UNCERTAIN: High semantic match but contradictory location/time; sends incident to NEEDS_REVIEW.

    Returns:
      (relationship_type, is_match, explanation)
    """
    if is_first_report:
        return (
            RelationshipType.INITIAL,
            True,
            "Initial report establishing new emergency incident.",
        )

    # -------------------------------------------------------------------------
    # Rule 1: High semantic match but contradictory location or time -> UNCERTAIN
    # Section 6.1: "High semantic match but contradictory location/time.
    #               Fused with warning flag; sends incident to NEEDS_REVIEW."
    # -------------------------------------------------------------------------
    is_high_semantic = (s_sem is not None and s_sem >= corroboration_threshold)
    is_contradictory_location = (spatial_match_type == "CONFLICTING_TEXT")
    is_contradictory_time = (delta_hours > cutoff_hours or s_temp <= 0.0)

    if is_high_semantic and (is_contradictory_location or is_contradictory_time):
        reason = "conflicting location" if is_contradictory_location else "excessive elapsed time (>6h)"
        return (
            RelationshipType.UNCERTAIN,
            True,
            f"High semantic match ({s_sem:.2f}) with {reason}; flagged UNCERTAIN for operator review.",
        )

    # -------------------------------------------------------------------------
    # Rule 2: Hard Veto on Conflicting Locations (Section 4.3 Case B)
    # If spatial comparison yielded explicit conflict, hard veto against fusion
    # -------------------------------------------------------------------------
    if is_contradictory_location:
        return (
            RelationshipType.INITIAL,
            False,
            "Explicit location conflict (hard veto against fusion); treated as distinct incident.",
        )

    # -------------------------------------------------------------------------
    # Rule 3: Distinct Incident (Below Corroboration Threshold)
    # Section 5: C_score < tau_corrob -> Distinct Incident
    # -------------------------------------------------------------------------
    if c_score < corroboration_threshold:
        return (
            RelationshipType.INITIAL,
            False,
            f"Correlation score ({c_score:.2f}) below threshold ({corroboration_threshold:.2f}); distinct incident.",
        )

    # -------------------------------------------------------------------------
    # Rule 4: Candidate for Fusion (C_score >= tau_corrob)
    # Distinguish DUPLICATE vs CORROBORATING vs RELATED
    # -------------------------------------------------------------------------
    norm_report_text = normalize_location_text(report_text)
    known_texts = [
        normalize_location_text(t) for t in (candidate_texts or [])
        if normalize_location_text(t) is not None
    ]
    is_verbatim_text = (norm_report_text is not None and norm_report_text in known_texts)

    norm_source_id = report_source_id.strip() if report_source_id else None
    known_source_ids = {
        s.strip() for s in (candidate_source_ids or [])
        if s and s.strip()
    }
    is_same_source = (norm_source_id is not None and norm_source_id in known_source_ids)

    # Secondary effect -> RELATED (Section 6.1)
    if is_secondary_effect:
        return (
            RelationshipType.RELATED,
            True,
            f"Correlated as secondary hazard effect (score={c_score:.2f}); minimal corroboration.",
        )

    # Identical / near-verbatim text or same source -> DUPLICATE (Section 6.1 & 6.2)
    if is_verbatim_text or is_same_source:
        dup_reason = "verbatim text match" if is_verbatim_text else f"repeated report from source '{norm_source_id}'"
        return (
            RelationshipType.DUPLICATE,
            True,
            f"Classified as DUPLICATE due to {dup_reason} (score={c_score:.2f}).",
        )

    # High similarity tier (C_score >= tau_dup) without verified distinct source
    # If source_id is unknown/indeterminate, conservative classification as DUPLICATE
    if c_score >= duplicate_threshold and norm_source_id is None:
        return (
            RelationshipType.DUPLICATE,
            True,
            f"Near-identical correlation ({c_score:.2f} >= {duplicate_threshold:.2f}) from indeterminate source; classified DUPLICATE.",
        )

    # Distinct source with formatted human variation -> CORROBORATING (Section 6.2)
    # 1. Distinct source_id from previous reports
    # 2. Formatted variation indicating human re-phrasing
    # 3. Reasonable temporal sequence (s_temp > 0, delta <= 6h)
    if norm_source_id is not None and not is_same_source and not is_verbatim_text:
        return (
            RelationshipType.CORROBORATING,
            True,
            f"Independent corroboration from distinct source '{norm_source_id}' (score={c_score:.2f}).",
        )

    # If score is in [tau_corrob, tau_dup) with different text but indeterminate source
    if not is_verbatim_text and norm_source_id is None:
        # Formatted human rephrasing even without caller ID qualifies as corroboration
        # per Section 6.2 rule 2 if plausible eyewitness variation
        return (
            RelationshipType.CORROBORATING,
            True,
            f"Corroborating eyewitness report with distinct phrasing (score={c_score:.2f}).",
        )

    # Fallback to RELATED for grey-zone ambiguous reports
    return (
        RelationshipType.RELATED,
        True,
        f"Correlated incident dispatch (score={c_score:.2f}); classified as RELATED.",
    )


# -----------------------------------------------------------------------------
# Corroboration Metric Formulation (Section 6.3)
# -----------------------------------------------------------------------------
def calculate_corroboration_score(
    independent_source_count: int,
    lambda_param: float = CORROBORATION_LAMBDA,
) -> float:
    """
    Asymptotic saturating corroboration score.
    Section 6.3:
      Score = 1.0 - exp(-lambda * N_independent)
      With lambda = 0.45:
        N=1 -> 0.36
        N=2 -> 0.59
        N=3 -> 0.74
        N=5 -> 0.89
        N>=7 -> 0.96 -> 1.0
    Constrained strictly to [0.0, 1.0].
    """
    if independent_source_count <= 0:
        return 0.0

    score = 1.0 - math.exp(-lambda_param * independent_source_count)
    score = max(0.0, min(1.0, score))
    return round(score, 2)


def generate_corroboration_explanation(
    report_count: int,
    independent_source_count: int,
    score: float,
) -> str:
    """Generates plain-language corroboration summary matching API contracts."""
    if independent_source_count <= 0:
        return "No independent verification recorded."
    if independent_source_count == 1:
        rep_suffix = "report" if report_count == 1 else "reports"
        return f"Single eyewitness source ({report_count} total {rep_suffix})."
    return f"Corroborated by {independent_source_count} distinct field reports (score={score:.2f})."


# -----------------------------------------------------------------------------
# Master Report-to-Incident Correlation Pipeline
# -----------------------------------------------------------------------------
def correlate_report_to_incident(
    *,
    # Report features
    report: Optional[Any] = None,
    report_text: Optional[str] = None,
    report_embedding: Optional[Sequence[float]] = None,
    report_timestamp: Optional[Union[datetime, str, int, float]] = None,
    report_latitude: Optional[float] = None,
    report_longitude: Optional[float] = None,
    report_location_text: Optional[str] = None,
    report_source_id: Optional[str] = None,
    # Incident candidate features
    incident: Optional[Any] = None,
    incident_embedding: Optional[Sequence[float]] = None,
    incident_timestamp: Optional[Union[datetime, str, int, float]] = None,
    incident_latitude: Optional[float] = None,
    incident_longitude: Optional[float] = None,
    incident_location_text: Optional[str] = None,
    candidate_texts: Optional[Sequence[str]] = None,
    candidate_source_ids: Optional[Sequence[str]] = None,
    current_report_count: int = 1,
    current_independent_sources: int = 1,
    # Engine configuration overrides
    is_first_report: bool = False,
    is_secondary_effect: bool = False,
    duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    corroboration_threshold: float = DEFAULT_CORROBORATION_THRESHOLD,
    tau_decay_hours: float = DEFAULT_TEMPORAL_DECAY_HOURS,
    cutoff_hours: float = DEFAULT_TEMPORAL_CUTOFF_HOURS,
    spatial_cluster_radius_km: float = DEFAULT_SPATIAL_CLUSTER_RADIUS_KM,
    weights: Optional[dict[str, float]] = None,
    reweight_missing: bool = True,
) -> CorrelationResult:
    """
    Pure deterministic correlation engine evaluating an incoming report against a candidate incident.

    Accepts:
    - Typed dataclasses, Pydantic objects, ORM models, plain dicts, or explicit kwargs.
    - Zero database or network dependencies.
    """
    all_warnings: list[str] = []

    # -------------------------------------------------------------------------
    # Step 1: Extract Report Features
    # -------------------------------------------------------------------------
    if report is not None:
        if report_text is None:
            report_text = getattr(report, "text", None) or (report.get("text") if isinstance(report, dict) else None)

        if report_embedding is None:
            report_embedding = getattr(report, "embedding", None) or (report.get("embedding") if isinstance(report, dict) else None)

        if report_timestamp is None:
            report_timestamp = getattr(report, "reported_at", None) or (report.get("reported_at") if isinstance(report, dict) else None)

        if report_latitude is None or report_longitude is None or report_location_text is None:
            # Check location or location_hint
            loc = getattr(report, "location", None) or getattr(report, "location_hint", None) or (
                report.get("location") if isinstance(report, dict) else report.get("location_hint") if isinstance(report, dict) else None
            )
            if loc is not None:
                if report_latitude is None:
                    report_latitude = getattr(loc, "latitude", None) if not isinstance(loc, dict) else loc.get("latitude")
                if report_longitude is None:
                    report_longitude = getattr(loc, "longitude", None) if not isinstance(loc, dict) else loc.get("longitude")
                if report_location_text is None:
                    report_location_text = getattr(loc, "text", None) or getattr(loc, "raw_text", None) if not isinstance(loc, dict) else loc.get("text") or loc.get("raw_text")

        if report_source_id is None:
            meta = getattr(report, "metadata", None) or (report.get("metadata") if isinstance(report, dict) else None)
            if isinstance(meta, dict):
                report_source_id = meta.get("caller_id") or meta.get("source_id") or meta.get("phone") or meta.get("user")
            if not report_source_id:
                report_source_id = getattr(report, "source", None) or (report.get("source") if isinstance(report, dict) else None)

    # -------------------------------------------------------------------------
    # Step 2: Extract Incident Candidate Features
    # -------------------------------------------------------------------------
    if incident is not None:
        if incident_embedding is None:
            incident_embedding = getattr(incident, "embedding", None) or (incident.get("embedding") if isinstance(incident, dict) else None)

        if incident_timestamp is None:
            incident_timestamp = getattr(incident, "updated_at", None) or getattr(incident, "created_at", None) or (
                incident.get("updated_at") if isinstance(incident, dict) else incident.get("created_at") if isinstance(incident, dict) else None
            )

        if incident_latitude is None or incident_longitude is None or incident_location_text is None:
            loc = getattr(incident, "location", None) or (incident.get("location") if isinstance(incident, dict) else None)
            if loc is not None:
                if incident_latitude is None:
                    incident_latitude = getattr(loc, "latitude", None) if not isinstance(loc, dict) else loc.get("latitude")
                if incident_longitude is None:
                    incident_longitude = getattr(loc, "longitude", None) if not isinstance(loc, dict) else loc.get("longitude")
                if incident_location_text is None:
                    incident_location_text = getattr(loc, "text", None) if not isinstance(loc, dict) else loc.get("text")

            # Flat fallback (e.g. ORM incidents.latitude)
            if incident_latitude is None and hasattr(incident, "latitude"):
                incident_latitude = getattr(incident, "latitude")
            if incident_longitude is None and hasattr(incident, "longitude"):
                incident_longitude = getattr(incident, "longitude")
            if incident_location_text is None and hasattr(incident, "location_text"):
                incident_location_text = getattr(incident, "location_text")

        if hasattr(incident, "report_count") and incident.report_count is not None:
            current_report_count = incident.report_count
        elif isinstance(incident, dict) and "report_count" in incident:
            current_report_count = incident["report_count"]

        if hasattr(incident, "independent_source_count") and incident.independent_source_count is not None:
            current_independent_sources = incident.independent_source_count
        elif isinstance(incident, dict) and "independent_source_count" in incident:
            current_independent_sources = incident["independent_source_count"]

    # -------------------------------------------------------------------------
    # Step 3: Compute Triangulation Dimensions
    # -------------------------------------------------------------------------
    s_sem, warn_sem = calculate_cosine_similarity(report_embedding, incident_embedding)
    all_warnings.extend(warn_sem)

    s_temp, delta_hours, warn_temp = calculate_temporal_similarity(
        report_timestamp,
        incident_timestamp,
        tau_decay_hours=tau_decay_hours,
        cutoff_hours=cutoff_hours,
    )
    all_warnings.extend(warn_temp)

    s_spatial, distance_km, spatial_match_type, warn_spatial = calculate_spatial_similarity(
        lat_report=report_latitude,
        lon_report=report_longitude,
        lat_incident=incident_latitude,
        lon_incident=incident_longitude,
        text_report=report_location_text,
        text_incident=incident_location_text,
        d_max_km=spatial_cluster_radius_km,
    )
    all_warnings.extend(warn_spatial)

    c_score, is_reweighted, weights_used, warn_comp = calculate_composite_score(
        s_sem=s_sem,
        s_temp=s_temp,
        s_spatial=s_spatial,
        weights=weights,
        reweight_missing=reweight_missing,
    )
    all_warnings.extend(warn_comp)

    triangulation = TriangulationScores(
        semantic_similarity=s_sem,
        temporal_similarity=s_temp,
        spatial_similarity=s_spatial,
        composite_score=c_score,
        time_delta_hours=delta_hours,
        spatial_distance_km=distance_km,
        spatial_match_type=spatial_match_type,
        is_reweighted=is_reweighted,
        weights_used=weights_used,
        warnings=all_warnings,
    )

    # -------------------------------------------------------------------------
    # Step 4: Classify Relationship Type
    # -------------------------------------------------------------------------
    relationship, is_match, explanation = classify_relationship(
        c_score=c_score,
        s_sem=s_sem,
        s_temp=s_temp,
        s_spatial=s_spatial,
        spatial_match_type=spatial_match_type,
        delta_hours=delta_hours,
        is_first_report=is_first_report,
        report_text=report_text,
        report_source_id=report_source_id,
        candidate_texts=candidate_texts,
        candidate_source_ids=candidate_source_ids,
        is_secondary_effect=is_secondary_effect,
        duplicate_threshold=duplicate_threshold,
        corroboration_threshold=corroboration_threshold,
        cutoff_hours=cutoff_hours,
    )

    # -------------------------------------------------------------------------
    # Step 5: Update Corroboration Metrics
    # -------------------------------------------------------------------------
    if relationship == RelationshipType.INITIAL:
        new_sources_count = 1
        new_report_count = 1
    elif relationship == RelationshipType.CORROBORATING:
        new_sources_count = current_independent_sources + 1
        new_report_count = current_report_count + 1
    else:
        # DUPLICATE, RELATED, UNCERTAIN: report_count increases, independent sources remain same
        new_sources_count = current_independent_sources
        new_report_count = current_report_count + (1 if is_match else 0)

    corrob_score = calculate_corroboration_score(new_sources_count)
    corrob_explanation = generate_corroboration_explanation(
        new_report_count,
        new_sources_count,
        corrob_score,
    )

    return CorrelationResult(
        relationship=relationship,
        is_match=is_match,
        composite_score=c_score,
        triangulation=triangulation,
        independent_sources_count=new_sources_count,
        corroboration_score=corrob_score,
        corroboration_explanation=corrob_explanation,
        explanation=explanation,
        warnings=all_warnings,
    )


def find_best_incident_match(
    report: Any,
    candidate_incidents: Sequence[Any],
    *,
    duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    corroboration_threshold: float = DEFAULT_CORROBORATION_THRESHOLD,
    tau_decay_hours: float = DEFAULT_TEMPORAL_DECAY_HOURS,
    cutoff_hours: float = DEFAULT_TEMPORAL_CUTOFF_HOURS,
    spatial_cluster_radius_km: float = DEFAULT_SPATIAL_CLUSTER_RADIUS_KM,
    weights: Optional[dict[str, float]] = None,
    reweight_missing: bool = True,
) -> tuple[Optional[Any], CorrelationResult]:
    """
    Evaluates an incoming report against a list of active candidate incidents.
    Returns the best matching incident candidate (highest composite score >= threshold)
    or (None, fallback_result) if no candidate matches.
    """
    if not candidate_incidents:
        fallback_res = correlate_report_to_incident(
            report=report,
            is_first_report=True,
            duplicate_threshold=duplicate_threshold,
            corroboration_threshold=corroboration_threshold,
        )
        return None, fallback_res

    best_incident: Optional[Any] = None
    best_result: Optional[CorrelationResult] = None
    highest_score: float = -1.0

    for candidate in candidate_incidents:
        result = correlate_report_to_incident(
            report=report,
            incident=candidate,
            duplicate_threshold=duplicate_threshold,
            corroboration_threshold=corroboration_threshold,
            tau_decay_hours=tau_decay_hours,
            cutoff_hours=cutoff_hours,
            spatial_cluster_radius_km=spatial_cluster_radius_km,
            weights=weights,
            reweight_missing=reweight_missing,
        )

        if result.is_match and result.composite_score > highest_score:
            highest_score = result.composite_score
            best_incident = candidate
            best_result = result

    if best_incident is not None and best_result is not None:
        return best_incident, best_result

    # No candidate passed matching criteria
    fallback_res = correlate_report_to_incident(
        report=report,
        is_first_report=True,
        duplicate_threshold=duplicate_threshold,
        corroboration_threshold=corroboration_threshold,
    )
    return None, fallback_res
