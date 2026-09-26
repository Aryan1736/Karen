"""
Karen's Ear — Machine Learning Pipeline Adapter
Boundary service decoupling backend ingestion from ML pipeline implementation.
Adheres strictly to docs/api-contract.md Section 4 and architecture/failure-handling.md.
"""
from __future__ import annotations

import importlib
import logging
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


class MLAdapter:
    """
    Decoupled adapter interface consuming Aryan's ML analyzer callable.
    Supports dependency-injected analyzers for testing and lazy dynamic discovery for production.
    """

    def __init__(self, analyzer: Optional[AnalyzerCallable] = None) -> None:
        self._analyzer: Optional[AnalyzerCallable] = analyzer
        self._discovery_attempted: bool = False

    def _discover_analyzer(self) -> Optional[AnalyzerCallable]:
        """
        Lazily discovers Aryan's unified analyze_report() function if available.
        Does NOT load heavy ML dependencies at module import time.
        """
        if self._discovery_attempted:
            return self._analyzer

        self._discovery_attempted = True
        candidate_paths = [
            ("ml.pipeline", "analyze_report"),
            ("ml.pipeline.orchestrator", "analyze_report"),
            ("ml", "analyze_report"),
        ]

        for mod_name, func_name in candidate_paths:
            try:
                mod = importlib.import_module(mod_name)
                func = getattr(mod, func_name, None)
                if callable(func):
                    logger.info("Discovered ML analyzer callable at %s.%s", mod_name, func_name)
                    self._analyzer = func
                    return self._analyzer
            except Exception as exc:
                # Log sanitized exception type only; never leak report text
                logger.debug("Discovery probe at %s failed: %s", mod_name, type(exc).__name__)

        logger.info("No unified ML analyzer callable discovered; adapter will operate in fallback mode")
        return None

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

    def analyze_report(
        self,
        text: str,
        report_id: str,
        location_hint: Optional[Union[dict[str, Any], LocationHint]] = None,
    ) -> MLPredictionOutput:
        """
        Analyzes an emergency dispatch using the configured or discovered ML callable.
        Guarantees that no exception halts execution, returning canonical fallback on failure.
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

        if isinstance(raw_output, MLPredictionOutput):
            return raw_output

        if not isinstance(raw_output, dict):
            logger.warning("ML analyzer returned non-dict output for report %s: %s", report_id, type(raw_output).__name__)
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
