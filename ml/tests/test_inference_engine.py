"""
Karen's Ear — Comprehensive Unit & Integration Tests for Unified Inference Pipeline.

Feature 10 — Step 5 of the ML pipeline (architecture/ml-pipeline.md).
Tests:
- Single public orchestration entry point: inference_engine.analyze(report) / InferenceEngine.analyze(report)
- End-to-end inference flow across all 9 prior features
- Report ID preservation & deterministic generation
- Model version propagation
- Strict schema validation against ml/schemas/incident_output.json
- Canonical output field names, types, and ordering
- Strict No-Hallucination invariant (coordinates strictly null)
- Failure isolation across each component (fail-soft vs fail-fast)
- Low confidence -> NEEDS_REVIEW degradation
- Recoverable component failures -> PARTIAL degradation
- Complete infrastructure failure -> FAILED degradation
- Schema violation rejection
- Privacy: Zero raw report text in logs
- Immutability of caller objects
- Determinism for identical inputs
- Realistic crisis dispatches
- Adversarial negation dispatches
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import jsonschema
import pytest

from ml import (
    CANONICAL_INCIDENT_TYPES,
    CANONICAL_PROCESSING_STATUSES,
    CANONICAL_RESPONSE_TYPES,
    CANONICAL_URGENCY_LEVELS,
    ComponentResult,
    InferenceEngine,
    MLConfig,
    MLInputError,
    MLSchemaValidationError,
    ModelMetadata,
    ProcessingContext,
    SchemaValidator,
    get_inference_engine,
    inference_engine,
    validate_incident_output,
)
from ml.classification.incident_classifier import ClassificationResult, IncidentClassifier
from ml.confidence.confidence_engine import ConfidenceEngine, ConfidenceResult
from ml.embeddings.embedder import SentenceTransformerEmbedder
from ml.extraction.location_entity_extractor import (
    EntityMention,
    LocationEntityExtractor,
    LocationEntityResult,
    LocationPrediction,
)
from ml.extraction.people_risk_extractor import (
    PeopleRiskExtractor,
    PeopleRiskResult,
    RiskEvidence,
)
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner
from ml.response.response_extractor import (
    RequiredResponseExtractor,
    ResponseExtractionResult,
    ResponseNeed,
)
from ml.urgency.urgency_engine import (
    ComponentScore,
    UrgencyBreakdown,
    UrgencyEngine,
    UrgencyResult,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "incident_output.json"


@pytest.fixture(scope="module")
def canonical_schema() -> dict:
    """Loads canonical incident output schema once for the test module."""
    assert SCHEMA_PATH.exists(), f"Schema missing at {SCHEMA_PATH}"
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def engine() -> InferenceEngine:
    """Returns a shared InferenceEngine for the test module."""
    return InferenceEngine()


# ==============================================================================
# 1. Pipeline Entry Point & Contract Verification
# ==============================================================================


class TestPipelineContractAndBasics:
    """Verifies the public API contract, schema validation, and frozen shape."""

    def test_01_public_entry_point_exists(self, engine: InferenceEngine) -> None:
        """Verifies single public entry point exists and is callable."""
        assert hasattr(engine, "analyze")
        assert callable(engine.analyze)
        assert hasattr(InferenceEngine, "analyze")
        assert callable(InferenceEngine.analyze)
        assert isinstance(inference_engine, InferenceEngine)
        assert hasattr(inference_engine, "analyze")
        assert callable(inference_engine.analyze)

    def test_02_successful_end_to_end_report(self, engine: InferenceEngine, canonical_schema: dict) -> None:
        """Verifies complete end-to-end execution of a realistic emergency dispatch."""
        text = "Flash flood waters are rapidly rising around Patia underpass. Several vehicles are stranded."
        result = engine.analyze(text, report_id="rep-flood-01")

        # Must strictly validate against canonical schema
        jsonschema.validate(instance=result, schema=canonical_schema)

        assert result["report_id"] == "rep-flood-01"
        assert result["model_version"] == "all-MiniLM-L6-v2+heuristic-v1"
        assert result["processing_status"] in CANONICAL_PROCESSING_STATUSES
        assert isinstance(result["incident_type"], dict)
        assert isinstance(result["urgency"], dict)
        assert isinstance(result["location"], dict)
        assert isinstance(result["people_at_risk"], dict)
        assert isinstance(result["required_response"], list)
        assert isinstance(result["entities"], list)
        assert isinstance(result["warnings"], list)
        assert result["embedding_reference"] == "emb-rep-flood-01"

    def test_03_report_id_propagation_and_preservation(self, engine: InferenceEngine) -> None:
        """Preserves caller-provided report ID without mutation."""
        res_str = engine.analyze("Fire reported on Main Street", report_id="rep-custom-99")
        assert res_str["report_id"] == "rep-custom-99"

        res_dict = engine.analyze({"text": "Fire reported on Main Street", "report_id": "rep-dict-42"})
        assert res_dict["report_id"] == "rep-dict-42"

        ctx = ProcessingContext(report_id="rep-ctx-77", raw_text="Fire reported on Main Street")
        res_ctx = engine.analyze(ctx)
        assert res_ctx["report_id"] == "rep-ctx-77"

    def test_04_deterministic_report_id_generation(self, engine: InferenceEngine) -> None:
        """Generates deterministic prefixed report ID when omitted by caller."""
        text = "Gas pipeline explosion near Khandagiri junction"
        res1 = engine.analyze(text)
        res2 = engine.analyze(text)

        assert res1["report_id"].startswith("rep-")
        assert res1["report_id"] == res2["report_id"]

    def test_05_model_version_propagation(self, engine: InferenceEngine) -> None:
        """Propagates configured ML model version to output."""
        res = engine.analyze("Medical emergency at school campus", report_id="rep-med-01")
        assert res["model_version"] == engine.config.model_version
        assert "all-MiniLM-L6-v2" in res["model_version"]

    def test_06_sole_public_entry_point_enforced(self, canonical_schema: dict) -> None:
        """
        Verifies InferenceEngine.analyze is the sole public orchestration entry point:
        - The old analyze_report wrapper is no longer exported from ml, ml.pipeline, or ml.pipeline.inference_engine
        - Neither ml nor ml.pipeline exposes a second public orchestration function
        - The canonical public path (inference_engine.analyze) executes successfully end-to-end
        """
        import ml
        import ml.pipeline
        import ml.pipeline.inference_engine as ie_mod

        # 1. InferenceEngine.analyze exists and is canonical
        assert hasattr(InferenceEngine, "analyze")
        assert callable(InferenceEngine.analyze)
        assert isinstance(inference_engine, InferenceEngine)

        # 2. The old analyze_report wrapper is no longer exported anywhere
        assert not hasattr(ml, "analyze_report"), "ml must not export analyze_report"
        assert not hasattr(ml.pipeline, "analyze_report"), "ml.pipeline must not export analyze_report"
        assert not hasattr(ie_mod, "analyze_report"), "ml.pipeline.inference_engine must not expose analyze_report"
        assert "analyze_report" not in getattr(ml, "__all__", [])
        assert "analyze_report" not in getattr(ml.pipeline, "__all__", [])
        assert "analyze_report" not in getattr(ie_mod, "__all__", [])

        # 3. ml.pipeline does not expose a second public orchestration function
        pipeline_public_callables = [
            name
            for name in getattr(ml.pipeline, "__all__", dir(ml.pipeline))
            if not name.startswith("_")
            and callable(getattr(ml.pipeline, name))
            and not isinstance(getattr(ml.pipeline, name), type)
        ]
        orchestration_pipeline_fns = [fn for fn in pipeline_public_callables if fn.startswith("analyze")]
        assert orchestration_pipeline_fns == [], f"Found unexpected orchestration function in ml.pipeline: {orchestration_pipeline_fns}"

        # 4. ml does not expose a second public orchestration function
        ml_public_callables = [
            name
            for name in getattr(ml, "__all__", dir(ml))
            if not name.startswith("_")
            and callable(getattr(ml, name))
            and not isinstance(getattr(ml, name), type)
        ]
        orchestration_ml_fns = [fn for fn in ml_public_callables if fn.startswith("analyze")]
        assert orchestration_ml_fns == [], f"Found unexpected orchestration function in ml: {orchestration_ml_fns}"

        # 5. Canonical public usage path (inference_engine.analyze) executes end-to-end successfully
        res = inference_engine.analyze("Severe storm damage on NH16 highway", report_id="rep-storm-01")
        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["report_id"] == "rep-storm-01"

    def test_07_embedding_inclusion_toggle(self, engine: InferenceEngine, canonical_schema: dict) -> None:
        """Verifies embedding field is omitted by default and present only when requested."""
        text = "Minor street flooding near market square"
        res_default = engine.analyze(text, report_id="rep-emb-def")
        assert "embedding" not in res_default
        assert res_default["embedding_reference"] == "emb-rep-emb-def"
        jsonschema.validate(instance=res_default, schema=canonical_schema)

        res_with_emb = engine.analyze(text, report_id="rep-emb-inc", include_embedding=True)
        assert "embedding" in res_with_emb
        assert isinstance(res_with_emb["embedding"], list)
        assert len(res_with_emb["embedding"]) == 384
        jsonschema.validate(instance=res_with_emb, schema=canonical_schema)

    def test_08_no_hallucinated_coordinates(self, engine: InferenceEngine) -> None:
        """Verifies strict no-hallucination policy for geographic coordinates."""
        res = engine.analyze("Fire spreading near Rasulgarh flyover", report_id="rep-coord-01")
        assert res["location"]["latitude"] is None
        assert res["location"]["longitude"] is None
        assert res["location"]["precision"] in ("exact", "approximate", "unknown")


# ==============================================================================
# 2. Input Validation (Fail-Fast Policy)
# ==============================================================================


class TestInputValidationFailFast:
    """Verifies fail-fast behavior on malformed, empty, or invalid inputs."""

    def test_09_empty_string_rejected(self, engine: InferenceEngine) -> None:
        """Rejects empty string with MLInputError."""
        with pytest.raises(MLInputError, match="empty or whitespace-only"):
            engine.analyze("")

    def test_10_whitespace_only_rejected(self, engine: InferenceEngine) -> None:
        """Rejects whitespace-only string with MLInputError."""
        with pytest.raises(MLInputError, match="empty or whitespace-only"):
            engine.analyze("   \n\t   ")

    def test_11_non_string_type_rejected(self, engine: InferenceEngine) -> None:
        """Rejects non-string/non-dict types with MLInputError."""
        with pytest.raises(MLInputError, match="Report must be a str, dict, or ProcessingContext"):
            engine.analyze(12345)  # type: ignore

    def test_12_dict_without_text_rejected(self, engine: InferenceEngine) -> None:
        """Rejects report dictionary lacking text field."""
        with pytest.raises(MLInputError, match="Report text must be a string"):
            engine.analyze({"report_id": "rep-no-text"})

    def test_13_caller_input_immutability(self, engine: InferenceEngine) -> None:
        """Caller dictionary is never mutated."""
        input_dict = {
            "text": "Tree fallen on car near Patia",
            "report_id": "rep-immutable-01",
            "location_hint": {"raw_text": "Patia"},
        }
        original_dict = dict(input_dict)
        engine.analyze(input_dict)
        assert input_dict == original_dict


# ==============================================================================
# 3. Component Invocations & Canonical Assembly
# ==============================================================================


class TestComponentAssemblyAndDeterminism:
    """Verifies that all components execute in order and assemble deterministically."""

    def test_14_canonical_entity_ordering_is_deterministic(self, engine: InferenceEngine) -> None:
        """Verifies entities are ordered deterministically by type then text."""
        text = "Three people trapped in a white van near Rasulgarh flyover."
        res1 = engine.analyze(text, report_id="rep-order-01")
        res2 = engine.analyze(text, report_id="rep-order-01")

        assert res1["entities"] == res2["entities"]
        # Verify sorted by (type, text)
        types_texts = [(e["type"], e["text"].lower()) for e in res1["entities"]]
        assert types_texts == sorted(types_texts)

    def test_15_canonical_response_ordering_is_deterministic(self, engine: InferenceEngine) -> None:
        """Verifies required responses follow canonical taxonomy precedence."""
        text = "Building collapse with multiple casualties, gas leak, and live wires."
        res = engine.analyze(text, report_id="rep-order-resp")

        types = [r["type"] for r in res["required_response"]]
        # Each type should be in CANONICAL_RESPONSE_TYPES
        for t in types:
            assert t in CANONICAL_RESPONSE_TYPES

        # Verify sorted according to CANONICAL_RESPONSE_TYPES order
        indices = [CANONICAL_RESPONSE_TYPES.index(t) for t in types]
        assert indices == sorted(indices)

    def test_16_deterministic_output_across_runs(self, engine: InferenceEngine) -> None:
        """Identical input produces identical JSON structure and values."""
        text = "Flash flood at Patia square, two cars submerged."
        res1 = engine.analyze(text, report_id="rep-det-01")
        res2 = engine.analyze(text, report_id="rep-det-01")

        assert res1 == res2

    def test_17_stage_latencies_measured_and_recorded(self, engine: InferenceEngine) -> None:
        """Stage latencies are measured and available in execution metadata."""
        engine.analyze("Ambulance needed for heart attack victim at hospital", report_id="rep-lat-01")
        meta = engine.last_execution_metadata
        assert "stage_latencies_ms" in meta
        stages = meta["stage_latencies_ms"]
        assert "preprocessing_ms" in stages
        assert "classification_ms" in stages
        assert "extraction_ms" in stages
        assert "response_ms" in stages
        assert "urgency_ms" in stages
        assert "embedding_ms" in stages
        assert "confidence_ms" in stages
        assert "validation_ms" in stages
        assert "total_ms" in stages


# ==============================================================================
# 4. Failure Isolation & Graceful Degradation (Fail-Soft Policy)
# ==============================================================================


class TestFailureIsolation:
    """Verifies that individual component failures do not destroy other outputs."""

    def test_18_classifier_failure_isolation(self, canonical_schema: dict) -> None:
        """When classifier fails, incident_type is null but other components survive."""
        mock_classifier = MagicMock(spec=IncidentClassifier)
        mock_classifier.predict.side_effect = RuntimeError("Classifier model crashed")

        engine = InferenceEngine(classifier=mock_classifier)
        res = engine.analyze("Fire on Main Street, 2 injured", report_id="rep-fail-class")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["incident_type"]["label"] is None
        assert res["incident_type"]["confidence"] is None
        # Other components survived!
        assert res["urgency"]["label"] is not None
        assert res["location"]["text"] is not None
        assert res["people_at_risk"]["count"] == 2
        assert len(res["required_response"]) > 0
        assert res["embedding_reference"] is not None
        assert res["processing_status"] in ("PARTIAL", "NEEDS_REVIEW")
        assert any("Component 'classification' failed" in w for w in res["warnings"])

    def test_19_location_extractor_failure_isolation(self, canonical_schema: dict) -> None:
        """When location extractor fails, location is null but others survive."""
        mock_loc = MagicMock(spec=LocationEntityExtractor)
        mock_loc.extract.side_effect = ValueError("NER gazetteer error")

        engine = InferenceEngine(location_extractor=mock_loc)
        res = engine.analyze("Flash flooding near Rasulgarh underpass", report_id="rep-fail-loc")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["location"]["text"] is None
        assert res["location"]["confidence"] is None
        assert res["location"]["latitude"] is None
        assert res["location"]["longitude"] is None
        # Other components preserved
        assert res["incident_type"]["label"] is not None
        assert res["urgency"]["label"] is not None
        assert res["embedding_reference"] is not None
        assert res["processing_status"] in ("PARTIAL", "NEEDS_REVIEW")
        assert any("Component 'location' failed" in w for w in res["warnings"])

    def test_20_people_extractor_failure_isolation(self, canonical_schema: dict) -> None:
        """When people extractor fails, people_at_risk count is null but others survive."""
        mock_people = MagicMock(spec=PeopleRiskExtractor)
        mock_people.extract.side_effect = RuntimeError("Regex engine fault")

        engine = InferenceEngine(people_extractor=mock_people)
        res = engine.analyze("5 people trapped inside collapsing building", report_id="rep-fail-people")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["people_at_risk"]["count"] is None
        assert res["people_at_risk"]["confidence"] is None
        assert res["incident_type"]["label"] is not None
        assert res["urgency"]["label"] is not None
        assert any("Component 'people_at_risk' failed" in w for w in res["warnings"])

    def test_21_response_extractor_failure_isolation(self, canonical_schema: dict) -> None:
        """When response extractor fails, required_response is empty array but others survive."""
        mock_resp = MagicMock(spec=RequiredResponseExtractor)
        mock_resp.extract.side_effect = RuntimeError("Taxonomy lookup failed")

        engine = InferenceEngine(response_extractor=mock_resp)
        res = engine.analyze("Gas leak spreading rapidly", report_id="rep-fail-resp")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["required_response"] == []
        assert res["incident_type"]["label"] is not None
        assert res["urgency"]["label"] is not None
        assert any("Component 'required_response' failed" in w for w in res["warnings"])

    def test_22_urgency_engine_failure_isolation(self, canonical_schema: dict) -> None:
        """When urgency engine fails, urgency is null but others survive."""
        mock_urgency = MagicMock(spec=UrgencyEngine)
        mock_urgency.score_urgency.side_effect = RuntimeError("Urgency scoring rule crashed")

        engine = InferenceEngine(urgency_engine=mock_urgency)
        res = engine.analyze("Flooding near Rasulgarh", report_id="rep-fail-urg")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["urgency"]["label"] is None
        assert res["urgency"]["confidence"] is None
        assert res["incident_type"]["label"] is not None
        assert any("Component 'urgency' failed" in w for w in res["warnings"])

    def test_23_embedding_failure_isolation_no_fabricated_reference(self, canonical_schema: dict) -> None:
        """When embedding fails, embedding_reference is null (never fabricated!)."""
        mock_embedder = MagicMock(spec=SentenceTransformerEmbedder)
        mock_embedder.encode_single.side_effect = RuntimeError("CUDA OOM / model loading error")

        engine = InferenceEngine(embedder=mock_embedder)
        res = engine.analyze("Fire on Main Street", report_id="rep-fail-emb")

        jsonschema.validate(instance=res, schema=canonical_schema)
        # MUST be None / null, NOT a fabricated string
        assert res["embedding_reference"] is None
        assert "embedding" not in res
        # Other components survive completely
        assert res["incident_type"]["label"] is not None
        assert res["urgency"]["label"] is not None
        assert any("Component 'embeddings' failed" in w for w in res["warnings"])

    def test_24_confidence_engine_failure_isolation(self, canonical_schema: dict) -> None:
        """When confidence engine fails, pipeline falls back safely to NEEDS_REVIEW without fake score."""
        mock_conf = MagicMock(spec=ConfidenceEngine)
        mock_conf.calculate.side_effect = ZeroDivisionError("Math error in confidence")

        engine = InferenceEngine(confidence_engine=mock_conf)
        res = engine.analyze("Flooding on highway", report_id="rep-fail-conf")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["processing_status"] == "NEEDS_REVIEW"
        assert any("Component 'confidence_engine' failed" in w for w in res["warnings"])

    def test_25_complete_infrastructure_failure_status_failed(self, canonical_schema: dict) -> None:
        """When all inference components fail, processing_status degrades strictly to FAILED."""
        mock_classifier = MagicMock(spec=IncidentClassifier)
        mock_classifier.predict.side_effect = RuntimeError("fail")

        mock_loc = MagicMock(spec=LocationEntityExtractor)
        mock_loc.extract.side_effect = RuntimeError("fail")

        mock_people = MagicMock(spec=PeopleRiskExtractor)
        mock_people.extract.side_effect = RuntimeError("fail")

        mock_resp = MagicMock(spec=RequiredResponseExtractor)
        mock_resp.extract.side_effect = RuntimeError("fail")

        mock_urg = MagicMock(spec=UrgencyEngine)
        mock_urg.score_urgency.side_effect = RuntimeError("fail")

        mock_emb = MagicMock(spec=SentenceTransformerEmbedder)
        mock_emb.encode_single.side_effect = RuntimeError("fail")

        engine = InferenceEngine(
            classifier=mock_classifier,
            location_extractor=mock_loc,
            people_extractor=mock_people,
            response_extractor=mock_resp,
            urgency_engine=mock_urg,
            embedder=mock_emb,
        )
        res = engine.analyze("Some emergency dispatch text", report_id="rep-all-failed")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["processing_status"] == "FAILED"
        assert res["incident_type"]["label"] is None
        assert res["urgency"]["label"] is None
        assert res["location"]["text"] is None
        assert res["people_at_risk"]["count"] is None
        assert res["required_response"] == []
        assert res["embedding_reference"] is None

    def test_26_schema_validation_rejection(self) -> None:
        """SchemaValidator rejects invalid output before it escapes."""
        validator = SchemaValidator()
        invalid_payload = {
            "report_id": "rep-bad",
            # Missing model_version and required fields
            "incident_type": {"label": "INVALID_LABEL", "confidence": 1.5},
        }
        with pytest.raises(MLSchemaValidationError, match="failed schema validation"):
            validator.validate(invalid_payload)

    def test_27_low_confidence_triggers_needs_review(self, canonical_schema: dict) -> None:
        """Low component confidence triggers NEEDS_REVIEW status."""
        mock_classifier = MagicMock(spec=IncidentClassifier)
        mock_classifier.predict.return_value = ClassificationResult(
            label="OTHER_GENERAL_INCIDENT",
            confidence=0.35,  # Low confidence
            method="keyword",
        )

        mock_urgency = MagicMock(spec=UrgencyEngine)
        mock_urgency.score_urgency.return_value = UrgencyResult(
            score=20.0,
            label="LOW",
            confidence=0.40,  # Low confidence
            breakdown=UrgencyBreakdown(
                life_safety=ComponentScore(name="life_safety", score=0, weight=0.5, weighted_contribution=0),
                hazard_velocity=ComponentScore(name="hazard_velocity", score=0, weight=0.3, weighted_contribution=0),
                vulnerability=ComponentScore(name="vulnerability", score=0, weight=0.2, weighted_contribution=0),
            ),
        )

        mock_loc = MagicMock(spec=LocationEntityExtractor)
        mock_loc.extract.return_value = LocationEntityResult(
            location=LocationPrediction(text="Somewhere", confidence=0.30),
            entities=[],
        )

        engine = InferenceEngine(
            classifier=mock_classifier,
            urgency_engine=mock_urgency,
            location_extractor=mock_loc,
        )
        res = engine.analyze("Vague unconfirmed dispatch", report_id="rep-low-conf")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["processing_status"] == "NEEDS_REVIEW"


# ==============================================================================
# 5. Realistic Emergency Scenarios (Step 26)
# ==============================================================================


class TestRealisticScenarios:
    """Tests realistic emergency dispatches exercising multiple components."""

    def test_28_structural_collapse_with_trapped_and_injured(
        self, engine: InferenceEngine, canonical_schema: dict
    ) -> None:
        """
        Scenario: HELP! Five people are trapped inside a collapsing building
        near Rasulgarh flyover. One person is badly injured and smoke is spreading.
        """
        text = (
            "HELP! Five people are trapped inside a collapsing building near "
            "Rasulgarh flyover. One person is badly injured and smoke is spreading."
        )
        res = engine.analyze(text, report_id="rep-real-01")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["people_at_risk"]["count"] == 5
        assert res["urgency"]["label"] in ("CRITICAL", "HIGH")
        assert "Rasulgarh" in (res["location"]["text"] or "")
        resp_types = [r["type"] for r in res["required_response"]]
        assert "SEARCH_AND_RESCUE" in resp_types
        assert res["embedding_reference"] == "emb-rep-real-01"

    def test_29_flash_flood_rapidly_rising(self, engine: InferenceEngine, canonical_schema: dict) -> None:
        """
        Scenario: Flash flood waters are rapidly rising around Patia underpass.
        Several vehicles are stranded.
        """
        text = "Flash flood waters are rapidly rising around Patia underpass. Several vehicles are stranded."
        res = engine.analyze(text, report_id="rep-real-02")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["incident_type"]["label"] == "FLOOD_FLASH_FLOOD"
        assert "Patia" in (res["location"]["text"] or "")
        # Qualitative count: "several vehicles" must NOT fabricate a number for people
        assert res["people_at_risk"]["count"] is None
        assert res["location"]["latitude"] is None


# ==============================================================================
# 6. Adversarial End-to-End Cases (Step 27)
# ==============================================================================


class TestAdversarialEndToEndCases:
    """Verifies that targeted negation and signal boundaries survive end-to-end orchestration."""

    def test_30_adversarial_trapped_preserved_despite_negated_injuries(
        self, engine: InferenceEngine, canonical_schema: dict
    ) -> None:
        """
        Adversarial Case 1:
        'No one is injured, but 5 people are trapped inside the collapsing building.'
        Must preserve: trapped, people count 5, collapse, high/critical urgency.
        """
        text = "No one is injured, but 5 people are trapped inside the collapsing building."
        res = engine.analyze(text, report_id="rep-adv-01")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["people_at_risk"]["count"] == 5
        assert res["incident_type"]["label"] == "STRUCTURAL_COLLAPSE"
        assert res["urgency"]["label"] in ("CRITICAL", "HIGH")
        resp_types = [r["type"] for r in res["required_response"]]
        assert "SEARCH_AND_RESCUE" in resp_types

    def test_31_adversarial_negated_trapped_with_active_collapse(
        self, engine: InferenceEngine, canonical_schema: dict
    ) -> None:
        """
        Adversarial Case 2:
        'No one is trapped; the building is still collapsing.'
        Must preserve: collapse, hazard velocity. Must NOT extract trapped count.
        """
        text = "No one is trapped; the building is still collapsing."
        res = engine.analyze(text, report_id="rep-adv-02")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["incident_type"]["label"] == "STRUCTURAL_COLLAPSE"
        assert res["people_at_risk"]["count"] is None

    def test_32_adversarial_all_safe_low_urgency(
        self, engine: InferenceEngine, canonical_schema: dict
    ) -> None:
        """
        Adversarial Case 3:
        'Everyone is safe and accounted for; no current danger.'
        Must produce low/controlled urgency.
        """
        text = "Everyone is safe and accounted for; no current danger."
        res = engine.analyze(text, report_id="rep-adv-03")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["urgency"]["label"] == "LOW"
        assert res["people_at_risk"]["count"] is None

    def test_33_adversarial_safe_people_with_active_collapse(
        self, engine: InferenceEngine, canonical_schema: dict
    ) -> None:
        """
        Adversarial Case 4:
        'Everyone is safe and accounted for, but the building is collapsing.'
        Must preserve active collapse hazard.
        """
        text = "Everyone is safe and accounted for, but the building is collapsing."
        res = engine.analyze(text, report_id="rep-adv-04")

        jsonschema.validate(instance=res, schema=canonical_schema)
        assert res["incident_type"]["label"] == "STRUCTURAL_COLLAPSE"
        assert res["people_at_risk"]["count"] is None

    def test_34_adversarial_no_injuries_live_power_lines(
        self, engine: InferenceEngine, canonical_schema: dict
    ) -> None:
        """
        Adversarial Case 5:
        'No injuries reported; live power lines are down and sparking.'
        Must preserve active electrical hazard (PUBLIC_WORKS_UTILITY) and negate casualty counts.
        """
        text = "No injuries reported; live power lines are down and sparking."
        res = engine.analyze(text, report_id="rep-adv-05")

        jsonschema.validate(instance=res, schema=canonical_schema)
        # People count is strictly None (negated injuries)
        assert res["people_at_risk"]["count"] is None
        # Must preserve active electrical hazard response routing
        resp_types = [r["type"] for r in res["required_response"]]
        assert "PUBLIC_WORKS_UTILITY" in resp_types


# ==============================================================================
# 7. Privacy & Logging Standards (Step 22)
# ==============================================================================


class TestPrivacyAndLogging:
    """Verifies that citizen distress text and embeddings never leak into logs."""

    def test_35_raw_report_text_never_in_logs(self, engine: InferenceEngine) -> None:
        """Verifies raw text is not present in log message or extra metadata."""
        sensitive_text = "Citizen John Doe is bleeding heavily at flat 402 with secret code 1234"
        with patch.object(engine.logger, "info") as mock_info:
            engine.analyze(sensitive_text, report_id="rep-priv-01")

            # Check all log calls made by pipeline logger
            for call_args in mock_info.call_args_list:
                msg = str(call_args.args[0] if call_args.args else "")
                kwargs = call_args.kwargs
                extra = kwargs.get("extra", {})

                assert sensitive_text not in msg
                assert "John Doe" not in msg
                # Extra context must not contain raw text
                for k, v in extra.items():
                    assert sensitive_text not in str(v)
                    assert "John Doe" not in str(v)
