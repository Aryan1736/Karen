"""
Karen's Ear — Canonical Schemas & Common Enums
Frozen enums matching gemini.md, docs/api-contract.md, and docs/data-schema.md.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, PlainSerializer


def format_datetime_utc(dt: datetime | None) -> str | None:
    """Serialize datetime to strict ISO-8601 UTC format (YYYY-MM-DDTHH:MM:SSZ)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


IsoUtcDatetime = Annotated[
    datetime,
    PlainSerializer(format_datetime_utc, return_type=str, when_used="json"),
]


class KarenBaseModel(BaseModel):
    """Base Pydantic model with ORM attribute support and alias population."""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class IncidentType(str, Enum):
    """Standardized hazard categories from CrisiText and constitution."""
    FLOOD_FLASH_FLOOD = "FLOOD_FLASH_FLOOD"
    FIRE_WILDFIRE_EXPLOSION = "FIRE_WILDFIRE_EXPLOSION"
    STRUCTURAL_COLLAPSE = "STRUCTURAL_COLLAPSE"
    EARTHQUAKE_LANDSLIDE = "EARTHQUAKE_LANDSLIDE"
    SEVERE_WEATHER_STORM = "SEVERE_WEATHER_STORM"
    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"
    CIVIL_UNREST_ACTIVE_THREAT = "CIVIL_UNREST_ACTIVE_THREAT"
    UTILITY_INFRASTRUCTURE_FAILURE = "UTILITY_INFRASTRUCTURE_FAILURE"
    OTHER_GENERAL_INCIDENT = "OTHER_GENERAL_INCIDENT"


class UrgencyLevel(str, Enum):
    """Operational urgency tiers derived from life-safety and hazard features."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PriorityLevel(str, Enum):
    """Ranked operational triage priority tiers."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class LocationPrecision(str, Enum):
    """Geographic confidence precision."""
    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


class IncidentStatus(str, Enum):
    """State machine states for emergency incidents."""
    NEW = "NEW"
    ANALYZING = "ANALYZING"
    ACTIVE = "ACTIVE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    FALSE_REPORT = "FALSE_REPORT"


class RelationshipType(str, Enum):
    """Fusion join relationship types."""
    INITIAL = "INITIAL"
    CORROBORATING = "CORROBORATING"
    DUPLICATE = "DUPLICATE"
    RELATED = "RELATED"
    UNCERTAIN = "UNCERTAIN"


class ResponseCapability(str, Enum):
    """Tactical responder agency services."""
    SEARCH_AND_RESCUE = "SEARCH_AND_RESCUE"
    MEDICAL_EMS = "MEDICAL_EMS"
    FIRE_HAZMAT = "FIRE_HAZMAT"
    POLICE_SECURITY = "POLICE_SECURITY"
    PUBLIC_WORKS_UTILITY = "PUBLIC_WORKS_UTILITY"


class SourceType(str, Enum):
    """Origin of raw incoming report."""
    MANUAL = "manual"
    SIMULATOR = "simulator"
    DATASET = "dataset"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    """NLP and pipeline processing outcome."""
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class SimulationStatus(str, Enum):
    """Simulator scenario run state."""
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
