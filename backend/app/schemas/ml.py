"""
Karen's Ear — Machine Learning Pipeline Output Schemas
Adheres strictly to ml/schemas/incident_output.json and docs/data-schema.md Section 2.2.
"""
from typing import Any, Optional
from pydantic import Field, model_validator

from backend.app.schemas.common import (
    IncidentType,
    IsoUtcDatetime,
    KarenBaseModel,
    LocationPrecision,
    ProcessingStatus,
    ResponseCapability,
    UrgencyLevel,
)


class TypePrediction(KarenBaseModel):
    """Predicted hazard category with confidence."""
    label: Optional[IncidentType] = Field(
        default=None,
        description="Hazard classification label or null if unclassifiable",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score in range [0.0, 1.0]",
    )


class UrgencyPrediction(KarenBaseModel):
    """Feature-derived operational urgency tier with confidence."""
    label: Optional[UrgencyLevel] = Field(
        default=None,
        description="Operational urgency level derived from life-safety features",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score in range [0.0, 1.0]",
    )


class LocationPrediction(KarenBaseModel):
    """Extracted location entity with coordinates if verified without hallucination."""
    text: Optional[str] = Field(default=None, description="Extracted location text")
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Verified latitude or null",
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Verified longitude or null",
    )
    precision: LocationPrecision = Field(
        default=LocationPrecision.UNKNOWN,
        description="Coordinate precision",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score",
    )


class RiskPrediction(KarenBaseModel):
    """Detected trapped or at-risk person count."""
    count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Assessed victims/trapped individuals count",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score in range [0.0, 1.0]",
    )


class ResponseNeed(KarenBaseModel):
    """Tactical responder agency requirement with confidence."""
    type: ResponseCapability = Field(..., description="Tactical capability type")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score in range [0.0, 1.0]",
    )


class EntityToken(KarenBaseModel):
    """Extracted named entity token."""
    text: str = Field(..., description="Extracted entity string")
    type: str = Field(..., description="Entity category label (e.g. LOCATION, HAZARD)")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Token confidence score",
    )


class MLPredictionOutput(KarenBaseModel):
    """
    Contract for ML/NLP analysis output (ml/schemas/incident_output.json).
    - If embedding is absent, it is valid (None).
    - If embedding is provided, it must be exactly 384 floats.
    - If embedding is explicitly passed as null, it is rejected.
    """
    report_id: str = Field(..., description="ID of originating raw report")
    model_version: str = Field(..., description="Model descriptor version")
    incident_type: TypePrediction
    urgency: UrgencyPrediction
    location: LocationPrediction
    people_at_risk: RiskPrediction
    required_response: list[ResponseNeed] = Field(default_factory=list)
    entities: list[EntityToken] = Field(default_factory=list)
    embedding_reference: Optional[str] = Field(
        default=None,
        description="Pointer to external vector reference if used",
    )
    embedding: Optional[list[float]] = Field(
        default=None,
        min_length=384,
        max_length=384,
        description="Normalized 384-dimensional dense semantic vector",
    )
    overall_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Aggregated model confidence",
    )
    processing_status: ProcessingStatus = Field(..., description="Operational status outcome")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings or fallbacks")

    @model_validator(mode="before")
    @classmethod
    def check_embedding_not_explicit_null(cls, data: Any) -> Any:
        if isinstance(data, dict) and "embedding" in data and data["embedding"] is None:
            raise ValueError(
                "Field 'embedding' may be omitted when absent, but cannot be explicitly null when present."
            )
        return data


class MLPredictionResponse(MLPredictionOutput):
    """Database representation of an ML prediction."""
    prediction_id: str
    created_at: IsoUtcDatetime
