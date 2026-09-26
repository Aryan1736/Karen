"""
Karen's Ear — Feature 1 Foundation Tests.

Validates:
- ml package and all subpackages cleanly import
- No circular import dependencies exist
- Centralized configuration loads correctly with canonical defaults
- Configuration does NOT trigger model loading
- Configuration bounds validation and environment overrides function properly
- Exceptions are typed and inherit cleanly from MLBaseError
- Logging utilities initialize, format valid JSON, and protect sensitive data
- Lightweight typed structures function as expected
"""

import importlib
import json
import logging
import os
import sys
from unittest.mock import patch

import pytest

from ml import (
    CANONICAL_INCIDENT_TYPES,
    CANONICAL_PRECISION_LEVELS,
    CANONICAL_PROCESSING_STATUSES,
    CANONICAL_RESPONSE_TYPES,
    CANONICAL_URGENCY_LEVELS,
    ComponentResult,
    MLBaseError,
    MLConfig,
    MLConfigurationError,
    MLInferenceError,
    MLInputError,
    MLJsonFormatter,
    MLLoggerAdapter,
    MLModelError,
    ModelMetadata,
    ProcessingContext,
    get_ml_config,
    get_ml_logger,
    reset_ml_config,
    set_ml_config,
)


# ==============================================================================
# 1. Package and Subpackage Import Tests
# ==============================================================================


def test_ml_package_import():
    """Verify that root ml package imports cleanly and exposes expected public symbols."""
    import ml

    assert hasattr(ml, "__version__")
    assert ml.__version__ == "0.1.0"
    assert hasattr(ml, "MLConfig")
    assert hasattr(ml, "get_ml_config")
    assert hasattr(ml, "MLBaseError")
    assert hasattr(ml, "get_ml_logger")


@pytest.mark.parametrize(
    "subpackage_name",
    [
        "ml.preprocessing",
        "ml.classification",
        "ml.urgency",
        "ml.extraction",
        "ml.response",
        "ml.embeddings",
        "ml.confidence",
        "ml.pipeline",
        "ml.tests",
    ],
)
def test_all_subpackages_importable(subpackage_name: str):
    """Verify that every ML subpackage can be cleanly imported without error."""
    module = importlib.import_module(subpackage_name)
    assert module is not None


def test_no_circular_imports():
    """Verify that importing all ML subpackages in any order has no circular dependencies."""
    subpackages = [
        "ml",
        "ml.config",
        "ml.exceptions",
        "ml.logging_utils",
        "ml.preprocessing",
        "ml.classification",
        "ml.urgency",
        "ml.extraction",
        "ml.response",
        "ml.embeddings",
        "ml.confidence",
        "ml.pipeline",
        "ml.tests",
    ]
    for subpkg in subpackages:
        mod = importlib.import_module(subpkg)
        assert mod is not None


# ==============================================================================
# 2. Configuration Tests
# ==============================================================================


def test_default_config_values():
    """Verify that default configuration strictly mirrors project specifications."""
    reset_ml_config()
    config = get_ml_config()

    # Model and version defaults
    assert config.model_version == "all-MiniLM-L6-v2+heuristic-v1"
    assert config.embedding_model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert config.embedding_dimension == 384
    assert config.device == "cpu"

    # Input constraints
    assert config.min_report_text_length == 3
    assert config.max_report_text_length == 4000

    # Operational thresholds
    assert config.confidence_review_threshold == 0.60
    assert config.duplicate_similarity_threshold == 0.85
    assert config.corroboration_similarity_threshold == 0.70

    # Urgency derivation weights and thresholds
    assert config.urgency_threshold_critical == 80.0
    assert config.urgency_threshold_high == 60.0
    assert config.urgency_threshold_medium == 35.0
    assert config.urgency_weight_life_safety == 0.50
    assert config.urgency_weight_hazard_velocity == 0.30
    assert config.urgency_weight_vulnerability == 0.20


def test_config_loading_does_not_load_heavy_models():
    """
    Ensure configuration module does NOT import or load heavyweight PyTorch or
    SentenceTransformer modules.
    """
    import inspect
    import ml.config

    # Inspect module source: ml.config must have zero imports of heavy ML libraries
    source = inspect.getsource(ml.config)
    assert "import torch" not in source
    assert "from torch" not in source
    assert "import sentence_transformers" not in source
    assert "from sentence_transformers" not in source
    assert "SentenceTransformer(" not in source

    # Verify executing from_env does not load models
    reset_ml_config()
    cfg = MLConfig.from_env()
    assert cfg.embedding_dimension == 384


def test_config_env_overrides():
    """Verify that environment variables correctly override configuration defaults."""
    env_vars = {
        "ML_MODEL_VERSION": "custom-v2",
        "ML_MODEL_NAME": "crisistransformers/CT-M1-Complete-SE",
        "EMBEDDING_DIMENSION": "768",
        "MIN_REPORT_TEXT_LENGTH": "5",
        "MAX_REPORT_TEXT_LENGTH": "2000",
        "CONFIDENCE_REVIEW_THRESHOLD": "0.75",
        "DUPLICATE_SIMILARITY_THRESHOLD": "0.90",
        "CORROBORATION_SIMILARITY_THRESHOLD": "0.80",
        "URGENCY_THRESHOLD_CRITICAL": "85.0",
        "URGENCY_WEIGHT_LIFE_SAFETY": "0.60",
        "ML_DEVICE": "cuda",
        "ML_LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        cfg = MLConfig.from_env()
        assert cfg.model_version == "custom-v2"
        assert cfg.embedding_model_name == "crisistransformers/CT-M1-Complete-SE"
        assert cfg.embedding_dimension == 768
        assert cfg.min_report_text_length == 5
        assert cfg.max_report_text_length == 2000
        assert cfg.confidence_review_threshold == 0.75
        assert cfg.duplicate_similarity_threshold == 0.90
        assert cfg.corroboration_similarity_threshold == 0.80
        assert cfg.urgency_threshold_critical == 85.0
        assert cfg.urgency_weight_life_safety == 0.60
        assert cfg.device == "cuda"
        assert cfg.log_level == "DEBUG"


def test_config_validation_bounds():
    """Verify that invalid configuration values raise typed MLConfigurationError."""
    # Invalid confidence threshold (> 1.0)
    with pytest.raises(MLConfigurationError, match="confidence_review_threshold"):
        MLConfig(confidence_review_threshold=1.5).validate()

    # Invalid negative text length
    with pytest.raises(MLConfigurationError, match="min_report_text_length"):
        MLConfig(min_report_text_length=-1).validate()

    # max_length <= min_length
    with pytest.raises(MLConfigurationError, match="max_report_text_length"):
        MLConfig(min_report_text_length=100, max_report_text_length=50).validate()

    # Corroboration threshold > duplicate threshold
    with pytest.raises(MLConfigurationError, match="corroboration_similarity_threshold"):
        MLConfig(
            duplicate_similarity_threshold=0.70,
            corroboration_similarity_threshold=0.85,
        ).validate()

    # Invalid float in env
    with patch.dict(os.environ, {"CONFIDENCE_REVIEW_THRESHOLD": "not_a_number"}, clear=False):
        with pytest.raises(MLConfigurationError, match="must be a float"):
            MLConfig.from_env()


def test_set_and_reset_ml_config():
    """Verify programmatic setting and resetting of the centralized config singleton."""
    reset_ml_config()
    custom = MLConfig(max_report_text_length=3000)
    set_ml_config(custom)
    assert get_ml_config().max_report_text_length == 3000
    reset_ml_config()
    assert get_ml_config().max_report_text_length == 4000


def test_canonical_taxonomies_match_contract():
    """Verify canonical taxonomy lists align with canonical schema enums."""
    assert "FLOOD_FLASH_FLOOD" in CANONICAL_INCIDENT_TYPES
    assert "CIVIL_UNREST_ACTIVE_THREAT" in CANONICAL_INCIDENT_TYPES
    assert len(CANONICAL_INCIDENT_TYPES) == 9

    assert set(CANONICAL_URGENCY_LEVELS) == {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert set(CANONICAL_PRECISION_LEVELS) == {"exact", "approximate", "unknown"}
    assert set(CANONICAL_PROCESSING_STATUSES) == {"SUCCESS", "PARTIAL", "FAILED", "NEEDS_REVIEW"}
    assert len(CANONICAL_RESPONSE_TYPES) == 5


# ==============================================================================
# 3. Exceptions Tests
# ==============================================================================


def test_exceptions_hierarchy():
    """Verify all custom ML exceptions inherit cleanly from MLBaseError."""
    assert issubclass(MLConfigurationError, MLBaseError)
    assert issubclass(MLInputError, MLBaseError)
    assert issubclass(MLInferenceError, MLBaseError)
    assert issubclass(MLModelError, MLBaseError)


def test_exception_details():
    """Verify exception message and optional diagnostic details serialization."""
    err = MLInputError("Text length violation", details={"length": 1, "min": 3})
    assert err.message == "Text length violation"
    assert err.details == {"length": 1, "min": 3}
    assert "Text length violation (details: {'length': 1, 'min': 3})" in str(err)


# ==============================================================================
# 4. Logging Utilities Tests
# ==============================================================================


def test_logger_initialization():
    """Verify logger adapter initialization and standard behavior."""
    logger = get_ml_logger(
        name="karen.ml.test",
        component="urgency",
        model_version="test-v1",
        report_id="rep-1234",
        processing_status="SUCCESS",
    )
    assert isinstance(logger, MLLoggerAdapter)
    assert logger.extra["component"] == "urgency"
    assert logger.extra["model_version"] == "test-v1"
    assert logger.extra["report_id"] == "rep-1234"
    assert logger.extra["processing_status"] == "SUCCESS"


def test_logger_context_derivation():
    """Verify with_context() creates a new adapter without mutating the parent."""
    base_logger = get_ml_logger(name="karen.ml.test", component="extraction")
    child_logger = base_logger.with_context(report_id="rep-5678", processing_status="PARTIAL")

    assert "report_id" not in base_logger.extra
    assert child_logger.extra["report_id"] == "rep-5678"
    assert child_logger.extra["component"] == "extraction"
    assert child_logger.extra["processing_status"] == "PARTIAL"


def test_json_formatter_and_secret_redaction():
    """
    Verify MLJsonFormatter outputs valid JSON and redacts secrets and raw text fields.
    """
    formatter = MLJsonFormatter()
    record = logging.LogRecord(
        name="karen.ml.classification",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Inference completed",
        args=(),
        exc_info=None,
    )
    # Attach ML context and sensitive extras
    record.component = "classification"
    record.model_version = "v1.0"
    record.report_id = "rep-999"
    record.processing_status = "SUCCESS"
    record.extra_context = {
        "api_key": "super_secret_key_12345",
        "password": "my_db_password",
        "raw_text": "Severe building collapse at Market Street with 5 people trapped!",
        "custom_metric": 42.5,
    }

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Inference completed"
    assert parsed["component"] == "classification"
    assert parsed["report_id"] == "rep-999"
    assert parsed["processing_status"] == "SUCCESS"

    # Verify secret redaction
    assert parsed["api_key"] == "[REDACTED_SECRET]"
    assert parsed["password"] == "[REDACTED_SECRET]"

    # Verify raw distress text suppression
    assert "[REDACTED_TEXT: length=64]" in parsed["raw_text"]
    assert "Severe building collapse" not in parsed["raw_text"]

    # Verify safe non-sensitive metric preserved
    assert parsed["custom_metric"] == 42.5


# ==============================================================================
# 5. Typed Structures Tests
# ==============================================================================


def test_model_metadata():
    """Verify ModelMetadata typed structure."""
    meta = ModelMetadata(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        version="v1",
        task="embedding",
        device="cpu",
        dimension=384,
    )
    assert meta.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert meta.dimension == 384
    assert meta.device == "cpu"


def test_processing_context():
    """Verify ProcessingContext typed structure."""
    ctx = ProcessingContext(
        report_id="rep-101",
        raw_text="Water rising quickly near hospital",
        location_hint={"raw_text": "City Hospital", "precision": "approximate"},
        metadata={"caller": "dispatch_radio"},
    )
    assert ctx.report_id == "rep-101"
    assert ctx.location_hint["precision"] == "approximate"
    assert ctx.metadata["caller"] == "dispatch_radio"


def test_component_result():
    """Verify ComponentResult typed structure."""
    res = ComponentResult(
        component="urgency",
        status="SUCCESS",
        data={"urgency_score": 85.0, "tier": "CRITICAL"},
        confidence=0.88,
        warnings=[],
    )
    assert res.component == "urgency"
    assert res.status == "SUCCESS"
    assert res.data["tier"] == "CRITICAL"
    assert res.confidence == 0.88
    assert len(res.warnings) == 0
