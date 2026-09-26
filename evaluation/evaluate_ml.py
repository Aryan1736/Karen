"""
Karen's Ear — NLP/ML Prediction Evaluator.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md, ml/schemas/incident_output.json, DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened NLP/ML Benchmark Evaluator

This module benchmarks crisis NLP inference against golden ground truth:
1. Canonical ML Schema Adapter: Ingests nested ml/schemas/incident_output.json payloads.
2. Strict Schema Auditing: Penalizes invalid/missing predictions via coverage_rate.
3. Multiclass Hazard Categorization: Macro F1, Precision, Recall.
4. Report-Level Critical Recall: Safety invariant (zero missed life threats).
5. Urgency Alignment Score: Mean Absolute Error (MAE) and High-Urgency Recall.
6. Hard Negative Discrimination Rate: Slang, drills, and rumor rejection.
7. Location Extraction & Coordinate Hallucination Auditing: Supports TEXT_EXTRACTION vs HINT_ASSISTED.
8. Multilabel Tactical Response Agency Metrics.
9. People-at-Risk Casualty Profiling: Life-safety recall, accuracy, count MAE.
10. Truthful Benchmark Certification: Distinguishes HARNESS_SELF_TEST, MOCK_FIXTURE, and REAL_ML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from evaluation.metrics import (
    ClassificationReport,
    CoverageReport,
    LatencyProfile,
    LocationEvaluationReport,
    MultilabelReport,
    PeopleAtRiskEvaluationReport,
    UrgencyAlignmentReport,
    compute_classification_report,
    compute_coverage_report,
    compute_latency_profile,
    compute_location_metrics,
    compute_multilabel_response_metrics,
    compute_people_at_risk_metrics,
    compute_urgency_alignment,
)
from simulator.models import (
    GroundTruthIncidentType,
    GroundTruthUrgency,
    ScenarioEvent,
)

logger = logging.getLogger("evaluation.ml")


# =============================================================================
# 1. Adapter for ml/schemas/incident_output.json
# =============================================================================

def _safe_float(val: Any) -> Tuple[Optional[float], bool]:
    """Safely parses a float, rejecting NaN, Inf, and unparseable types."""
    if val is None:
        return None, True
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None, False
        return f, True
    except (ValueError, TypeError):
        return None, False


def _safe_int(val: Any) -> Tuple[Optional[int], bool]:
    """Safely parses an int, rejecting NaN, Inf, and unparseable types."""
    if val is None:
        return None, True
    try:
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None, False
        return int(val), True
    except (ValueError, TypeError):
        return None, False


@dataclass
class NormalizedMLPrediction:
    """Canonical, validated representation of an NLP incident analysis output."""
    report_id: str
    incident_type: str
    incident_type_confidence: Optional[float]
    urgency: str
    urgency_confidence: Optional[float]
    people_at_risk_count: Optional[int]
    location_text: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    precision: str
    required_response_types: List[str]
    people_at_risk: Optional[bool] = None
    is_valid: bool = True
    validation_error: Optional[str] = None
    model_version: Optional[str] = None
    processing_status: Optional[str] = None


class MLPredictionAdapter:
    """
    Adapter that normalizes ML pipeline outputs adhering to ml/schemas/incident_output.json
    or legacy flat dictionaries into NormalizedMLPrediction objects.
    Enforces robust validation: unparseable values, NaN, Inf, and out-of-bound ranges
    mark is_valid=False and penalize coverage rate.
    """

    @staticmethod
    def adapt(
        data: Any,
        expected_report_id: Optional[str] = None,
        allow_location_hint_fallback: bool = False,
    ) -> NormalizedMLPrediction:
        """
        Parses raw ML inference output.
        Returns a NormalizedMLPrediction with is_valid=False if the schema is breached.
        """
        if not isinstance(data, dict):
            return NormalizedMLPrediction(
                report_id=expected_report_id or "unknown",
                incident_type="OTHER_GENERAL_INCIDENT",
                incident_type_confidence=None,
                urgency="LOW",
                urgency_confidence=None,
                people_at_risk_count=None,
                location_text=None,
                latitude=None,
                longitude=None,
                precision="unknown",
                required_response_types=[],
                is_valid=False,
                validation_error=f"Prediction is not a dictionary: got {type(data).__name__}",
            )

        report_id = data.get("report_id") or expected_report_id or "unknown"

        # 1. Parse incident_type (nested object in Aryan's schema, or flat string in legacy mocks)
        inc_raw = data.get("incident_type")
        inc_label = "OTHER_GENERAL_INCIDENT"
        inc_conf_raw = None

        if isinstance(inc_raw, dict):
            inc_label = inc_raw.get("label") or "OTHER_GENERAL_INCIDENT"
            inc_conf_raw = inc_raw.get("confidence")
        elif isinstance(inc_raw, str):
            inc_label = inc_raw
        elif inc_raw is not None:
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type="OTHER_GENERAL_INCIDENT",
                incident_type_confidence=None,
                urgency="LOW",
                urgency_confidence=None,
                people_at_risk_count=None,
                location_text=None,
                latitude=None,
                longitude=None,
                precision="unknown",
                required_response_types=[],
                is_valid=False,
                validation_error=f"Invalid incident_type format: {type(inc_raw).__name__}",
            )

        inc_conf, inc_conf_valid = _safe_float(inc_conf_raw)
        if not inc_conf_valid or (inc_conf is not None and not (0.0 <= inc_conf <= 1.0)):
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type=str(inc_label).upper(),
                incident_type_confidence=None,
                urgency="LOW",
                urgency_confidence=None,
                people_at_risk_count=None,
                location_text=None,
                latitude=None,
                longitude=None,
                precision="unknown",
                required_response_types=[],
                is_valid=False,
                validation_error=f"Invalid incident_type confidence (must be float in [0.0, 1.0]): {inc_conf_raw!r}",
            )

        # 2. Parse urgency (nested object in Aryan's schema, or flat string in legacy mocks)
        urg_raw = data.get("urgency")
        urg_label = "LOW"
        urg_conf_raw = None

        if isinstance(urg_raw, dict):
            urg_label = urg_raw.get("label") or "LOW"
            urg_conf_raw = urg_raw.get("confidence")
        elif isinstance(urg_raw, str):
            urg_label = urg_raw
        elif urg_raw is not None:
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type=str(inc_label).upper(),
                incident_type_confidence=inc_conf,
                urgency="LOW",
                urgency_confidence=None,
                people_at_risk_count=None,
                location_text=None,
                latitude=None,
                longitude=None,
                precision="unknown",
                required_response_types=[],
                is_valid=False,
                validation_error=f"Invalid urgency format: {type(urg_raw).__name__}",
            )

        urg_conf, urg_conf_valid = _safe_float(urg_conf_raw)
        if not urg_conf_valid or (urg_conf is not None and not (0.0 <= urg_conf <= 1.0)):
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type=str(inc_label).upper(),
                incident_type_confidence=inc_conf,
                urgency=str(urg_label).upper(),
                urgency_confidence=None,
                people_at_risk_count=None,
                location_text=None,
                latitude=None,
                longitude=None,
                precision="unknown",
                required_response_types=[],
                is_valid=False,
                validation_error=f"Invalid urgency confidence (must be float in [0.0, 1.0]): {urg_conf_raw!r}",
            )

        # 3. Parse location
        loc_raw = data.get("location")
        loc_text = None
        lat_raw = None
        lon_raw = None
        precision = "unknown"

        if isinstance(loc_raw, dict):
            loc_text = loc_raw.get("text")
            lat_raw = loc_raw.get("latitude")
            lon_raw = loc_raw.get("longitude")
            precision = loc_raw.get("precision", "unknown")
        elif allow_location_hint_fallback and isinstance(data.get("location_hint"), dict):
            # Controlled fallback for simulator baseline self-test only
            lh = data["location_hint"]
            loc_text = lh.get("raw_text")
            lat_raw = lh.get("latitude")
            lon_raw = lh.get("longitude")
            precision = lh.get("precision", "unknown")

        lat, lat_valid = _safe_float(lat_raw)
        lon, lon_valid = _safe_float(lon_raw)

        if not lat_valid or not lon_valid:
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type=str(inc_label).upper(),
                incident_type_confidence=inc_conf,
                urgency=str(urg_label).upper(),
                urgency_confidence=urg_conf,
                people_at_risk_count=None,
                location_text=loc_text,
                latitude=None,
                longitude=None,
                precision=str(precision).lower(),
                required_response_types=[],
                is_valid=False,
                validation_error=f"Invalid coordinate format: lat={lat_raw!r}, lon={lon_raw!r}",
            )

        if (lat is not None) != (lon is not None):
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type=str(inc_label).upper(),
                incident_type_confidence=inc_conf,
                urgency=str(urg_label).upper(),
                urgency_confidence=urg_conf,
                people_at_risk_count=None,
                location_text=loc_text,
                latitude=lat,
                longitude=lon,
                precision=str(precision).lower(),
                required_response_types=[],
                is_valid=False,
                validation_error=f"Incomplete coordinate pair: lat={lat}, lon={lon}",
            )

        if lat is not None and not (-90.0 <= lat <= 90.0):
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type=str(inc_label).upper(),
                incident_type_confidence=inc_conf,
                urgency=str(urg_label).upper(),
                urgency_confidence=urg_conf,
                people_at_risk_count=None,
                location_text=loc_text,
                latitude=lat,
                longitude=lon,
                precision=str(precision).lower(),
                required_response_types=[],
                is_valid=False,
                validation_error=f"Latitude out of bounds [-90, 90]: {lat}",
            )

        if lon is not None and not (-180.0 <= lon <= 180.0):
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type=str(inc_label).upper(),
                incident_type_confidence=inc_conf,
                urgency=str(urg_label).upper(),
                urgency_confidence=urg_conf,
                people_at_risk_count=None,
                location_text=loc_text,
                latitude=lat,
                longitude=lon,
                precision=str(precision).lower(),
                required_response_types=[],
                is_valid=False,
                validation_error=f"Longitude out of bounds [-180, 180]: {lon}",
            )

        # 4. Parse people_at_risk
        people_raw = data.get("people_at_risk")
        people_count_raw = None
        people_at_risk_flag: Optional[bool] = None
        if isinstance(people_raw, dict):
            people_count_raw = people_raw.get("count")
            p_conf = people_raw.get("confidence")
            if "at_risk" in people_raw:
                people_at_risk_flag = bool(people_raw["at_risk"])
            elif people_count_raw is not None and isinstance(people_count_raw, (int, float)):
                # When count is explicitly specified, count > 0 dictates life-risk flag
                people_at_risk_flag = (int(people_count_raw) > 0)
            elif p_conf is not None and isinstance(p_conf, (int, float)) and p_conf >= 0.5:
                people_at_risk_flag = True
        elif isinstance(people_raw, bool):
            people_at_risk_flag = people_raw
        elif data.get("people_count") is not None:
            people_count_raw = data["people_count"]

        people_count, count_valid = _safe_int(people_count_raw)
        if not count_valid or (people_count is not None and people_count < 0):
            return NormalizedMLPrediction(
                report_id=report_id,
                incident_type=str(inc_label).upper(),
                incident_type_confidence=inc_conf,
                urgency=str(urg_label).upper(),
                urgency_confidence=urg_conf,
                people_at_risk_count=None,
                location_text=loc_text,
                latitude=lat,
                longitude=lon,
                precision=str(precision).lower(),
                required_response_types=[],
                people_at_risk=False,
                is_valid=False,
                validation_error=f"Invalid people_at_risk count (must be non-negative integer): {people_count_raw!r}",
            )

        if people_at_risk_flag is None:
            if people_count is not None:
                people_at_risk_flag = (people_count > 0)
            else:
                people_at_risk_flag = False

        # 5. Parse required_response
        resp_raw = data.get("required_response")
        resp_types: List[str] = []
        if isinstance(resp_raw, list):
            for item in resp_raw:
                if isinstance(item, dict) and "type" in item:
                    resp_types.append(str(item["type"]).upper())
                elif isinstance(item, str):
                    resp_types.append(item.upper())

        model_version = str(data.get("model_version")) if data.get("model_version") is not None else None
        proc_status = str(data.get("processing_status")) if data.get("processing_status") is not None else None

        return NormalizedMLPrediction(
            report_id=report_id,
            incident_type=str(inc_label).upper(),
            incident_type_confidence=inc_conf,
            urgency=str(urg_label).upper(),
            urgency_confidence=urg_conf,
            people_at_risk_count=people_count,
            location_text=loc_text,
            latitude=lat,
            longitude=lon,
            precision=str(precision).lower(),
            required_response_types=resp_types,
            people_at_risk=people_at_risk_flag,
            is_valid=True,
            model_version=model_version,
            processing_status=proc_status,
        )


# =============================================================================
# 2. Report Data Structure
# =============================================================================

class EvaluationMode(str, Enum):
    HARNESS_SELF_TEST = "HARNESS_SELF_TEST"
    MOCK_FIXTURE = "MOCK_FIXTURE"
    REAL_ML = "REAL_ML"


class LocationEvalMode(str, Enum):
    TEXT_EXTRACTION = "TEXT_EXTRACTION"
    HINT_ASSISTED = "HINT_ASSISTED"


@dataclass
class MLEvaluationReport:
    """Quantitative scorecard of NLP pipeline performance."""
    total_samples: int
    coverage: CoverageReport
    hazard_classification: ClassificationReport
    urgency_mae: Optional[float]
    high_urgency_recall: Optional[float]
    report_critical_recall: Optional[float]
    hard_negative_rejection_rate: Optional[float]
    hard_negative_tested: int
    hard_negative_rejected: int
    location_report: Optional[LocationEvaluationReport] = None
    response_report: Optional[MultilabelReport] = None
    people_report: Optional[PeopleAtRiskEvaluationReport] = None
    evaluation_mode: EvaluationMode = EvaluationMode.HARNESS_SELF_TEST
    is_real_system_result: bool = False
    details: List[Dict[str, Any]] = field(default_factory=list)
    latency_profile: Optional[LatencyProfile] = None
    latencies_ms: List[float] = field(default_factory=list)
    cold_latency_ms: Optional[float] = None
    warm_latency_profile: Optional[LatencyProfile] = None
    model_version: Optional[str] = None
    status_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def is_hermetic_mock(self) -> bool:
        return not self.is_real_system_result

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "total_samples": self.total_samples,
            "coverage_rate": round(self.coverage.coverage_rate, 4),
            "valid_predictions": self.coverage.valid_predictions,
            "invalid_predictions": self.coverage.invalid_predictions,
            "macro_f1": round(self.hazard_classification.macro_f1, 4),
            "macro_precision": round(self.hazard_classification.macro_precision, 4),
            "macro_recall": round(self.hazard_classification.macro_recall, 4),
            "accuracy": round(self.hazard_classification.accuracy, 4),
            "urgency_mae": round(self.urgency_mae, 4) if self.urgency_mae is not None else None,
            "high_urgency_recall": round(self.high_urgency_recall, 4) if self.high_urgency_recall is not None else None,
            "report_critical_recall": round(self.report_critical_recall, 4) if self.report_critical_recall is not None else None,
            "hard_negative_rejection_rate": round(self.hard_negative_rejection_rate, 4) if self.hard_negative_rejection_rate is not None else None,
            "hard_negative_tested": self.hard_negative_tested,
            "hard_negative_rejected": self.hard_negative_rejected,
            "location_metrics": self.location_report.to_dict() if self.location_report else None,
            "response_metrics": self.response_report.to_dict() if self.response_report else None,
            "people_metrics": self.people_report.to_dict() if self.people_report else None,
            "evaluation_mode": self.evaluation_mode.value,
            "is_real_system_result": self.is_real_system_result,
            "is_hermetic_mock": self.is_hermetic_mock,
        }
        if self.latency_profile is not None:
            d["latency_profile"] = self.latency_profile.to_dict()
        if self.cold_latency_ms is not None:
            d["cold_latency_ms"] = round(self.cold_latency_ms, 2)
        if self.warm_latency_profile is not None:
            d["warm_latency_profile"] = self.warm_latency_profile.to_dict()
        if self.model_version is not None:
            d["model_version"] = self.model_version
        if self.status_counts:
            d["status_counts"] = dict(self.status_counts)
        return d


# =============================================================================
# 3. Evaluation Runner
# =============================================================================

def evaluate_ml_predictions(
    events: Sequence[ScenarioEvent],
    predict_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    mock_predictions: Optional[Sequence[Dict[str, Any]]] = None,
    location_mode: LocationEvalMode = LocationEvalMode.HINT_ASSISTED,
    is_real_system_result: Optional[bool] = None,
) -> MLEvaluationReport:
    """
    Evaluates ML performance against ground-truth labels for a sequence of ScenarioEvents.

    Args:
        events: Ground-truth ScenarioEvents.
        predict_fn: Optional callable taking text string and returning canonical ML output.
        mock_predictions: Optional pre-computed predictions matching events.
        location_mode: Location evaluation mode (TEXT_EXTRACTION vs HINT_ASSISTED).
        is_real_system_result: Explicit provenance override. If None, derived strictly from inputs.

    Returns:
        MLEvaluationReport with quantitative benchmark metrics.
    """
    if not events:
        raise ValueError("Cannot evaluate empty events list.")

    if predict_fn is not None:
        eval_mode = EvaluationMode.REAL_ML
        real_result = True if is_real_system_result is None else is_real_system_result
    elif mock_predictions is not None:
        eval_mode = EvaluationMode.MOCK_FIXTURE
        # Mocks are NOT real system benchmarks unless explicitly certified
        real_result = False if is_real_system_result is None else is_real_system_result
    else:
        eval_mode = EvaluationMode.HARNESS_SELF_TEST
        real_result = False

    y_true_hazard: List[str] = []
    y_pred_hazard: List[str] = []

    y_true_urgency: List[str] = []
    y_pred_urgency: List[str] = []

    true_locations: List[Dict[str, Any]] = []
    pred_locations: List[Dict[str, Any]] = []

    true_responses: List[List[str]] = []
    pred_responses: List[List[str]] = []

    y_true_at_risk: List[bool] = []
    y_pred_at_risk: List[bool] = []
    y_true_people_count: List[Optional[int]] = []
    y_pred_people_count: List[Optional[int]] = []

    crit_gt_count = 0
    crit_correct_count = 0

    hn_total = 0
    hn_rejected = 0

    status_counts: Dict[str, int] = {}
    detected_model_version: Optional[str] = None
    valid_predictions = 0
    invalid_predictions = 0
    invalid_reasons: List[str] = []
    details: List[Dict[str, Any]] = []

    allow_fallback = (eval_mode == EvaluationMode.HARNESS_SELF_TEST or location_mode == LocationEvalMode.HINT_ASSISTED)

    # Build lookup index if mock_predictions is provided
    mock_by_report_id: Optional[Dict[str, Any]] = None
    mock_list: Optional[Sequence[Any]] = None
    if mock_predictions is not None:
        if isinstance(mock_predictions, dict):
            mock_by_report_id = mock_predictions
        elif isinstance(mock_predictions, (list, tuple)):
            mock_list = mock_predictions
            mock_by_report_id = {}
            for item in mock_predictions:
                if isinstance(item, dict) and "report_id" in item:
                    mock_by_report_id[str(item["report_id"])] = item

    for idx, event in enumerate(events):
        gt = event.ground_truth
        dispatch = event.dispatch
        text = dispatch.text

        # Determine prediction input
        if mock_predictions is not None:
            if mock_by_report_id and dispatch.report_id in mock_by_report_id:
                raw_pred = mock_by_report_id[dispatch.report_id]
            elif mock_list is not None and not mock_by_report_id and idx < len(mock_list):
                raw_pred = mock_list[idx]
            else:
                raw_pred = None
        elif predict_fn is not None:
            loc_hint_dict = dispatch.location_hint.model_dump(mode="json") if dispatch.location_hint else None
            try:
                raw_pred = predict_fn(text, dispatch.report_id, loc_hint_dict)
            except TypeError:
                try:
                    raw_pred = predict_fn(text, dispatch.report_id)
                except TypeError:
                    raw_pred = predict_fn(text)
        else:
            # Hermetic baseline simulator prediction (matches GT to establish benchmark harness baseline)
            expected_resps = []
            if gt.expected_required_response is not None:
                expected_resps = [
                    r.value if hasattr(r, "value") else str(r)
                    for r in gt.expected_required_response
                ]
            elif gt.expected_people_at_risk:
                expected_resps = ["SEARCH_AND_RESCUE"]

            raw_pred = {
                "report_id": dispatch.report_id,
                "incident_type": {
                    "label": gt.expected_incident_type.value if gt.expected_incident_type else "OTHER_GENERAL_INCIDENT",
                    "confidence": 0.95,
                },
                "urgency": {
                    "label": gt.expected_urgency.value if gt.expected_urgency else "LOW",
                    "confidence": 0.92,
                },
                "people_at_risk": {
                    "count": gt.expected_people_count,
                    "confidence": 0.88 if gt.expected_people_at_risk else 0.1,
                    "at_risk": bool(gt.expected_people_at_risk),
                },
                "location": {
                    "text": dispatch.location_hint.raw_text if dispatch.location_hint else None,
                    "latitude": dispatch.location_hint.latitude if dispatch.location_hint else None,
                    "longitude": dispatch.location_hint.longitude if dispatch.location_hint else None,
                    "precision": dispatch.location_hint.precision.value if dispatch.location_hint else "unknown",
                    "confidence": 0.90,
                },
                "required_response": [
                    {"type": r, "confidence": 0.95} for r in expected_resps
                ],
            }

        # Adapt and validate prediction (zero fallback to ground truth if prediction is missing)
        if raw_pred is None and (mock_predictions is not None or predict_fn is not None):
            norm_pred = NormalizedMLPrediction(
                report_id=dispatch.report_id,
                incident_type="OTHER_GENERAL_INCIDENT",
                incident_type_confidence=0.0,
                urgency="LOW",
                urgency_confidence=0.0,
                people_at_risk=False,
                people_at_risk_count=None,
                location_text=None,
                latitude=None,
                longitude=None,
                precision="unknown",
                required_response_types=[],
                is_valid=False,
                validation_error="Prediction missing from model output",
            )
        else:
            norm_pred = MLPredictionAdapter.adapt(
                raw_pred,
                expected_report_id=dispatch.report_id,
                allow_location_hint_fallback=allow_fallback,
            )

        if norm_pred.is_valid:
            valid_predictions += 1
        else:
            invalid_predictions += 1
            if norm_pred.validation_error:
                invalid_reasons.append(norm_pred.validation_error)

        if norm_pred.processing_status:
            st = norm_pred.processing_status.upper()
            status_counts[st] = status_counts.get(st, 0) + 1
        if norm_pred.model_version and detected_model_version is None:
            detected_model_version = norm_pred.model_version

        true_hazard = gt.expected_incident_type.value if gt.expected_incident_type else "OTHER_GENERAL_INCIDENT"
        pred_hazard = norm_pred.incident_type

        true_urgency = gt.expected_urgency.value if gt.expected_urgency else "LOW"
        pred_urgency = norm_pred.urgency

        y_true_hazard.append(true_hazard)
        y_pred_hazard.append(pred_hazard)

        y_true_urgency.append(true_urgency)
        y_pred_urgency.append(pred_urgency)

        # Collect location data
        true_loc_dict = {
            "raw_text": dispatch.location_hint.raw_text if dispatch.location_hint else None,
            "latitude": dispatch.location_hint.latitude if dispatch.location_hint else None,
            "longitude": dispatch.location_hint.longitude if dispatch.location_hint else None,
        }
        pred_loc_dict = {
            "text": norm_pred.location_text,
            "latitude": norm_pred.latitude,
            "longitude": norm_pred.longitude,
        }
        true_locations.append(true_loc_dict)
        pred_locations.append(pred_loc_dict)

        # Collect tactical response agencies
        expected_responses: List[str] = []
        if gt.expected_required_response is not None:
            expected_responses = [
                r.value if hasattr(r, "value") else str(r)
                for r in gt.expected_required_response
            ]
        elif gt.expected_people_at_risk:
            expected_responses = ["SEARCH_AND_RESCUE"]

        true_responses.append(expected_responses)
        pred_responses.append(norm_pred.required_response_types)

        # Track people at risk & casualty counts
        gt_at_risk_flag = bool(gt.expected_people_at_risk)
        pred_at_risk_flag = bool(norm_pred.people_at_risk if norm_pred.people_at_risk is not None else (norm_pred.people_at_risk_count and norm_pred.people_at_risk_count > 0))
        y_true_at_risk.append(gt_at_risk_flag)
        y_pred_at_risk.append(pred_at_risk_flag)
        y_true_people_count.append(gt.expected_people_count)
        y_pred_people_count.append(norm_pred.people_at_risk_count)

        # Track single-report critical recall
        if true_urgency == "CRITICAL":
            crit_gt_count += 1
            if pred_urgency == "CRITICAL":
                crit_correct_count += 1

        # Track hard-negative discrimination: non-actionable distractors, rumors, drills, slang
        # Must strictly have expected_urgency == LOW (or expected_actionable is False)
        is_hard_negative = (
            (gt.expected_actionable is False)
            or (
                gt.expected_urgency
                and gt.expected_urgency.value == "LOW"
                and (
                    (gt.relation_type and gt.relation_type.value in ("NOISE", "UNCERTAIN"))
                    or (gt.expected_incident_type is None or gt.expected_incident_type.value == "OTHER_GENERAL_INCIDENT")
                )
            )
        )
        if is_hard_negative:
            hn_total += 1
            if pred_urgency == "LOW":
                hn_rejected += 1

        details.append({
            "event_id": event.event_id,
            "report_id": dispatch.report_id,
            "true_hazard": true_hazard,
            "pred_hazard": pred_hazard,
            "true_urgency": true_urgency,
            "pred_urgency": pred_urgency,
            "is_critical": (true_urgency == "CRITICAL"),
            "is_valid": norm_pred.is_valid,
            "processing_status": norm_pred.processing_status,
        })

    # Compute classification reports
    hazard_report = compute_classification_report(y_true_hazard, y_pred_hazard)
    urgency_report = compute_urgency_alignment(y_true_urgency, y_pred_urgency)
    location_report = compute_location_metrics(true_locations, pred_locations, mode=location_mode.value)
    response_report = compute_multilabel_response_metrics(true_responses, pred_responses)
    people_report = compute_people_at_risk_metrics(
        gt_at_risk=y_true_at_risk,
        pred_at_risk=y_pred_at_risk,
        gt_counts=y_true_people_count,
        pred_counts=y_pred_people_count,
    )

    coverage_rep = compute_coverage_report(
        total_samples=len(events),
        valid_predictions=valid_predictions,
        invalid_predictions=invalid_predictions,
        invalid_reasons=invalid_reasons,
    )

    report_crit_recall = (
        (crit_correct_count / crit_gt_count) if crit_gt_count > 0 else None
    )
    hn_rate = (
        (hn_rejected / hn_total) if hn_total > 0 else None
    )

    return MLEvaluationReport(
        total_samples=len(events),
        coverage=coverage_rep,
        hazard_classification=hazard_report,
        urgency_mae=urgency_report.mae,
        high_urgency_recall=urgency_report.high_urgency_recall,
        report_critical_recall=report_crit_recall,
        hard_negative_rejection_rate=hn_rate,
        hard_negative_tested=hn_total,
        hard_negative_rejected=hn_rejected,
        location_report=location_report,
        response_report=response_report,
        people_report=people_report,
        evaluation_mode=eval_mode,
        is_real_system_result=real_result,
        details=details,
        model_version=detected_model_version,
        status_counts=status_counts,
    )


# =============================================================================
# 4. Real ML Inference Adapter & Benchmark Runner
# =============================================================================

def build_real_ml_predictor(
    include_embedding: bool = False,
    latency_collector: Optional[List[float]] = None,
) -> Callable[[str, Optional[str], Optional[Dict[str, Any]]], Dict[str, Any]]:
    """
    Builds a real ML predictor closure reusing a single process-wide InferenceEngine instance.
    Calls get_inference_engine() exactly once upon creation.
    Strictly forwards only legitimate public dispatch fields: report text, report_id, location_hint.
    Zero ground truth is passed to the ML engine.
    """
    from ml.pipeline import get_inference_engine

    engine = get_inference_engine()

    def predict(
        text: str,
        report_id: Optional[str] = None,
        location_hint: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        result = engine.analyze(
            report=text,
            report_id=report_id,
            location_hint=location_hint,
            include_embedding=include_embedding,
        )
        t_elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if latency_collector is not None:
            latency_collector.append(t_elapsed_ms)
        return result

    return predict


def evaluate_real_ml(
    events: Optional[Sequence[ScenarioEvent]] = None,
    location_mode: LocationEvalMode = LocationEvalMode.HINT_ASSISTED,
    include_embedding: bool = False,
) -> MLEvaluationReport:
    """
    Executes the REAL_ML benchmark against Aryan's live inference engine.
    Reuses a single process-level engine instance across all events.
    Captures true inference latencies and produces an MLEvaluationReport marked REAL_ML.
    """
    if events is None:
        from simulator.scenarios import get_scenario, list_scenarios
        events = []
        for sid in list_scenarios():
            events.extend(get_scenario(sid))

    measured_latencies: List[float] = []
    predictor = build_real_ml_predictor(
        include_embedding=include_embedding,
        latency_collector=measured_latencies,
    )

    report = evaluate_ml_predictions(
        events=events,
        predict_fn=predictor,
        location_mode=location_mode,
        is_real_system_result=True,
    )

    if measured_latencies:
        report.latencies_ms = measured_latencies
        report.latency_profile = compute_latency_profile(measured_latencies)
        report.cold_latency_ms = measured_latencies[0]
        if len(measured_latencies) > 1:
            report.warm_latency_profile = compute_latency_profile(measured_latencies[1:])

    return report


def main(args: Optional[List[str]] = None) -> int:
    import argparse
    from pathlib import Path
    import sys

    parser = argparse.ArgumentParser(description="Karen's Ear ML/NLP Evaluation Runner")
    parser.add_argument("--real-ml", action="store_true", help="Evaluate live Aryan ML pipeline")
    parser.add_argument("--output", "-o", help="Optional output JSON path")
    parser.add_argument("--location-mode", choices=["TEXT_EXTRACTION", "HINT_ASSISTED"], default="HINT_ASSISTED")
    parser.add_argument("--include-embedding", action="store_true", help="Request embeddings from inference engine")
    parser.add_argument("--scenarios", nargs="*", default=None, help="Specific scenario names to evaluate")
    parsed = parser.parse_args(args)

    loc_mode = LocationEvalMode(parsed.location_mode)
    from simulator.scenarios import get_scenario, list_scenarios

    scenario_names = parsed.scenarios or list_scenarios()
    events: List[ScenarioEvent] = []
    for sid in scenario_names:
        events.extend(get_scenario(sid))

    if parsed.real_ml:
        report = evaluate_real_ml(
            events=events,
            location_mode=loc_mode,
            include_embedding=parsed.include_embedding,
        )
    else:
        report = evaluate_ml_predictions(
            events=events,
            location_mode=loc_mode,
        )

    rep_dict = report.to_dict()
    print(json.dumps(rep_dict, indent=2))

    if parsed.output:
        out_p = Path(parsed.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(rep_dict, f, indent=2)
        print(f"\n[OK] ML evaluation report saved to {out_p}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
