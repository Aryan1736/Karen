"""
Karen's Ear — Machine Learning & Emergency Intelligence Pipeline.

Foundation package for Aryan's ML pipeline modules:
- Preprocessing & normalization (ml.preprocessing)
- Crisis classification (ml.classification)
- Feature-derived operational urgency (ml.urgency)
- Entity & location extraction with no hallucination (ml.extraction)
- Required response mapping (ml.response)
- Dense semantic embeddings (ml.embeddings)
- Confidence calibration & quality gating (ml.confidence)
- Pipeline orchestration (ml.pipeline)

The canonical output contract remains strictly defined by ml/schemas/incident_output.json.
"""

from ml.config import (
    CANONICAL_INCIDENT_TYPES,
    CANONICAL_PRECISION_LEVELS,
    CANONICAL_PROCESSING_STATUSES,
    CANONICAL_RESPONSE_TYPES,
    CANONICAL_URGENCY_LEVELS,
    ComponentResult,
    MLConfig,
    ModelMetadata,
    ProcessingContext,
    get_ml_config,
    reset_ml_config,
    set_ml_config,
)
from ml.exceptions import (
    MLBaseError,
    MLConfigurationError,
    MLInferenceError,
    MLInputError,
    MLModelError,
)
from ml.logging_utils import (
    MLJsonFormatter,
    MLLoggerAdapter,
    get_ml_logger,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Configuration & Taxonomies
    "MLConfig",
    "get_ml_config",
    "set_ml_config",
    "reset_ml_config",
    "CANONICAL_INCIDENT_TYPES",
    "CANONICAL_URGENCY_LEVELS",
    "CANONICAL_PRECISION_LEVELS",
    "CANONICAL_RESPONSE_TYPES",
    "CANONICAL_PROCESSING_STATUSES",
    # Typed Contexts
    "ModelMetadata",
    "ProcessingContext",
    "ComponentResult",
    # Exceptions
    "MLBaseError",
    "MLConfigurationError",
    "MLInputError",
    "MLInferenceError",
    "MLModelError",
    # Observability
    "get_ml_logger",
    "MLLoggerAdapter",
    "MLJsonFormatter",
]
