"""
Karen's Ear — Lightweight Mode Deployment Hotfix Tests
Verifies that ML_LIGHTWEIGHT_MODE enables memory-constrained runtime for Render Free (512MB RAM):
A. ML_LIGHTWEIGHT_MODE=false/unset preserves current behavior.
B. ML_LIGHTWEIGHT_MODE=true causes backend adapter to request include_embedding=False.
C. Lightweight classification uses the existing keyword path.
D. Lightweight output validates against the canonical ML schema.
E. Lightweight output contains no embedding.
F. A lightweight analysis does not import/load torch, sentence_transformers, or transformers.
G. Existing caller-supplied coordinates remain preserved.
H. Existing fallback/privacy behavior remains unchanged.
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.schemas.common import LocationPrecision, ProcessingStatus
from backend.app.schemas.ml import MLPredictionOutput
from backend.app.services.ml_adapter import (
    MLAdapter,
    is_lightweight_mode,
    reset_discovered_engine,
)
from ml.classification.incident_classifier import IncidentClassifier
from ml.config import MLConfig, get_ml_config, reset_ml_config
from ml.embeddings.embedder import SentenceTransformerEmbedder
from ml.exceptions import MLModelError
from ml.pipeline.inference_engine import InferenceEngine, get_inference_engine, reset_inference_engine
from ml.pipeline.schema_validator import get_schema_validator


@pytest.fixture(autouse=True)
def clean_runtime_state():
    """Ensures clean configuration and adapter state for each test."""
    reset_ml_config()
    reset_discovered_engine()
    reset_inference_engine()
    yield
    reset_ml_config()
    reset_discovered_engine()
    reset_inference_engine()


class TestLightweightModeEnvironmentParsing:
    """Verifies boolean parsing for ML_LIGHTWEIGHT_MODE."""

    @pytest.mark.parametrize("val", ["1", "true", "True", "TRUE", "yes", "YES", "on", "ON"])
    def test_truthy_values(self, monkeypatch, val):
        monkeypatch.setenv("ML_LIGHTWEIGHT_MODE", val)
        assert is_lightweight_mode() is True

        reset_ml_config()
        cfg = MLConfig.from_env()
        assert cfg.lightweight_mode is True

    @pytest.mark.parametrize("val", ["0", "false", "False", "no", "off", "", "random"])
    def test_falsy_values(self, monkeypatch, val):
        monkeypatch.setenv("ML_LIGHTWEIGHT_MODE", val)
        assert is_lightweight_mode() is False

        reset_ml_config()
        cfg = MLConfig.from_env()
        assert cfg.lightweight_mode is False

    def test_unset_defaults_to_false(self, monkeypatch):
        monkeypatch.delenv("ML_LIGHTWEIGHT_MODE", raising=False)
        assert is_lightweight_mode() is False

        reset_ml_config()
        cfg = MLConfig.from_env()
        assert cfg.lightweight_mode is False


class TestRequirementAAndBBackendAdapterToggle:
    """
    Requirement A: ML_LIGHTWEIGHT_MODE=false/unset preserves current behavior (include_embedding=True).
    Requirement B: ML_LIGHTWEIGHT_MODE=true causes backend adapter to request include_embedding=False.
    """

    def test_req_a_unset_or_false_requests_include_embedding_true(self, monkeypatch):
        monkeypatch.delenv("ML_LIGHTWEIGHT_MODE", raising=False)
        mock_engine = MagicMock()
        mock_engine.analyze.return_value = {
            "report_id": "rep-test-01",
            "model_version": "test-v1",
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.9},
            "urgency": {"label": "HIGH", "confidence": 0.8},
            "location": {
                "text": "Patia",
                "latitude": None,
                "longitude": None,
                "precision": "unknown",
                "confidence": 0.7,
            },
            "people_at_risk": {"count": None, "confidence": None},
            "required_response": [],
            "entities": [],
            "embedding_reference": "emb-rep-test-01",
            "processing_status": "SUCCESS",
            "warnings": [],
        }

        wrapped = MLAdapter._wrap_discovered_engine(mock_engine)
        wrapped("Heavy rain near Patia", "rep-test-01", None)

        mock_engine.analyze.assert_called_once_with(
            report="Heavy rain near Patia",
            report_id="rep-test-01",
            location_hint=None,
            include_embedding=True,
        )

    def test_req_b_lightweight_true_requests_include_embedding_false(self, monkeypatch):
        monkeypatch.setenv("ML_LIGHTWEIGHT_MODE", "true")
        mock_engine = MagicMock()
        mock_engine.analyze.return_value = {
            "report_id": "rep-test-02",
            "model_version": "test-v1",
            "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.9},
            "urgency": {"label": "HIGH", "confidence": 0.8},
            "location": {
                "text": "Patia",
                "latitude": None,
                "longitude": None,
                "precision": "unknown",
                "confidence": 0.7,
            },
            "people_at_risk": {"count": None, "confidence": None},
            "required_response": [],
            "entities": [],
            "embedding_reference": None,
            "processing_status": "SUCCESS",
            "warnings": [],
        }

        wrapped = MLAdapter._wrap_discovered_engine(mock_engine)
        wrapped("Heavy rain near Patia", "rep-test-02", None)

        mock_engine.analyze.assert_called_once_with(
            report="Heavy rain near Patia",
            report_id="rep-test-02",
            location_hint=None,
            include_embedding=False,
        )


class TestRequirementCKeywordClassification:
    """Requirement C: Lightweight classification uses the existing keyword path."""

    def test_classifier_defaults_to_keyword_mode_in_lightweight(self, monkeypatch):
        monkeypatch.setenv("ML_LIGHTWEIGHT_MODE", "true")
        reset_ml_config()
        cfg = get_ml_config()
        classifier = IncidentClassifier(config=cfg)

        assert classifier.mode == "keyword"

        res = classifier.predict("Flash flood water entering ground floor homes")
        assert res.method == "keyword"
        assert res.label == "FLOOD_FLASH_FLOOD"
        assert "raw_cosine_similarities" not in res.evidence
        assert "semantic_scores" not in res.evidence
        assert "keyword_scores" in res.evidence

    def test_classifier_defaults_to_hybrid_in_normal_mode(self, monkeypatch):
        monkeypatch.delenv("ML_LIGHTWEIGHT_MODE", raising=False)
        reset_ml_config()
        cfg = get_ml_config()
        classifier = IncidentClassifier(config=cfg)

        assert classifier.mode == "hybrid"


class TestRequirementDAndESchemaValidationAndNoEmbedding:
    """
    Requirement D: Lightweight output validates against the canonical ML schema.
    Requirement E: Lightweight output contains no embedding.
    """

    def test_lightweight_output_validates_and_omits_embedding(self, monkeypatch):
        monkeypatch.setenv("ML_LIGHTWEIGHT_MODE", "true")
        reset_ml_config()
        reset_inference_engine()

        cfg = MLConfig(lightweight_mode=True)
        engine = InferenceEngine(config=cfg)
        validator = get_schema_validator()

        raw_output = engine.analyze(
            "Flash flood and rising water trapped people on rooftop near Rasulgarh",
            report_id="rep-lw-01",
            include_embedding=False,
        )

        # Requirement D: Schema validation passes
        validator.validate(raw_output)

        # Requirement E: Omission of embedding key
        assert "embedding" not in raw_output
        assert raw_output["embedding_reference"] is None
        assert raw_output["incident_type"]["label"] == "FLOOD_FLASH_FLOOD"
        assert raw_output["processing_status"] in ("SUCCESS", "PARTIAL", "NEEDS_REVIEW")

        # Backend Pydantic validation passes
        pred_output = MLPredictionOutput.model_validate(raw_output)
        assert pred_output.embedding is None
        assert pred_output.report_id == "rep-lw-01"


class TestRequirementFNoHeavyNeuralImports:
    """
    Requirement F: A lightweight analysis does not import/load torch,
    sentence_transformers, or transformers.
    """

    def test_neural_modules_blocked_in_process_lightweight_mode(self, monkeypatch):
        """Even if sentence_transformers is blocked from import, lightweight analysis succeeds."""
        monkeypatch.setenv("ML_LIGHTWEIGHT_MODE", "true")
        reset_ml_config()
        reset_inference_engine()

        # Simulate missing/blocked heavy libraries
        with patch.dict(
            sys.modules,
            {
                "sentence_transformers": None,
                "transformers": None,
                "torch": None,
            },
        ):
            engine = InferenceEngine(config=MLConfig(lightweight_mode=True))
            res = engine.analyze(
                "Major wildfire spreading through forest near settlement",
                report_id="rep-fire-01",
                include_embedding=False,
            )
            assert res["incident_type"]["label"] == "FIRE_WILDFIRE_EXPLOSION"
            assert "embedding" not in res

    def test_embedder_raises_without_loading_model_in_lightweight(self):
        """Attempting to access neural model in lightweight mode raises MLModelError without importing."""
        cfg = MLConfig(lightweight_mode=True)
        embedder = SentenceTransformerEmbedder(config=cfg)
        with pytest.raises(MLModelError, match="disabled in lightweight mode"):
            embedder._get_model()

    def test_clean_subprocess_zero_heavy_imports(self):
        """In a pristine Python subprocess, lightweight analysis never loads torch or sentence_transformers."""
        script = """
import os
import sys

os.environ["ML_LIGHTWEIGHT_MODE"] = "true"

from ml.pipeline import get_inference_engine
from backend.app.services.ml_adapter import get_ml_adapter

# 1. Run ML pipeline analysis directly
engine = get_inference_engine()
out = engine.analyze("Heavy flash flooding in Cuttack road", report_id="rep-sub-01", include_embedding=False)
assert "embedding" not in out
assert out["incident_type"]["label"] == "FLOOD_FLASH_FLOOD"

# 2. Run through backend adapter
adapter = get_ml_adapter()
pred = adapter.analyze_report("Heavy flash flooding in Cuttack road", report_id="rep-sub-02")
assert pred.embedding is None
assert pred.incident_type.label is not None

# 3. Verify zero heavy neural packages in sys.modules
imported = set(sys.modules.keys())
assert "torch" not in imported, f"torch was unexpectedly imported: {'torch' in imported}"
assert "sentence_transformers" not in imported, f"sentence_transformers was unexpectedly imported"
assert "transformers" not in imported, f"transformers was unexpectedly imported"
print("CLEAN_SUBPROCESS_SUCCESS")
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert proc.returncode == 0, f"Subprocess failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        assert "CLEAN_SUBPROCESS_SUCCESS" in proc.stdout


class TestRequirementGCallerCoordinatesPreserved:
    """Requirement G: Existing caller-supplied coordinates remain preserved."""

    def test_caller_coordinates_preserved_in_lightweight(self, monkeypatch):
        monkeypatch.setenv("ML_LIGHTWEIGHT_MODE", "true")
        reset_ml_config()
        reset_discovered_engine()
        reset_inference_engine()

        adapter = MLAdapter()
        pred = adapter.analyze_report(
            text="Flash flood water level reaching waist depth",
            report_id="rep-coord-test",
            location_hint={
                "latitude": 20.2961,
                "longitude": 85.8245,
                "precision": "exact",
                "raw_text": "Saheed Nagar",
            },
        )

        assert pred.location.latitude == 20.2961
        assert pred.location.longitude == 85.8245
        assert pred.location.precision == LocationPrecision.EXACT
        assert pred.location.text == "Saheed Nagar"
        assert pred.embedding is None


class TestRequirementHFallbackAndPrivacyBehavior:
    """Requirement H: Existing fallback/privacy behavior remains unchanged."""

    def test_fallback_prediction_generated_on_failure(self, monkeypatch):
        monkeypatch.setenv("ML_LIGHTWEIGHT_MODE", "true")
        reset_ml_config()

        def failing_analyzer(text, rep_id, hint):
            raise RuntimeError("Simulated internal failure")

        adapter = MLAdapter(analyzer=failing_analyzer)
        pred = adapter.analyze_report(
            text="Distress call about power outage and fallen transformer",
            report_id="rep-fail-01",
            location_hint={"raw_text": "Old Town", "precision": "approximate"},
        )

        assert pred.processing_status == ProcessingStatus.FAILED
        assert "ML_ANALYSIS_FAILED" in pred.warnings
        assert pred.location.text == "Old Town"
        assert pred.embedding is None
        # Does not leak raw exception message in model output
        assert "Simulated internal failure" not in str(pred.warnings)
