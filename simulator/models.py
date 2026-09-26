"""
Karen's Ear — Disaster Simulator Core Models & Ground-Truth Schema.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md (v1.0), docs/api-contract.md (v1.0)
Status: Hardened Models & Ground-Truth Foundation

This module defines:
1. GroundTruthLeakageError & verify_no_ground_truth_leakage() (Canonical recursive safety firewall)
2. LocationHint & LocationPrecision (Canonical location representation with cross-field consistency)
3. ReportMetadata (Strictly typed metadata eliminating loose dicts and preventing hidden leaks)
4. RawReportPayload (Canonical public dispatch contract for simulator events)
5. GroundTruth (Private evaluator data for scoring NLP, deduplication, and prioritization)
6. ScenarioEvent (Structural pairing of public dispatch and private ground truth with ID consistency)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
import unicodedata
from typing import Any, Dict, List, Literal, Optional, Sequence, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


# =============================================================================
# 1. Safety Firewall & Exceptions
# =============================================================================

class GroundTruthLeakageError(RuntimeError):
    """Raised when private ground-truth fields attempt to cross the network boundary."""
    pass


FORBIDDEN_GROUND_TRUTH_KEYS: frozenset[str] = frozenset({
    "ground_truth",
    "incident_group",
    "relation_type",
    "expected_incident_type",
    "expected_urgency",
    "expected_people_at_risk",
    "expected_people_count",
    "expected_direction",
    "expected_needs_review",
    "expected_location_text",
    "expected_latitude",
    "expected_longitude",
    "expected_required_response",
    "expected_actionable",
    "notes",
})

NORMALIZED_FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "".join(c for c in unicodedata.normalize("NFKD", k.lower()) if c.isalnum())
    for k in FORBIDDEN_GROUND_TRUTH_KEYS
} | {"groundtruth", "trueurgency", "truehazard", "truegroup"})

ALLOWED_PUBLIC_METADATA_KEYS: frozenset[str] = frozenset({
    "scenario_id",
    "event_id",
    "reporter_id",
    "caller_id",
    "channel",
    "phase",
    "batch_index",
})

AUDITED_METADATA_FIELDS: frozenset[str] = frozenset({
    "channel",
    "caller_id",
    "reporter_id",
    "phase",
    "scenario_id",
})

FORBIDDEN_VALUE_TOKENS: frozenset[str] = frozenset({
    "ground_truth",
    "groundtruth",
    "incident_group",
    "incidentgroup",
    "relation_type",
    "relationtype",
    "trueurgency",
    "truehazard",
    "truegroup",
    "true_urgency",
    "true_hazard",
    "true_group",
    "expected_incident_type",
    "expected_urgency",
    "expected_people_at_risk",
    "expected_people_count",
    "expected_direction",
    "expected_needs_review",
    "expected_location_text",
    "expected_latitude",
    "expected_longitude",
    "expected_required_response",
    "expected_actionable",
    "expectedincidenttype",
    "expectedurgency",
    "expectedpeopleatrisk",
    "expectedpeoplecount",
    "expecteddirection",
    "expectedneedsreview",
    "expectedlocationtext",
    "expectedlatitude",
    "expectedlongitude",
    "expectedrequiredresponse",
    "expectedactionable",
})

FORBIDDEN_VALUE_PREFIXES: tuple[str, ...] = (
    "expected_",
    "expected-",
    "expected:",
    "expected.",
    "expected=",
)


def _audit_metadata_string_value(val_str: str, current_path: str) -> None:
    """
    Audits a string value within an allowed metadata field to ensure zero smuggled
    evaluator ground-truth tokens or prefixes cross the security firewall.
    Raises GroundTruthLeakageError immediately if any leakage is detected.
    """
    val_lower = val_str.lower()
    norm_val = "".join(c for c in unicodedata.normalize("NFKD", val_lower) if c.isalnum())

    # 1. Full normalized value starts with 'expected' or is an exact normalized forbidden token
    if norm_val.startswith("expected") or norm_val in NORMALIZED_FORBIDDEN_KEYS:
        raise GroundTruthLeakageError(
            f"LEAKAGE VIOLATION at '{current_path}': private ground-truth token detected in metadata string value '{val_str}'."
        )

    # 2. Check forbidden value prefixes
    for prefix in FORBIDDEN_VALUE_PREFIXES:
        if val_lower.startswith(prefix):
            raise GroundTruthLeakageError(
                f"LEAKAGE VIOLATION at '{current_path}': private ground-truth prefix '{prefix}' detected in metadata string value '{val_str}'."
            )

    # 3. Check forbidden substring tokens in val_lower or norm_val
    for tok in FORBIDDEN_VALUE_TOKENS:
        if tok in val_lower or tok in norm_val:
            raise GroundTruthLeakageError(
                f"LEAKAGE VIOLATION at '{current_path}': private ground-truth token '{tok}' detected in metadata string value '{val_str}'."
            )

    # 4. Token-level delimiter split audit (handles embedded key-value pairs like channel='radio;expected_urgency=CRITICAL' or 'sim_expected:CRITICAL')
    tokens = re.split(r"[^a-zA-Z0-9]+", val_str)
    for tok in tokens:
        if not tok:
            continue
        tok_lower = tok.lower()
        tok_norm = "".join(c for c in unicodedata.normalize("NFKD", tok_lower) if c.isalnum())
        if (
            tok_lower in FORBIDDEN_VALUE_TOKENS
            or tok_norm in NORMALIZED_FORBIDDEN_KEYS
            or tok_norm.startswith("expected")
            or tok_lower.startswith("expected_")
        ):
            raise GroundTruthLeakageError(
                f"LEAKAGE VIOLATION at '{current_path}': private ground-truth token '{tok}' detected in metadata string value '{val_str}'."
            )


def verify_no_ground_truth_leakage(
    data: Any,
    path: str = "$",
    in_audited_metadata: bool = False,
) -> None:
    """
    Recursively audits any Python data structure (dict, list, tuple, set, primitive)
    to ensure ZERO evaluator-only ground truth fields or indicators are leaked.
    Audits dictionary keys with case-folding, punctuation normalization, and prefix detection.
    Also recursively audits string values within allowed metadata fields
    ('channel', 'caller_id', 'reporter_id', 'phase') for smuggled evaluator ground-truth tokens.
    Raises GroundTruthLeakageError immediately if any violation is detected.
    """
    if isinstance(data, dict):
        for key, val in data.items():
            key_str = str(key)
            current_path = f"{path}.{key_str}"
            norm_key = "".join(c for c in unicodedata.normalize("NFKD", key_str.lower()) if c.isalnum())

            # Check exact forbidden keys, normalized tokens, or expected* prefixes
            if (
                key_str in FORBIDDEN_GROUND_TRUTH_KEYS
                or norm_key in NORMALIZED_FORBIDDEN_KEYS
                or norm_key.startswith("expected")
                or key_str.lower().startswith("expected_")
                or key_str.lower().startswith("expected-")
            ):
                raise GroundTruthLeakageError(
                    f"LEAKAGE VIOLATION at '{current_path}': private ground-truth key '{key_str}' detected."
                )

            is_audited_field = in_audited_metadata or (key_str.lower() in AUDITED_METADATA_FIELDS)
            verify_no_ground_truth_leakage(val, current_path, in_audited_metadata=is_audited_field)
    elif isinstance(data, (list, tuple, set, frozenset)):
        for idx, item in enumerate(data):
            current_path = f"{path}[{idx}]"
            verify_no_ground_truth_leakage(item, current_path, in_audited_metadata=in_audited_metadata)
    elif isinstance(data, str):
        path_segments = [s.strip("[]0123456789") for s in path.lower().replace("[", ".").split(".")]
        is_audited_path = any(f in path_segments for f in AUDITED_METADATA_FIELDS)
        if in_audited_metadata or is_audited_path:
            _audit_metadata_string_value(data, path)


# =============================================================================
# 2. Canonical Enums
# =============================================================================

class LocationPrecision(str, Enum):
    """
    Canonical location precision tiers as specified in docs/data-schema.md Section 2.1
    and frontend/src/types/incident.ts line 38.
    """
    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


class ReportSource(str, Enum):
    """
    Canonical report sources specified in docs/data-schema.md Section 2.1.
    For simulator-generated dispatches, 'simulator' is strictly enforced.
    """
    MANUAL = "manual"
    SIMULATOR = "simulator"
    DATASET = "dataset"
    OTHER = "other"


class GroundTruthRelationType(str, Enum):
    """
    Evaluation ground truth relation taxonomy.
    Includes canonical relationship types from docs/data-schema.md Section 2.4
    (INITIAL, CORROBORATING, DUPLICATE, RELATED, UNCERTAIN)
    plus NOISE for unrelated background distractor dispatches.
    """
    INITIAL = "INITIAL"
    CORROBORATING = "CORROBORATING"
    DUPLICATE = "DUPLICATE"
    RELATED = "RELATED"
    UNCERTAIN = "UNCERTAIN"
    NOISE = "NOISE"


class GroundTruthIncidentType(str, Enum):
    """
    Canonical crisis hazard categories from docs/data-schema.md Section 2.2
    and ml/schemas/incident_output.json.
    """
    FLOOD_FLASH_FLOOD = "FLOOD_FLASH_FLOOD"
    FIRE_WILDFIRE_EXPLOSION = "FIRE_WILDFIRE_EXPLOSION"
    STRUCTURAL_COLLAPSE = "STRUCTURAL_COLLAPSE"
    EARTHQUAKE_LANDSLIDE = "EARTHQUAKE_LANDSLIDE"
    SEVERE_WEATHER_STORM = "SEVERE_WEATHER_STORM"
    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"
    CIVIL_UNREST_ACTIVE_THREAT = "CIVIL_UNREST_ACTIVE_THREAT"
    UTILITY_INFRASTRUCTURE_FAILURE = "UTILITY_INFRASTRUCTURE_FAILURE"
    OTHER_GENERAL_INCIDENT = "OTHER_GENERAL_INCIDENT"


class GroundTruthUrgency(str, Enum):
    """
    Canonical operational urgency tiers from docs/data-schema.md Section 2.2
    and ml/schemas/incident_output.json.
    """
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExpectedQueueDirection(str, Enum):
    """
    Deterministic queue escalation direction assertions.
    """
    ESCALATE = "ESCALATE"
    ESCALATE_TO_TOP = "ESCALATE_TO_TOP"
    STABLE = "STABLE"
    DEESCALATE = "DEESCALATE"
    LOW_PRIORITY = "LOW_PRIORITY"
    NO_ASSERTION = "NO_ASSERTION"


# =============================================================================
# 3. Location Model
# =============================================================================

class LocationHint(BaseModel):
    """
    Location hint sub-schema matching docs/data-schema.md Section 2.1.
    Preserves uncertainty without GPS hallucination (ADR-009).

    Invariants Enforced:
      1. Latitude and Longitude must both be present or both be null.
      2. precision='unknown' requires latitude=None and longitude=None.
      3. precision='exact' requires both coordinates to be non-null.
      4. precision='approximate' allows both coordinates or both null.
      5. Coordinates bounded: lat [-90, 90], lon [-180, 180].
    """
    model_config = ConfigDict(extra="forbid")

    raw_text: Optional[str] = Field(
        default=None,
        description="Raw location text snippet as spoken/typed (e.g. 'near Patia square').",
    )
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Geocoded latitude or None if unverified.",
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Geocoded longitude or None if unverified.",
    )
    precision: LocationPrecision = Field(
        default=LocationPrecision.UNKNOWN,
        description="Confidence precision: 'exact', 'approximate', or 'unknown'.",
    )

    @model_validator(mode="after")
    def validate_coordinates_and_precision(self) -> "LocationHint":
        has_lat = self.latitude is not None
        has_lon = self.longitude is not None

        # Rule 1: Lat and lon must either BOTH be present or BOTH absent
        if has_lat != has_lon:
            raise ValueError(
                f"Incomplete coordinate pair: latitude ({self.latitude}) and longitude ({self.longitude}) "
                "must either both be provided or both be null."
            )

        # Rule 2: precision unknown requires both null
        if self.precision == LocationPrecision.UNKNOWN and (has_lat or has_lon):
            raise ValueError(
                f"Contradictory location state: precision is 'unknown' but coordinates were provided "
                f"({self.latitude}, {self.longitude}). Unknown precision requires null coordinates."
            )

        # Rule 3: precision exact requires both coordinates
        if self.precision == LocationPrecision.EXACT and (not has_lat or not has_lon):
            raise ValueError(
                "Contradictory location state: precision is 'exact' but coordinates are missing. "
                "Exact precision requires non-null latitude and longitude."
            )

        return self


# =============================================================================
# 4. Typed Metadata Model
# =============================================================================

class ReportMetadata(BaseModel):
    """
    Typed metadata sub-schema matching docs/data-schema.md Section 2.1.
    Eliminates loose unvalidated dictionaries while preserving extensible metadata.
    Guarantees that private ground-truth fields cannot be hidden inside metadata.
    """
    model_config = ConfigDict(extra="allow")

    scenario_id: Optional[str] = Field(
        default=None,
        description="Scenario template identifier (e.g. 'flood_rasulgarh').",
    )
    event_id: Optional[str] = Field(
        default=None,
        description="Deterministic scenario event identifier (e.g. 'evt-001').",
    )
    reporter_id: Optional[str] = Field(
        default=None,
        description="Simulated synthetic reporter handle (e.g. 'sim-source-001').",
    )
    caller_id: Optional[str] = Field(
        default=None,
        description="Simulated caller handle alias.",
    )
    channel: Optional[str] = Field(
        default=None,
        description="Simulated ingestion channel (e.g. 'phone', 'sms', 'radio').",
    )
    phase: Optional[str] = Field(
        default=None,
        description="Scenario timeline phase tag (e.g. 'T0', 'T+2m').",
    )
    batch_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Sequential index within injection batch.",
    )

    @model_validator(mode="after")
    def check_no_leakage_in_metadata(self) -> "ReportMetadata":
        # Recursively audit extra fields for ground-truth leakage
        data_dict = self.model_dump()
        verify_no_ground_truth_leakage(data_dict, path="metadata")
        return self


# =============================================================================
# 5. Public Raw Report Payload
# =============================================================================

class RawReportPayload(BaseModel):
    """
    Public dispatch payload matching docs/data-schema.md Section 2.1 exactly.
    This is what is sent over the wire to Daksh's POST /reports endpoint.

    Simulator Invariants:
      - source MUST be 'simulator'
      - is_synthetic MUST be True (cannot be False)
      - text length between 3 and 4,000 characters
      - reported_at must be timezone-aware (serializes to ISO-8601 UTC with explicit 'Z')
      - extra fields are strictly forbidden (prevents GroundTruth leakage)
    """
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique report identifier (e.g. 'rep-sim-001' or UUIDv4).",
    )
    text: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Dispatch text content (length 3 to 4,000 characters).",
    )
    source: Literal["simulator"] = Field(
        default="simulator",
        description="Source of report. Strictly 'simulator' for simulator dispatches.",
    )
    is_synthetic: Literal[True] = Field(
        default=True,
        description="Synthetic data indicator. Must strictly be True for simulator dispatches.",
    )
    reported_at: datetime = Field(
        ...,
        description="ISO-8601 UTC timestamp of report event. Must be timezone-aware.",
    )
    location_hint: Optional[LocationHint] = Field(
        default=None,
        description="Pre-extracted or provided location hint with precision.",
    )
    metadata: Optional[ReportMetadata] = Field(
        default=None,
        description="Typed metadata container (scenario_id, event_id, etc.).",
    )

    @field_validator("reported_at", mode="before")
    @classmethod
    def parse_reported_at(cls, v: Any) -> datetime:
        """Parses string or datetime, validating timezone awareness."""
        if isinstance(v, str):
            # Parse ISO string
            iso_str = v.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                raise ValueError("reported_at string must contain timezone (e.g. 'Z' or '+00:00').")
            return dt
        elif isinstance(v, datetime):
            if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
                raise ValueError("reported_at datetime must be timezone-aware.")
            return v
        raise ValueError(f"Invalid datetime format: {v}")

    @field_serializer("reported_at", when_used="json-unless-none")
    def serialize_reported_at(self, dt: datetime) -> str:
        """
        Serializes datetime strictly to ISO-8601 UTC with 'Z' suffix.
        Preserves microsecond precision.
        """
        utc_dt = dt.astimezone(timezone.utc)
        if utc_dt.microsecond > 0:
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# =============================================================================
# 6. Private Evaluation Ground-Truth Model
# =============================================================================

class GroundTruth(BaseModel):
    """
    Private evaluation ground truth retained exclusively by Pankaj's test harness.
    Used to benchmark:
      - Aryan's ML predictions (hazard type, urgency tier, people-at-risk count)
      - Daksh's correlation engine (incident grouping, duplicate vs corroboration)

    This model is NEVER sent to the backend API or exposed to the ML pipeline.
    Fields are optional to represent uncertain, ambiguous, or partial ground truth.
    """
    model_config = ConfigDict(extra="forbid")

    incident_group: Optional[str] = Field(
        default=None,
        description="Known situation/cluster ID (e.g. 'bbsr-flood-01') for clustering evaluation.",
    )
    expected_incident_type: Optional[GroundTruthIncidentType] = Field(
        default=None,
        description="Ground-truth crisis hazard category.",
    )
    expected_urgency: Optional[GroundTruthUrgency] = Field(
        default=None,
        description="Ground-truth operational urgency tier.",
    )
    expected_people_at_risk: Optional[bool] = Field(
        default=None,
        description="True if human lives are in imminent danger.",
    )
    expected_people_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated victim count, or None if ambiguous/unspecified.",
    )
    relation_type: Optional[GroundTruthRelationType] = Field(
        default=None,
        description="Ground-truth relationship to existing situation (INITIAL, CORROBORATING, DUPLICATE, RELATED, UNCERTAIN, NOISE).",
    )
    expected_direction: Optional[ExpectedQueueDirection] = Field(
        default=None,
        description="Expected queue movement enum.",
    )
    expected_needs_review: Optional[bool] = Field(
        default=None,
        description="True = explicitly expected review, False = explicitly expected no review, None = unlabelled/do not score.",
    )
    expected_location_text: Optional[str] = Field(
        default=None,
        description="Ground-truth expected location text string.",
    )
    expected_latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Ground-truth expected latitude.",
    )
    expected_longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Ground-truth expected longitude.",
    )
    expected_required_response: Optional[List[str]] = Field(
        default=None,
        description="Explicit ground-truth tactical response agencies required.",
    )
    expected_actionable: Optional[bool] = Field(
        default=None,
        description="Explicit indicator if the report represents an actionable emergency vs drill/rumor.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Human evaluator context or justification for this ground truth.",
    )


# =============================================================================
# 7. Scenario Event Model
# =============================================================================

class ScenarioEvent(BaseModel):
    """
    Represents an atomic, timed scenario event combining:
      - dispatch: Public RawReportPayload sent to Karen's Ear
      - ground_truth: Private GroundTruth retained for evaluation

    Architectural Isolation:
      public_payload() returns ONLY the dispatch dictionary and recursively audits
      for any GroundTruth leakage before returning.
    """
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique scenario event identifier (e.g. 'evt-001').",
    )
    delay_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Delay in seconds before injecting this dispatch in real-time playback.",
    )
    dispatch: RawReportPayload = Field(
        ...,
        description="Public raw report payload to be submitted to POST /reports.",
    )
    ground_truth: GroundTruth = Field(
        ...,
        description="Private evaluation ground truth retained by test harness.",
    )

    @model_validator(mode="after")
    def validate_event_id_consistency(self) -> "ScenarioEvent":
        """Ensures ScenarioEvent.event_id matches dispatch.metadata.event_id if present."""
        if self.dispatch.metadata and self.dispatch.metadata.event_id is not None:
            if self.dispatch.metadata.event_id != self.event_id:
                raise ValueError(
                    f"ScenarioEvent.event_id mismatch: event_id is '{self.event_id}' but "
                    f"dispatch.metadata.event_id is '{self.dispatch.metadata.event_id}'."
                )
        return self

    def public_payload(self) -> Dict[str, Any]:
        """
        Returns the strictly validated public payload for transmission to Karen's Ear.
        Guarantees zero GroundTruth fields are included via allowlisted projection and recursive safety check.
        """
        payload = self.dispatch.model_dump(mode="json")
        # Enforce metadata egress allowlist to guarantee zero arbitrary private field leakage
        if "metadata" in payload and isinstance(payload["metadata"], dict):
            payload["metadata"] = {
                k: v for k, v in payload["metadata"].items() if k in ALLOWED_PUBLIC_METADATA_KEYS
            }
        verify_no_ground_truth_leakage(payload, path="public_payload")
        return payload
