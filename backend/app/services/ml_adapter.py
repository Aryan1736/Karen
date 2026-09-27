"""
Karen's Ear — Machine Learning Pipeline Adapter
Boundary service decoupling backend ingestion from ML pipeline implementation.
Adheres strictly to docs/api-contract.md Section 4 and architecture/failure-handling.md.
"""
from __future__ import annotations

import importlib
import logging
import os
import threading
from typing import Any, Callable, Optional, Union

from pydantic import ValidationError

from backend.app.schemas.common import LocationPrecision, ProcessingStatus
from backend.app.schemas.ml import (
    LocationPrediction,
    MLPredictionOutput,
    RiskPrediction,
    TypePrediction,
    UrgencyPrediction,
)
from backend.app.schemas.report import LocationHint

logger = logging.getLogger("karen.backend.ml_adapter")

# Type alias for analyzer callables:
# analyze_report(text: str, report_id: str, location_hint: dict | None = None) -> dict
AnalyzerCallable = Callable[[str, str, Optional[dict[str, Any]]], Union[dict[str, Any], MLPredictionOutput]]

DEFAULT_FALLBACK_MODEL_VERSION = "karen-fallback-v1"


def is_lightweight_mode() -> bool:
    """
    Returns True if ML_LIGHTWEIGHT_MODE is enabled via environment variable or settings.
    Accepts standard truthy values: 1, true, yes, on.
    Defaults to False.
    """
    val = os.getenv("ML_LIGHTWEIGHT_MODE")
    if val is not None and val.strip():
        return val.strip().lower() in ("1", "true", "yes", "on")
    try:
        from backend.app.core.config import settings
        return bool(getattr(settings, "ML_LIGHTWEIGHT_MODE", False))
    except Exception:
        return False


# Shared process-level lock protecting concurrent execution of the discovered ML InferenceEngine
_discovered_engine_lock = threading.Lock()
_discovered_engine: Any = None


def reset_discovered_engine() -> None:
    """Resets the cached discovered engine and default adapter (used in test suites)."""
    global _discovered_engine, _default_adapter
    _discovered_engine = None
    _default_adapter = None


class MLAdapter:
    """
    Decoupled adapter interface consuming Aryan's ML analyzer callable or InferenceEngine.
    Supports dependency-injected analyzers for testing and lazy dynamic discovery for production.
    """

    is_lightweight_mode = staticmethod(is_lightweight_mode)

    def __init__(self, analyzer: Optional[AnalyzerCallable] = None) -> None:
        self._analyzer: Optional[AnalyzerCallable] = analyzer
        self._discovery_attempted: bool = False

    @staticmethod
    def _wrap_discovered_engine(engine: Any) -> AnalyzerCallable:
        """
        Wraps discovered InferenceEngine with the process-level lock
        and adapts to the backend (text, report_id, location_hint) -> dict contract.
        Requests include_embedding=False in lightweight mode, or True in normal mode.
        """
        def _call_engine(
            text: str,
            report_id: str,
            location_hint: Optional[dict[str, Any]] = None,
        ) -> dict[str, Any]:
            with _discovered_engine_lock:
                req_embedding = not is_lightweight_mode()
                return engine.analyze(
                    report=text,
                    report_id=report_id,
                    location_hint=location_hint,
                    include_embedding=req_embedding,
                )
        return _call_engine

    def _discover_analyzer(self) -> Optional[AnalyzerCallable]:
        """
        Lazily discovers Aryan's unified InferenceEngine if available.
        Does NOT load heavy ML dependencies at module import time.
        Protects execution with the process-level _discovered_engine_lock.
        """
        if self._discovery_attempted:
            return self._analyzer

        self._discovery_attempted = True
        global _discovered_engine

        if _discovered_engine is not None:
            self._analyzer = self._wrap_discovered_engine(_discovered_engine)
            return self._analyzer

        try:
            mod = importlib.import_module("ml.pipeline")
            get_engine = getattr(mod, "get_inference_engine", None)
            if callable(get_engine):
                engine = get_engine()
                if engine is not None and hasattr(engine, "analyze"):
                    logger.info("Discovered ML InferenceEngine via ml.pipeline.get_inference_engine")
                    _discovered_engine = engine
                    self._analyzer = self._wrap_discovered_engine(engine)
                    return self._analyzer

            # Secondary discovery paths: InferenceEngine class or inference_engine singleton
            engine_cls = getattr(mod, "InferenceEngine", None)
            if engine_cls is not None and callable(engine_cls):
                engine = engine_cls()
                logger.info("Discovered ML InferenceEngine via ml.pipeline.InferenceEngine")
                _discovered_engine = engine
                self._analyzer = self._wrap_discovered_engine(engine)
                return self._analyzer

            engine_inst = getattr(mod, "inference_engine", None)
            if engine_inst is not None and hasattr(engine_inst, "analyze"):
                logger.info("Discovered ML InferenceEngine via ml.pipeline.inference_engine")
                _discovered_engine = engine_inst
                self._analyzer = self._wrap_discovered_engine(engine_inst)
                return self._analyzer

            # Legacy fallback: check for analyze_report if exposed
            func = getattr(mod, "analyze_report", None)
            if callable(func):
                logger.info("Discovered legacy analyze_report at ml.pipeline")
                self._analyzer = func
                return self._analyzer
        except Exception as exc:
            # Log sanitized exception type only; never leak report text
            logger.debug("Discovery probe for ml.pipeline failed: %s", type(exc).__name__)

        logger.info("No unified ML analyzer callable discovered; adapter will operate in fallback mode")
        return None

    @staticmethod
    def _overlay_caller_location_evidence(
        raw_output: dict[str, Any],
        location_hint: Optional[Union[dict[str, Any], LocationHint]],
    ) -> dict[str, Any]:
        """
        Overlays trusted caller-provided location evidence onto ML output without inventing data:
        - If location_hint contains both non-null latitude and longitude:
            - overlays latitude and longitude
            - overlays caller precision when supplied
            - uses caller raw_text as location text if available to preserve coherence with coordinates
            - otherwise preserves ML-extracted location text
            - preserves ML confidence (never invents confidence for caller coordinates)
        - If location_hint does NOT contain a complete coordinate pair:
            - never overlays partial coordinates
            - retains ML location result
            - fills missing ML text with caller raw_text if ML text is null
            - uses caller precision only where it accurately describes caller-provided evidence
        - Never geocodes or fabricates latitude/longitude.
        """
        if location_hint is None:
            return raw_output

        caller_raw_text: Optional[str] = None
        caller_lat: Optional[float] = None
        caller_lon: Optional[float] = None
        caller_prec: Optional[Union[str, LocationPrecision]] = None

        if isinstance(location_hint, dict):
            caller_raw_text = location_hint.get("raw_text")
            caller_lat = location_hint.get("latitude")
            caller_lon = location_hint.get("longitude")
            caller_prec = location_hint.get("precision")
        elif isinstance(location_hint, LocationHint):
            caller_raw_text = location_hint.raw_text
            caller_lat = location_hint.latitude
            caller_lon = location_hint.longitude
            caller_prec = location_hint.precision

        normalized_caller_prec: Optional[str] = None
        if isinstance(caller_prec, LocationPrecision):
            normalized_caller_prec = caller_prec.value
        elif isinstance(caller_prec, str) and caller_prec.lower() in ("exact", "approximate", "unknown"):
            normalized_caller_prec = caller_prec.lower()

        loc = raw_output.get("location")
        if not isinstance(loc, dict):
            loc = {
                "text": None,
                "latitude": None,
                "longitude": None,
                "precision": "unknown",
                "confidence": None,
            }
            raw_output["location"] = loc

        has_complete_coords = caller_lat is not None and caller_lon is not None

        if has_complete_coords:
            loc["latitude"] = caller_lat
            loc["longitude"] = caller_lon
            if normalized_caller_prec is not None:
                loc["precision"] = normalized_caller_prec
            if caller_raw_text is not None and str(caller_raw_text).strip():
                loc["text"] = str(caller_raw_text).strip()
        else:
            # Partial or missing coordinates: do NOT overlay coordinates
            ml_text = loc.get("text")
            if (ml_text is None or not str(ml_text).strip()) and (caller_raw_text is not None and str(caller_raw_text).strip()):
                loc["text"] = str(caller_raw_text).strip()
                if normalized_caller_prec is not None and loc.get("precision") in (None, "unknown", LocationPrecision.UNKNOWN):
                    loc["precision"] = normalized_caller_prec

        return raw_output

    @staticmethod
    def make_fallback_prediction(
        report_id: str,
        location_hint: Optional[Union[dict[str, Any], LocationHint]] = None,
        warning_code: str = "ML_ANALYSIS_FAILED",
    ) -> MLPredictionOutput:
        """
        Constructs a canonical, non-hallucinatory fallback ML prediction.
        Preserves caller-provided location evidence without inventing coordinates.
        Never leaks raw exception text or citizen report contents.
        """
        raw_text: Optional[str] = None
        lat: Optional[float] = None
        lon: Optional[float] = None
        prec = LocationPrecision.UNKNOWN

        if location_hint is not None:
            if isinstance(location_hint, dict):
                raw_text = location_hint.get("raw_text")
                lat = location_hint.get("latitude")
                lon = location_hint.get("longitude")
                raw_prec = location_hint.get("precision", LocationPrecision.UNKNOWN)
                if isinstance(raw_prec, LocationPrecision):
                    prec = raw_prec
                elif isinstance(raw_prec, str) and raw_prec.lower() in ("exact", "approximate", "unknown"):
                    prec = LocationPrecision(raw_prec.lower())
            elif isinstance(location_hint, LocationHint):
                raw_text = location_hint.raw_text
                lat = location_hint.latitude
                lon = location_hint.longitude
                prec = location_hint.precision

        return MLPredictionOutput(
            report_id=report_id,
            model_version=DEFAULT_FALLBACK_MODEL_VERSION,
            incident_type=TypePrediction(label=None, confidence=None),
            urgency=UrgencyPrediction(label=None, confidence=None),
            location=LocationPrediction(
                text=raw_text,
                latitude=lat,
                longitude=lon,
                precision=prec,
                confidence=None,
            ),
            people_at_risk=RiskPrediction(count=None, confidence=None),
            required_response=[],
            entities=[],
            embedding_reference=None,
            overall_confidence=None,
            processing_status=ProcessingStatus.FAILED,
            warnings=[warning_code],
        )

    @staticmethod
    def _overlay_location_on_model(
        pred: MLPredictionOutput,
        location_hint: Optional[Union[dict[str, Any], LocationHint]],
    ) -> MLPredictionOutput:
        """
        Overlays trusted caller-provided location evidence directly onto an MLPredictionOutput.
        """
        if location_hint is None:
            return pred

        caller_raw_text: Optional[str] = None
        caller_lat: Optional[float] = None
        caller_lon: Optional[float] = None
        caller_prec: Optional[Union[str, LocationPrecision]] = None

        if isinstance(location_hint, dict):
            caller_raw_text = location_hint.get("raw_text")
            caller_lat = location_hint.get("latitude")
            caller_lon = location_hint.get("longitude")
            caller_prec = location_hint.get("precision")
        elif isinstance(location_hint, LocationHint):
            caller_raw_text = location_hint.raw_text
            caller_lat = location_hint.latitude
            caller_lon = location_hint.longitude
            caller_prec = location_hint.precision

        normalized_caller_prec: Optional[LocationPrecision] = None
        if isinstance(caller_prec, LocationPrecision):
            normalized_caller_prec = caller_prec
        elif isinstance(caller_prec, str) and caller_prec.lower() in ("exact", "approximate", "unknown"):
            normalized_caller_prec = LocationPrecision(caller_prec.lower())

        has_complete_coords = caller_lat is not None and caller_lon is not None

        if has_complete_coords:
            pred.location.latitude = caller_lat
            pred.location.longitude = caller_lon
            if normalized_caller_prec is not None:
                pred.location.precision = normalized_caller_prec
            if caller_raw_text is not None and str(caller_raw_text).strip():
                pred.location.text = str(caller_raw_text).strip()
        else:
            ml_text = pred.location.text
            if (ml_text is None or not str(ml_text).strip()) and (caller_raw_text is not None and str(caller_raw_text).strip()):
                pred.location.text = str(caller_raw_text).strip()
                if normalized_caller_prec is not None and pred.location.precision == LocationPrecision.UNKNOWN:
                    pred.location.precision = normalized_caller_prec

        return pred

    def analyze_report(
        self,
        text: str,
        report_id: str,
        location_hint: Optional[Union[dict[str, Any], LocationHint]] = None,
    ) -> MLPredictionOutput:
        """
        Analyzes an emergency dispatch using the configured or discovered ML callable.
        Guarantees that no exception halts execution, returning canonical fallback on failure.
        Preserves caller-provided location evidence without inventing coordinates.
        """
        analyzer = self._analyzer or self._discover_analyzer()
        if analyzer is None:
            logger.warning("ML analyzer unavailable for report %s", report_id)
            return self.make_fallback_prediction(
                report_id=report_id,
                location_hint=location_hint,
                warning_code="ML_ANALYZER_UNAVAILABLE",
            )

        # Normalize location_hint to dict for analyzer contract
        hint_dict: Optional[dict[str, Any]] = None
        if location_hint is not None:
            if isinstance(location_hint, dict):
                hint_dict = location_hint
            elif hasattr(location_hint, "model_dump"):
                hint_dict = location_hint.model_dump(mode="json")

        try:
            raw_output = analyzer(text, report_id, hint_dict)
        except Exception as exc:
            # Sanitize logging: record only exception type, never report text
            logger.warning(
                "ML analyzer invocation raised exception for report %s: %s",
                report_id,
                type(exc).__name__,
            )
            return self.make_fallback_prediction(
                report_id=report_id,
                location_hint=location_hint,
                warning_code="ML_ANALYSIS_FAILED",
            )

        # If already an MLPredictionOutput, apply overlay directly and return
        if isinstance(raw_output, MLPredictionOutput):
            try:
                return self._overlay_location_on_model(raw_output, location_hint)
            except Exception as overlay_exc:
                logger.warning(
                    "Location overlay raised exception on model for report %s: %s",
                    report_id,
                    type(overlay_exc).__name__,
                )
                return self.make_fallback_prediction(
                    report_id=report_id,
                    location_hint=location_hint,
                    warning_code="ML_OUTPUT_INVALID",
                )

        if not isinstance(raw_output, dict):
            logger.warning("ML analyzer returned non-dict output for report %s: %s", report_id, type(raw_output).__name__)
            return self.make_fallback_prediction(
                report_id=report_id,
                location_hint=location_hint,
                warning_code="ML_OUTPUT_INVALID",
            )

        # Overlay trusted caller location evidence onto ML output
        try:
            raw_output = self._overlay_caller_location_evidence(raw_output, location_hint)
        except Exception as overlay_exc:
            logger.warning(
                "Location overlay raised exception for report %s: %s",
                report_id,
                type(overlay_exc).__name__,
            )
            return self.make_fallback_prediction(
                report_id=report_id,
                location_hint=location_hint,
                warning_code="ML_OUTPUT_INVALID",
            )

        try:
            # Validate raw dictionary against canonical schema
            return MLPredictionOutput.model_validate(raw_output)
        except ValidationError:
            logger.warning("ML analyzer output failed schema validation for report %s", report_id)
            return self.make_fallback_prediction(
                report_id=report_id,
                location_hint=location_hint,
                warning_code="ML_OUTPUT_INVALID",
            )


# Global singleton instance for production use
_default_adapter: Optional[MLAdapter] = None


def get_ml_adapter() -> MLAdapter:
    """Returns the default MLAdapter instance (lazily initialized)."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = MLAdapter()
    return _default_adapter

