"""
Karen's Ear — Unified ML Inference Pipeline Orchestrator.

Feature 10 — Step 5 of the ML pipeline (architecture/ml-pipeline.md).
Provides ONE canonical public inference entry point orchestrating all ML components:
  Raw Report
      ↓
  Preprocessor (Feature 2)
      ↓
  Incident Classifier (Feature 3)
      ↓
  Entity Extractor (Features 4 & 5)
      ├── Location (Feature 5)
      ├── People at Risk (Feature 4)
      └── Other Entities (Feature 5)
      ↓
  Response Mapper (Feature 6)
      ↓
  Urgency Engine (Feature 7)
      ↓
  Embedding Engine (Feature 8)
      ↓
  Confidence Engine (Feature 9)
      ↓
  Schema Validator (Feature 10)
      ↓
  Canonical ML Output (FROZEN CONTRACT)

Public Entry Point:
    result = inference_engine.analyze(report)
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Sequence

from ml.classification.incident_classifier import (
    ClassificationResult,
    IncidentClassifier,
)
from ml.confidence.confidence_engine import (
    ConfidenceEngine,
    ConfidenceResult,
)
from ml.config import (
    CANONICAL_INCIDENT_TYPES,
    CANONICAL_PRECISION_LEVELS,
    CANONICAL_PROCESSING_STATUSES,
    CANONICAL_RESPONSE_TYPES,
    CANONICAL_URGENCY_LEVELS,
    ComponentResult,
    MLConfig,
    ProcessingContext,
    get_ml_config,
)
from ml.embeddings.embedder import (
    EmbeddingEngine,
    SentenceTransformerEmbedder,
)
from ml.exceptions import (
    MLBaseError,
    MLInferenceError,
    MLInputError,
    MLSchemaValidationError,
)
from ml.extraction.location_entity_extractor import (
    LocationEntityExtractor,
    LocationEntityResult,
)
from ml.extraction.people_risk_extractor import (
    PeopleRiskExtractor,
    PeopleRiskResult,
)
from ml.logging_utils import get_ml_logger
from ml.pipeline.schema_validator import (
    SchemaValidator,
    get_schema_validator,
)
from ml.preprocessing.text_cleaner import (
    PreprocessedText,
    TextCleaner,
)
from ml.response.response_extractor import (
    RequiredResponseExtractor,
    ResponseExtractionResult,
)
from ml.urgency.urgency_engine import (
    UrgencyEngine,
    UrgencyResult,
)


def _generate_deterministic_report_id(text: str) -> str:
    """Generates a deterministic report ID from report text when none is provided."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"rep-{digest}"


def _dedup_warnings(warnings: Sequence[str]) -> list[str]:
    """Deduplicates warning strings while strictly preserving insertion order."""
    seen: set[str] = set()
    result: list[str] = []
    for w in warnings:
        w_clean = str(w).strip()
        if w_clean and w_clean not in seen:
            seen.add(w_clean)
            result.append(w_clean)
    return result


class InferenceEngine:
    """
    Unified public inference engine for Karen's Ear ML pipeline.

    Orchestrates all ML components in fixed sequential order with failure isolation,
    strict schema validation, and complete observability.
    """

    def __init__(
        self,
        config: MLConfig | None = None,
        text_cleaner: TextCleaner | None = None,
        classifier: IncidentClassifier | None = None,
        location_extractor: LocationEntityExtractor | None = None,
        people_extractor: PeopleRiskExtractor | None = None,
        response_extractor: RequiredResponseExtractor | None = None,
        urgency_engine: UrgencyEngine | None = None,
        embedder: SentenceTransformerEmbedder | None = None,
        confidence_engine: ConfidenceEngine | None = None,
        validator: SchemaValidator | None = None,
    ) -> None:
        self.config = config or get_ml_config()
        self.logger = get_ml_logger(
            name="karen.ml.pipeline",
            component="pipeline",
            model_version=self.config.model_version,
        )

        # Component instances (support dependency injection for testing and failure injection)
        self.text_cleaner = text_cleaner or TextCleaner(config=self.config)
        self.classifier = classifier or IncidentClassifier(config=self.config)
        self.location_extractor = location_extractor or LocationEntityExtractor(config=self.config)
        self.people_extractor = people_extractor or PeopleRiskExtractor(config=self.config)
        self.response_extractor = response_extractor or RequiredResponseExtractor(config=self.config)
        self.urgency_engine = urgency_engine or UrgencyEngine(config=self.config)
        self.embedder = embedder or SentenceTransformerEmbedder(config=self.config)
        self.confidence_engine = confidence_engine or ConfidenceEngine(config=self.config)
        self.validator = validator or get_schema_validator()

        # Observability metadata from the most recent analysis run
        self.last_execution_metadata: dict[str, Any] = {}

    def analyze(
        self,
        report: str | dict[str, Any] | ProcessingContext,
        report_id: str | None = None,
        location_hint: dict[str, Any] | None = None,
        include_embedding: bool = False,
    ) -> dict[str, Any]:
        """
        Single public orchestration entry point for Karen's Ear ML analysis.

        Fixed Execution Order:
          1. Input validation & Preprocessing (Fail-fast)
          2. Incident classification (Fail-soft)
          3. Entity extraction: Location, People at Risk, Other Entities (Fail-soft)
          4. Required response extraction (Fail-soft)
          5. Operational urgency (Fail-soft)
          6. Dense semantic embedding (Fail-soft)
          7. Confidence aggregation & operational status resolution (Fail-soft)
          8. Canonical output packaging
          9. Final JSON schema validation (Fail-fast)

        Args:
            report: Raw report string, dictionary, or ProcessingContext.
            report_id: Optional tracking identifier overriding or providing ID.
            location_hint: Optional location hint metadata from caller.
            include_embedding: If True, includes raw 384-d vector in payload.
                               Default False conforms to minimal canonical shape.

        Returns:
            Dictionary strictly adhering to ml/schemas/incident_output.json.

        Raises:
            MLInputError: If report input is invalid, empty, or unparseable.
            MLSchemaValidationError: If final canonical output violates frozen contract.
        """
        t_pipeline_start = time.perf_counter()
        stage_latencies: dict[str, float] = {}
        all_warnings: list[str] = []

        # ======================================================================
        # Step 0: Input Parsing & Validation (FAIL-FAST)
        # ======================================================================
        raw_text, effective_report_id, _ = self._parse_input(
            report=report,
            report_id=report_id,
            location_hint=location_hint,
        )

        # ======================================================================
        # Step 1: Preprocessing & Text Normalization (FAIL-FAST)
        # ======================================================================
        clean_res, stage_latencies["preprocessing_ms"] = self._run_preprocessing(
            raw_text=raw_text,
            effective_report_id=effective_report_id,
            all_warnings=all_warnings,
        )

        # ======================================================================
        # Step 2: Incident Classification (FAIL-SOFT)
        # ======================================================================
        classifier_res, incident_type_dict, stage_latencies["classification_ms"] = self._run_classification(
            clean_res=clean_res,
            effective_report_id=effective_report_id,
            all_warnings=all_warnings,
        )

        # ======================================================================
        # Step 3: Entity Extraction (FAIL-SOFT)
        # ======================================================================
        (
            loc_res,
            location_dict,
            people_res,
            people_at_risk_dict,
            canonical_entities,
            stage_latencies["extraction_ms"],
        ) = self._run_extraction(
            clean_res=clean_res,
            effective_report_id=effective_report_id,
            all_warnings=all_warnings,
        )

        # ======================================================================
        # Step 4: Required Response Mapping (FAIL-SOFT)
        # ======================================================================
        resp_res, required_response_list, stage_latencies["response_ms"] = self._run_response(
            clean_res=clean_res,
            effective_report_id=effective_report_id,
            all_warnings=all_warnings,
        )

        # ======================================================================
        # Step 5: Operational Urgency Engine (FAIL-SOFT)
        # ======================================================================
        urgency_res, urgency_dict, stage_latencies["urgency_ms"] = self._run_urgency(
            clean_res=clean_res,
            classifier_res=classifier_res,
            people_res=people_res,
            resp_res=resp_res,
            loc_res=loc_res,
            all_warnings=all_warnings,
        )

        # ======================================================================
        # Step 6: Dense Semantic Embedding (FAIL-SOFT)
        # ======================================================================
        embedding_vec, embedding_reference, stage_latencies["embedding_ms"] = self._run_embedding(
            clean_res=clean_res,
            effective_report_id=effective_report_id,
            all_warnings=all_warnings,
        )

        # ======================================================================
        # Step 7: Confidence Calibration & Operational Status (FAIL-SOFT)
        # ======================================================================
        processing_status, stage_latencies["confidence_ms"] = self._run_confidence(
            classifier_res=classifier_res,
            urgency_res=urgency_res,
            loc_res=loc_res,
            people_res=people_res,
            resp_res=resp_res,
            embedding_vec=embedding_vec,
            all_warnings=all_warnings,
        )

        # ======================================================================
        # Step 8: Final Payload Assembly
        # ======================================================================
        deduped_warnings = _dedup_warnings(all_warnings)

        payload: dict[str, Any] = {
            "report_id": effective_report_id,
            "model_version": self.config.model_version,
            "incident_type": incident_type_dict,
            "urgency": urgency_dict,
            "location": location_dict,
            "people_at_risk": people_at_risk_dict,
            "required_response": required_response_list,
            "entities": canonical_entities,
            "embedding_reference": embedding_reference,
            "processing_status": processing_status,
            "warnings": deduped_warnings,
        }

        # Optional raw dense embedding vector for internal ML-to-backend payload
        if include_embedding and embedding_vec is not None:
            payload["embedding"] = embedding_vec

        # ======================================================================
        # Step 9: Final Schema Validation Gate (FAIL-FAST)
        # ======================================================================
        stage_latencies["validation_ms"] = self._run_validation(payload)

        total_latency_ms = round((time.perf_counter() - t_pipeline_start) * 1000, 2)
        stage_latencies["total_ms"] = total_latency_ms

        # Record observability metadata
        self.last_execution_metadata = {
            "report_id": effective_report_id,
            "processing_status": processing_status,
            "stage_latencies_ms": dict(stage_latencies),
            "total_latency_ms": total_latency_ms,
            "warnings_count": len(deduped_warnings),
        }

        # Safe logging (Never log raw report text or embedding vectors)
        self.logger.info(
            "Unified inference pipeline execution completed",
            extra={
                "report_id": effective_report_id,
                "processing_status": processing_status,
                "model_version": self.config.model_version,
                "total_latency_ms": total_latency_ms,
                "warnings_count": len(deduped_warnings),
            },
        )

        return payload

    def _run_preprocessing(
        self,
        raw_text: str,
        effective_report_id: str,
        all_warnings: list[str],
    ) -> tuple[PreprocessedText, float]:
        t0 = time.perf_counter()
        try:
            clean_res: PreprocessedText = self.text_cleaner.clean(
                text=raw_text,
                report_id=effective_report_id,
            )
            all_warnings.extend(clean_res.warnings)
        except MLInputError:
            raise
        except Exception as exc:
            self.logger.error("Text preprocessing failed fatally", exc_info=True)
            raise MLInferenceError(
                f"Preprocessing failed fatally on input text: {exc}",
                details={"error_type": type(exc).__name__},
            ) from exc
        return clean_res, round((time.perf_counter() - t0) * 1000, 2)

    def _run_classification(
        self,
        clean_res: PreprocessedText,
        effective_report_id: str,
        all_warnings: list[str],
    ) -> tuple[ClassificationResult | None, dict[str, Any], float]:
        t0 = time.perf_counter()
        classifier_res: ClassificationResult | None = None
        incident_type_dict: dict[str, Any] = {"label": None, "confidence": None}
        try:
            if hasattr(self.classifier, "predict"):
                classifier_res = self.classifier.predict(clean_res, report_id=effective_report_id)
            elif hasattr(self.classifier, "classify"):
                classifier_res = self.classifier.classify(clean_res, report_id=effective_report_id)
            else:
                raise AttributeError("Classifier has neither 'predict' nor 'classify' method")
            incident_type_dict = {
                "label": classifier_res.label,
                "confidence": classifier_res.confidence,
            }
            all_warnings.extend(classifier_res.warnings)
        except Exception as exc:
            self.logger.warning(
                "Incident classifier failed during analysis",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            all_warnings.append(f"Component 'classification' failed: {type(exc).__name__}")
        return classifier_res, incident_type_dict, round((time.perf_counter() - t0) * 1000, 2)

    def _run_extraction(
        self,
        clean_res: PreprocessedText,
        effective_report_id: str,
        all_warnings: list[str],
    ) -> tuple[
        LocationEntityResult | None,
        dict[str, Any],
        PeopleRiskResult | None,
        dict[str, Any],
        list[dict[str, Any]],
        float,
    ]:
        t0 = time.perf_counter()
        loc_res: LocationEntityResult | None = None
        location_dict: dict[str, Any] = {
            "text": None,
            "latitude": None,
            "longitude": None,
            "precision": "unknown",
            "confidence": None,
        }
        loc_entities: list[dict[str, Any]] = []

        try:
            loc_res = self.location_extractor.extract(clean_res, report_id=effective_report_id)
            location_dict = loc_res.location.to_canonical_dict()
            loc_entities = [ent.to_canonical_dict() for ent in loc_res.entities]
            all_warnings.extend(loc_res.warnings)
        except Exception as exc:
            self.logger.warning(
                "Location entity extractor failed during analysis",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            all_warnings.append(f"Component 'location' failed: {type(exc).__name__}")

        # Strict No-Hallucination Invariant: Coordinates must remain null unless verified
        location_dict["latitude"] = None
        location_dict["longitude"] = None

        people_res: PeopleRiskResult | None = None
        people_at_risk_dict: dict[str, Any] = {"count": None, "confidence": None}
        people_entities: list[dict[str, Any]] = []

        try:
            people_res = self.people_extractor.extract(clean_res, report_id=effective_report_id)
            people_at_risk_dict = people_res.to_canonical_dict()
            people_entities = people_res.to_entities()
            all_warnings.extend(people_res.warnings)
        except Exception as exc:
            self.logger.warning(
                "People risk extractor failed during analysis",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            all_warnings.append(f"Component 'people_at_risk' failed: {type(exc).__name__}")

        canonical_entities = self._assemble_canonical_entities(
            loc_entities=loc_entities,
            people_entities=people_entities,
        )
        return (
            loc_res,
            location_dict,
            people_res,
            people_at_risk_dict,
            canonical_entities,
            round((time.perf_counter() - t0) * 1000, 2),
        )

    def _run_response(
        self,
        clean_res: PreprocessedText,
        effective_report_id: str,
        all_warnings: list[str],
    ) -> tuple[ResponseExtractionResult | None, list[dict[str, Any]], float]:
        t0 = time.perf_counter()
        resp_res: ResponseExtractionResult | None = None
        required_response_list: list[dict[str, Any]] = []
        try:
            resp_res = self.response_extractor.extract(clean_res, report_id=effective_report_id)
            required_response_list = resp_res.to_canonical_list()
            all_warnings.extend(resp_res.warnings)
        except Exception as exc:
            self.logger.warning(
                "Response extractor failed during analysis",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            all_warnings.append(f"Component 'required_response' failed: {type(exc).__name__}")

        # Canonical deterministic ordering of response needs
        required_response_list.sort(
            key=lambda r: (
                CANONICAL_RESPONSE_TYPES.index(r["type"])
                if r.get("type") in CANONICAL_RESPONSE_TYPES
                else 999
            )
        )
        return resp_res, required_response_list, round((time.perf_counter() - t0) * 1000, 2)

    def _run_urgency(
        self,
        clean_res: PreprocessedText,
        classifier_res: ClassificationResult | None,
        people_res: PeopleRiskResult | None,
        resp_res: ResponseExtractionResult | None,
        loc_res: LocationEntityResult | None,
        all_warnings: list[str],
    ) -> tuple[UrgencyResult | None, dict[str, Any], float]:
        t0 = time.perf_counter()
        urgency_res: UrgencyResult | None = None
        urgency_dict: dict[str, Any] = {"label": None, "confidence": None}
        try:
            urgency_res = self.urgency_engine.score_urgency(
                text=clean_res,
                incident_type=classifier_res,
                people_at_risk=people_res,
                required_response=resp_res,
                location_entities=loc_res,
            )
            urgency_dict = urgency_res.to_canonical_dict()
            all_warnings.extend(urgency_res.warnings)
        except Exception as exc:
            self.logger.warning(
                "Urgency engine failed during analysis",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            all_warnings.append(f"Component 'urgency' failed: {type(exc).__name__}")
        return urgency_res, urgency_dict, round((time.perf_counter() - t0) * 1000, 2)

    def _run_embedding(
        self,
        clean_res: PreprocessedText,
        effective_report_id: str,
        all_warnings: list[str],
    ) -> tuple[list[float] | None, str | None, float]:
        t0 = time.perf_counter()
        embedding_vec: list[float] | None = None
        embedding_reference: str | None = None
        try:
            embedding_vec = self.embedder.encode_single(
                text=clean_res,
                report_id=effective_report_id,
            )
            embedding_reference = f"emb-{effective_report_id}"
        except Exception as exc:
            self.logger.warning(
                "Embedding generator failed during analysis",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            embedding_vec = None
            embedding_reference = None
            all_warnings.append(f"Component 'embeddings' failed: {type(exc).__name__}")
        return embedding_vec, embedding_reference, round((time.perf_counter() - t0) * 1000, 2)

    def _run_confidence(
        self,
        classifier_res: ClassificationResult | None,
        urgency_res: UrgencyResult | None,
        loc_res: LocationEntityResult | None,
        people_res: PeopleRiskResult | None,
        resp_res: ResponseExtractionResult | None,
        embedding_vec: list[float] | None,
        all_warnings: list[str],
    ) -> tuple[str, float]:
        t0 = time.perf_counter()
        processing_status = "SUCCESS"
        try:
            conf_input_classifier = (
                classifier_res
                if classifier_res is not None
                else ComponentResult(component="incident_type", status="FAILED", confidence=None)
            )
            conf_input_urgency = (
                urgency_res
                if urgency_res is not None
                else ComponentResult(component="urgency", status="FAILED", confidence=None)
            )
            conf_input_location = (
                loc_res
                if loc_res is not None
                else ComponentResult(component="location", status="FAILED", confidence=None)
            )
            conf_input_people = (
                people_res
                if people_res is not None
                else ComponentResult(component="people_at_risk", status="FAILED", confidence=None)
            )
            conf_input_response = (
                resp_res
                if resp_res is not None
                else ComponentResult(component="required_response", status="FAILED", confidence=None)
            )

            conf_res: ConfidenceResult = self.confidence_engine.calculate(
                incident_type=conf_input_classifier,
                urgency=conf_input_urgency,
                location=conf_input_location,
                people_at_risk=conf_input_people,
                required_response=conf_input_response,
                embedding=embedding_vec,
            )
            processing_status = conf_res.status
            all_warnings.extend(conf_res.warnings)
        except Exception as exc:
            self.logger.error(
                "Confidence engine failed during calculation",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            all_warnings.append(f"Component 'confidence_engine' failed: {type(exc).__name__}")
            active_successes = sum(
                1 for c in (classifier_res, urgency_res, loc_res, people_res, resp_res) if c is not None
            )
            if active_successes == 0:
                processing_status = "FAILED"
            else:
                processing_status = "NEEDS_REVIEW"
        return processing_status, round((time.perf_counter() - t0) * 1000, 2)

    def _run_validation(self, payload: dict[str, Any]) -> float:
        t0 = time.perf_counter()
        try:
            self.validator.validate(payload)
        except MLSchemaValidationError:
            raise
        except Exception as exc:
            self.logger.error("Unexpected failure during schema validation gate", exc_info=True)
            raise MLSchemaValidationError(
                f"Schema validator error: {exc}",
                details={"error_type": type(exc).__name__},
            ) from exc
        return round((time.perf_counter() - t0) * 1000, 2)

    def _parse_input(
        self,
        report: str | dict[str, Any] | ProcessingContext,
        report_id: str | None = None,
        location_hint: dict[str, Any] | None = None,
    ) -> tuple[str, str, dict[str, Any] | None]:
        """
        Parses and validates caller input into raw text, report ID, and location hint.
        Ensures immutability of caller structures.
        """
        if isinstance(report, str):
            raw_text = report
            extracted_id = report_id
            extracted_hint = location_hint
        elif isinstance(report, dict):
            # Safe read without mutating caller dictionary
            raw_text = report.get("text") or report.get("raw_text")
            extracted_id = report_id or report.get("report_id") or report.get("id")
            extracted_hint = location_hint or report.get("location_hint")
        elif isinstance(report, ProcessingContext):
            raw_text = report.raw_text
            extracted_id = report_id or report.report_id
            extracted_hint = location_hint or report.location_hint
        else:
            raise MLInputError(
                f"Report must be a str, dict, or ProcessingContext, got {type(report).__name__}",
                details={"type": type(report).__name__},
            )

        if not isinstance(raw_text, str):
            raise MLInputError(
                f"Report text must be a string, got {type(raw_text).__name__}",
                details={"type": type(raw_text).__name__},
            )

        if not raw_text or not raw_text.strip():
            raise MLInputError("Report text cannot be empty or whitespace-only")

        # Resolve or deterministically generate report ID
        final_id = (
            str(extracted_id).strip()
            if extracted_id is not None and str(extracted_id).strip()
            else _generate_deterministic_report_id(raw_text)
        )

        return raw_text, final_id, extracted_hint

    @staticmethod
    def _assemble_canonical_entities(
        loc_entities: list[dict[str, Any]],
        people_entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Merges, deduplicates, and deterministically sorts entity mentions.
        """
        combined = list(loc_entities) + list(people_entities)
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []

        for ent in combined:
            text_val = str(ent.get("text", "")).strip()
            type_val = str(ent.get("type", "")).strip()
            if not text_val:
                continue

            key = (type_val.upper(), text_val.lower())
            if key not in seen:
                seen.add(key)
                deduped.append({
                    "text": text_val,
                    "type": type_val,
                    "confidence": ent.get("confidence"),
                })

        # Canonical deterministic ordering: sort by type then text
        deduped.sort(key=lambda e: (e["type"], e["text"].lower()))
        return deduped


# Process-level default engine singleton
_default_inference_engine: InferenceEngine | None = None


def get_inference_engine(config: MLConfig | None = None) -> InferenceEngine:
    """Returns the process-level singleton InferenceEngine instance."""
    global _default_inference_engine
    if _default_inference_engine is None or config is not None:
        _default_inference_engine = InferenceEngine(config=config)
    return _default_inference_engine


# Public module-level instance for direct import
inference_engine = InferenceEngine()

__all__: list[str] = [
    "InferenceEngine",
    "inference_engine",
    "get_inference_engine",
]

