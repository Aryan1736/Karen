"""
Karen's Ear — Centralized ML Pipeline Configuration.

Provides structured, environment-aware configuration and lightweight typed
containers for upcoming ML modules. All default values strictly mirror the
project specifications codified in gemini.md, architecture/ml-pipeline.md,
and ml/schemas/incident_output.json.

IMPORTANT:
- Models are NOT loaded here.
- Secrets are NOT hardcoded.
- Values not yet frozen in the architecture remain configurable with documented TODOs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from ml.exceptions import MLConfigurationError

# ==============================================================================
# Canonical Taxonomies & Enums
# (Strictly matching ml/schemas/incident_output.json)
# ==============================================================================

CANONICAL_INCIDENT_TYPES: tuple[str, ...] = (
    "FLOOD_FLASH_FLOOD",
    "FIRE_WILDFIRE_EXPLOSION",
    "STRUCTURAL_COLLAPSE",
    "EARTHQUAKE_LANDSLIDE",
    "SEVERE_WEATHER_STORM",
    "MEDICAL_EMERGENCY",
    "CIVIL_UNREST_ACTIVE_THREAT",
    "UTILITY_INFRASTRUCTURE_FAILURE",
    "OTHER_GENERAL_INCIDENT",
)

CANONICAL_URGENCY_LEVELS: tuple[str, ...] = (
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
)

CANONICAL_PRECISION_LEVELS: tuple[str, ...] = (
    "exact",
    "approximate",
    "unknown",
)

CANONICAL_RESPONSE_TYPES: tuple[str, ...] = (
    "SEARCH_AND_RESCUE",
    "MEDICAL_EMS",
    "FIRE_HAZMAT",
    "POLICE_SECURITY",
    "PUBLIC_WORKS_UTILITY",
)

CANONICAL_PROCESSING_STATUSES: tuple[str, ...] = (
    "SUCCESS",
    "PARTIAL",
    "FAILED",
    "NEEDS_REVIEW",
)

# Canonical default dense embedding backbone
DEFAULT_EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"

# Reference / candidate models noted in architecture
CANDIDATE_EMBEDDING_MODELS: tuple[str, ...] = (
    DEFAULT_EMBEDDING_MODEL_NAME,
    "crisistransformers/CT-M1-Complete-SE",
)

# Default component confidence weights for weighted harmonic mean (Feature 9)
# NOTE: The repository architecture specifies a weighted harmonic mean for overall
# ML confidence, but component weights were not previously specified in repo architecture or ADRs.
# The weights below represent a configurable provisional baseline subject to operational calibration.
DEFAULT_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "incident_type": 0.30,
    "urgency": 0.25,
    "location": 0.20,
    "people_at_risk": 0.15,
    "required_response": 0.10,
}


# ==============================================================================
# Lightweight Typed Structures for ML Pipeline
# (Advisory metadata and internal component execution contexts)
# ==============================================================================


@dataclass(frozen=True)
class ModelMetadata:
    """Lightweight metadata descriptor for an ML model or subcomponent."""

    model_name: str
    version: str
    task: str
    device: str = "cpu"
    dimension: int | None = None


@dataclass
class ProcessingContext:
    """
    Encapsulates the runtime context of an emergency report undergoing ML analysis.
    Does NOT duplicate or replace the canonical ML output schema.
    """

    report_id: str
    raw_text: str
    location_hint: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentResult:
    """
    Standardized internal result emitted by an individual ML subcomponent
    (e.g., classification, extraction, urgency, embeddings) before pipeline packaging.
    """

    component: str
    status: str = "SUCCESS"  # SUCCESS, PARTIAL, FAILED, NEEDS_REVIEW
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    warnings: list[str] = field(default_factory=list)


# ==============================================================================
# Centralized ML Configuration
# ==============================================================================


@dataclass(frozen=True)
class MLConfig:
    """
    Centralized, immutable configuration for Karen's Ear ML pipeline.
    All defaults originate directly from project architecture contracts.
    """

    # Model and version identifiers
    model_version: str = "all-MiniLM-L6-v2+heuristic-v1"
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL_NAME
    embedding_dimension: int = 384
    device: str = "cpu"

    # Input constraints (docs/api-contract.md and architecture/ml-pipeline.md)
    min_report_text_length: int = 3
    max_report_text_length: int = 4000

    # Confidence and quality thresholds (gemini.md Section 8 & architecture/ml-pipeline.md Section 4.3)
    confidence_review_threshold: float = 0.60

    # Component confidence weights for weighted harmonic mean (Feature 9)
    # Provisional baseline weights; fully externalized and configurable
    confidence_weight_incident_type: float = 0.30
    confidence_weight_urgency: float = 0.25
    confidence_weight_location: float = 0.20
    confidence_weight_people_at_risk: float = 0.15
    confidence_weight_required_response: float = 0.10

    @property
    def confidence_weights(self) -> dict[str, float]:
        """Returns the dictionary of configured component confidence weights."""
        return {
            "incident_type": self.confidence_weight_incident_type,
            "urgency": self.confidence_weight_urgency,
            "location": self.confidence_weight_location,
            "people_at_risk": self.confidence_weight_people_at_risk,
            "required_response": self.confidence_weight_required_response,
        }

    # Dynamic similarity thresholds (gemini.md Section 9 & architecture/testing.md Section 3.1)
    duplicate_similarity_threshold: float = 0.85
    corroboration_similarity_threshold: float = 0.70

    # Operational Urgency derivation thresholds (architecture/ml-pipeline.md Section 3.3)
    urgency_threshold_critical: float = 80.0
    urgency_threshold_high: float = 60.0
    urgency_threshold_medium: float = 35.0

    # Operational Urgency feature weights (architecture/ml-pipeline.md Section 3.3)
    urgency_weight_life_safety: float = 0.50
    urgency_weight_hazard_velocity: float = 0.30
    urgency_weight_vulnerability: float = 0.20

    # Observability
    log_level: str = "INFO"

    # Optional component model identifiers (Configurable hooks for future features)
    # TODO (Feature 2): Configure classification backbone (e.g., zero-shot or DeBERTa-v3-small)
    classification_model_name: str | None = None
    # TODO (Feature 4): Configure NER entity extractor (ADR-002: spacy en_core_web_sm vs bert-base-NER)
    ner_model_name: str | None = None

    # Lightweight mode for constrained deployment environments (e.g. Render Free 512MB RAM)
    lightweight_mode: bool = False

    def validate(self) -> None:
        """Validates configuration values against acceptable operational bounds."""
        if self.min_report_text_length <= 0:
            raise MLConfigurationError(
                f"min_report_text_length must be positive, got {self.min_report_text_length}"
            )
        if self.max_report_text_length <= self.min_report_text_length:
            raise MLConfigurationError(
                f"max_report_text_length ({self.max_report_text_length}) must exceed "
                f"min_report_text_length ({self.min_report_text_length})"
            )
        if not (0.0 <= self.confidence_review_threshold <= 1.0):
            raise MLConfigurationError(
                f"confidence_review_threshold must be between 0.0 and 1.0, got {self.confidence_review_threshold}"
            )
        if not (0.0 <= self.duplicate_similarity_threshold <= 1.0):
            raise MLConfigurationError(
                f"duplicate_similarity_threshold must be between 0.0 and 1.0, got {self.duplicate_similarity_threshold}"
            )
        if not (0.0 <= self.corroboration_similarity_threshold <= 1.0):
            raise MLConfigurationError(
                f"corroboration_similarity_threshold must be between 0.0 and 1.0, got {self.corroboration_similarity_threshold}"
            )
        if self.corroboration_similarity_threshold > self.duplicate_similarity_threshold:
            raise MLConfigurationError(
                f"corroboration_similarity_threshold ({self.corroboration_similarity_threshold}) "
                f"must not exceed duplicate_similarity_threshold ({self.duplicate_similarity_threshold})"
            )
        if self.embedding_dimension <= 0:
            raise MLConfigurationError(
                f"embedding_dimension must be positive, got {self.embedding_dimension}"
            )
        for comp_name, w in self.confidence_weights.items():
            if w <= 0.0:
                raise MLConfigurationError(
                    f"Confidence weight for '{comp_name}' must be strictly positive (> 0.0), got {w}"
                )

    @classmethod
    def from_env(cls) -> MLConfig:
        """
        Constructs MLConfig, overriding defaults with environment variables when present.
        Ensures robust type parsing and validation.
        """

        def _get_float(key: str, default: float) -> float:
            val = os.getenv(key)
            if val is None or not val.strip():
                return default
            try:
                return float(val.strip())
            except ValueError:
                raise MLConfigurationError(f"Environment variable '{key}' must be a float, got: {val!r}")

        def _get_int(key: str, default: int) -> int:
            val = os.getenv(key)
            if val is None or not val.strip():
                return default
            try:
                return int(val.strip())
            except ValueError:
                raise MLConfigurationError(f"Environment variable '{key}' must be an integer, got: {val!r}")

        def _get_bool(key: str, default: bool) -> bool:
            val = os.getenv(key)
            if val is None or not val.strip():
                return default
            return val.strip().lower() in ("1", "true", "yes", "on")

        config = cls(
            model_version=os.getenv("ML_MODEL_VERSION", "all-MiniLM-L6-v2+heuristic-v1").strip(),
            embedding_model_name=os.getenv(
                "ML_MODEL_NAME",
                os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL_NAME),
            ).strip(),
            embedding_dimension=_get_int("EMBEDDING_DIMENSION", 384),
            device=os.getenv("ML_DEVICE", "cpu").strip().lower(),
            min_report_text_length=_get_int("MIN_REPORT_TEXT_LENGTH", 3),
            max_report_text_length=_get_int("MAX_REPORT_TEXT_LENGTH", 4000),
            confidence_review_threshold=_get_float("CONFIDENCE_REVIEW_THRESHOLD", 0.60),
            duplicate_similarity_threshold=_get_float("DUPLICATE_SIMILARITY_THRESHOLD", 0.85),
            corroboration_similarity_threshold=_get_float("CORROBORATION_SIMILARITY_THRESHOLD", 0.70),
            urgency_threshold_critical=_get_float("URGENCY_THRESHOLD_CRITICAL", 80.0),
            urgency_threshold_high=_get_float("URGENCY_THRESHOLD_HIGH", 60.0),
            urgency_threshold_medium=_get_float("URGENCY_THRESHOLD_MEDIUM", 35.0),
            urgency_weight_life_safety=_get_float("URGENCY_WEIGHT_LIFE_SAFETY", 0.50),
            urgency_weight_hazard_velocity=_get_float("URGENCY_WEIGHT_HAZARD_VELOCITY", 0.30),
            urgency_weight_vulnerability=_get_float("URGENCY_WEIGHT_VULNERABILITY", 0.20),
            confidence_weight_incident_type=_get_float("CONFIDENCE_WEIGHT_INCIDENT_TYPE", 0.30),
            confidence_weight_urgency=_get_float("CONFIDENCE_WEIGHT_URGENCY", 0.25),
            confidence_weight_location=_get_float("CONFIDENCE_WEIGHT_LOCATION", 0.20),
            confidence_weight_people_at_risk=_get_float("CONFIDENCE_WEIGHT_PEOPLE_AT_RISK", 0.15),
            confidence_weight_required_response=_get_float("CONFIDENCE_WEIGHT_REQUIRED_RESPONSE", 0.10),
            log_level=os.getenv("ML_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")).strip().upper(),
            classification_model_name=os.getenv("CLASSIFICATION_MODEL_NAME"),
            ner_model_name=os.getenv("NER_MODEL_NAME"),
            lightweight_mode=_get_bool("ML_LIGHTWEIGHT_MODE", False),
        )
        config.validate()
        return config


# Default singleton configuration instance
_default_config: MLConfig | None = None


def get_ml_config() -> MLConfig:
    """
    Returns the centralized ML configuration.
    Lazily initializes from environment variables on first access.
    """
    global _default_config
    if _default_config is None:
        _default_config = MLConfig.from_env()
    return _default_config


def set_ml_config(config: MLConfig) -> None:
    """
    Overrides the active ML configuration (primarily used in testing).
    Validates before setting.
    """
    global _default_config
    config.validate()
    _default_config = config


def reset_ml_config() -> None:
    """Resets the singleton configuration to force reload from environment."""
    global _default_config
    _default_config = None
