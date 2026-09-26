"""
Karen's Ear — ML Evaluation Harness Integration & Unit Test Suite.

Feature 11 — Quantitative Evaluation Layer.
Tests:
- ClassificationEvaluator with mock and live inference pipeline
- EntityEvaluator matching methodologies (location spans, joint, span-only)
- UrgencyEvaluator 4x4 matrix, critical recall, and critical false negative rate
- EmbeddingEvaluator ROC-AUC, threshold metrics, and configurable threshold
- PerformanceEvaluator cold-start, latency distribution, and memory reporting
- MLEvaluationHarness end-to-end evaluation orchestration and report saving
- Machine-readable JSON report schema compliance
- Human-readable summary output formatting
- CLI argument parsing (python -m ml.evaluation)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ml.config import CANONICAL_INCIDENT_TYPES, CANONICAL_URGENCY_LEVELS
from ml.evaluation import (
    ClassificationClassMetrics,
    ClassificationEvaluationResult,
    ClassificationEvaluator,
    ColdStartMemoryMetrics,
    ColdStartMetrics,
    EmbeddingEvaluationResult,
    EmbeddingEvaluator,
    EntityEvaluationResult,
    EntityEvaluator,
    EvaluationReport,
    MLEvaluationHarness,
    PerformanceEvaluationResult,
    PerformanceEvaluator,
    SpanMetrics,
    UrgencyEvaluationResult,
    UrgencyEvaluator,
)
from ml.evaluation.__main__ import parse_args
from ml.pipeline import inference_engine
from ml.pipeline.inference_engine import InferenceEngine
from ml.tests.fixtures.embedding_benchmark import CURATED_SEMANTIC_PAIRS, SemanticPair
from ml.tests.fixtures.incident_benchmark import INCIDENT_BENCHMARK_DATASET, BenchmarkItem
from ml.tests.fixtures.ner_benchmark import (
    NER_BENCHMARK_DATASET,
    ExpectedEntity,
    NERBenchmarkSample,
)
from ml.tests.fixtures.urgency_benchmark import (
    CURATED_URGENCY_BENCHMARK,
    UrgencyBenchmarkSample,
)


# ==============================================================================
# 1. Classification Evaluator Tests
# ==============================================================================
def test_classification_evaluator_with_mock_engine():
    """ClassificationEvaluator correctly compiles 9-class metrics from mock engine."""
    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.analyze.side_effect = [
        {"incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.95}},
        {"incident_type": {"label": "FIRE_WILDFIRE_EXPLOSION", "confidence": 0.90}},
        {"incident_type": {"label": "OTHER_GENERAL_INCIDENT", "confidence": 0.60}},  # error on 3rd
    ]

    mini_dataset = (
        BenchmarkItem(
            id="f1",
            text="Flood waters rising.",
            expected_label="FLOOD_FLASH_FLOOD",
            source="test",
            difficulty="straightforward",
        ),
        BenchmarkItem(
            id="f2",
            text="Wildfire advancing.",
            expected_label="FIRE_WILDFIRE_EXPLOSION",
            source="test",
            difficulty="straightforward",
        ),
        BenchmarkItem(
            id="f3",
            text="Earthquake tremors felt.",
            expected_label="EARTHQUAKE_LANDSLIDE",
            source="test",
            difficulty="straightforward",
        ),
    )

    evaluator = ClassificationEvaluator(engine=mock_engine)
    res = evaluator.evaluate(dataset=mini_dataset, fixture_name="mini_incident_test")

    assert isinstance(res, ClassificationEvaluationResult)
    assert res.sample_count == 3
    assert res.accuracy == 0.6667
    assert len(res.canonical_labels) == 9
    assert "FLOOD_FLASH_FLOOD" in res.per_class
    assert res.per_class["FLOOD_FLASH_FLOOD"].tp == 1
    assert res.per_class["FIRE_WILDFIRE_EXPLOSION"].tp == 1
    assert res.per_class["EARTHQUAKE_LANDSLIDE"].fn == 1
    assert len(res.misclassifications) == 1
    assert res.misclassifications[0]["id"] == "f3"

    # Verify dict conversion
    d = res.to_dict()
    assert d["fixture_name"] == "mini_incident_test"
    assert d["sample_count"] == 3


# ==============================================================================
# 2. Entity Evaluator Tests
# ==============================================================================
def test_entity_evaluator_with_mock_engine():
    """EntityEvaluator evaluates location spans, joint entities, and span-only matches."""
    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.analyze.side_effect = [
        # Sample 1: Perfect location and entity match
        {
            "location": {"text": "Rasulgarh Flyover", "precision": "approximate", "confidence": 0.90},
            "entities": [{"text": "bus", "type": "VEHICLE"}, {"text": "Rasulgarh Flyover", "type": "LOCATION"}],
        },
        # Sample 2: Negative sample with no location and no entities
        {
            "location": {"text": None, "precision": "unknown", "confidence": None},
            "entities": [],
        },
    ]

    mini_dataset = (
        NERBenchmarkSample(
            sample_id="b1",
            text="Trapped inside bus near Rasulgarh flyover.",
            expected_location="Rasulgarh flyover",
            expected_precision="approximate",
            expected_entities=(
                ExpectedEntity("bus", "VEHICLE"),
                ExpectedEntity("Rasulgarh flyover", "LOCATION"),
            ),
            is_negative=False,
        ),
        NERBenchmarkSample(
            sample_id="b2",
            text="Room 204 has collapsed.",
            expected_location=None,
            expected_precision="unknown",
            expected_entities=(),
            is_negative=True,
        ),
    )

    evaluator = EntityEvaluator(engine=mock_engine)
    res = evaluator.evaluate(dataset=mini_dataset, fixture_name="mini_ner_test")

    assert isinstance(res, EntityEvaluationResult)
    assert res.sample_count == 2
    assert res.positive_samples == 1
    assert res.negative_samples == 1

    # Location span metrics
    loc_m = res.location_span_metrics
    assert loc_m.tp == 1
    assert loc_m.tn == 1
    assert loc_m.fp == 0
    assert loc_m.fn == 0
    assert loc_m.precision == 1.0
    assert loc_m.recall == 1.0

    # Joint entity metrics
    joint_m = res.joint_entity_metrics
    assert joint_m.tp == 2
    assert joint_m.fp == 0
    assert joint_m.fn == 0
    assert joint_m.precision == 1.0
    assert joint_m.recall == 1.0

    # Per-type breakdown
    assert "VEHICLE" in res.per_entity_type_metrics
    assert res.per_entity_type_metrics["VEHICLE"].tp == 1


# ==============================================================================
# 3. Urgency Evaluator Tests
# ==============================================================================
def test_urgency_evaluator_with_mock_engine():
    """UrgencyEvaluator computes 4x4 confusion matrix, critical recall, and critical FNR."""
    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.analyze.side_effect = [
        {"urgency": {"label": "CRITICAL", "confidence": 0.95}},
        {"urgency": {"label": "HIGH", "confidence": 0.85}},
        {"urgency": {"label": "MEDIUM", "confidence": 0.70}},
        {"urgency": {"label": "LOW", "confidence": 0.50}},
    ]

    mini_dataset = (
        UrgencyBenchmarkSample(
            id="u1",
            text="Victims trapped under building rubble.",
            expected_reference_label="CRITICAL",
            scenario_category="critical",
            difficulty="straightforward",
        ),
        UrgencyBenchmarkSample(
            id="u2",
            text="Structure fire on 2nd floor.",
            expected_reference_label="HIGH",
            scenario_category="high",
            difficulty="straightforward",
        ),
        UrgencyBenchmarkSample(
            id="u3",
            text="Minor street waterlogging.",
            expected_reference_label="MEDIUM",
            scenario_category="medium",
            difficulty="straightforward",
        ),
        UrgencyBenchmarkSample(
            id="u4",
            text="Trash can smoldering.",
            expected_reference_label="LOW",
            scenario_category="low",
            difficulty="straightforward",
        ),
    )

    evaluator = UrgencyEvaluator(engine=mock_engine)
    res = evaluator.evaluate(dataset=mini_dataset, fixture_name="mini_urgency_test")

    assert isinstance(res, UrgencyEvaluationResult)
    assert res.sample_count == 4
    assert res.accuracy == 1.0
    assert res.critical_recall == 1.0
    assert res.critical_false_negative_rate == 0.0
    assert res.per_tier["CRITICAL"].tp == 1
    assert res.per_tier["HIGH"].tp == 1
    assert res.per_tier["MEDIUM"].tp == 1
    assert res.per_tier["LOW"].tp == 1
    assert res.confusion_matrix["CRITICAL"]["CRITICAL"] == 1
    assert "CrisiText does NOT provide operational urgency labels" in res.notice


def test_urgency_evaluator_critical_false_negative():
    """UrgencyEvaluator detects critical false negative (misclassifying CRITICAL as HIGH)."""
    mock_engine = MagicMock(spec=InferenceEngine)
    # Both actual CRITICAL: one predicted CRITICAL, one predicted HIGH
    mock_engine.analyze.side_effect = [
        {"urgency": {"label": "CRITICAL", "confidence": 0.90}},
        {"urgency": {"label": "HIGH", "confidence": 0.75}},  # FN!
    ]

    mini_dataset = (
        UrgencyBenchmarkSample(
            id="u1",
            text="Report 1",
            expected_reference_label="CRITICAL",
            scenario_category="critical",
            difficulty="straightforward",
        ),
        UrgencyBenchmarkSample(
            id="u2",
            text="Report 2",
            expected_reference_label="CRITICAL",
            scenario_category="critical",
            difficulty="straightforward",
        ),
    )

    evaluator = UrgencyEvaluator(engine=mock_engine)
    res = evaluator.evaluate(dataset=mini_dataset)

    assert res.per_tier["CRITICAL"].tp == 1
    assert res.per_tier["CRITICAL"].fn == 1
    assert res.critical_recall == 0.5
    assert res.critical_false_negative_rate == 0.5
    assert len(res.mismatches) == 1


# ==============================================================================
# 4. Embedding Evaluator Tests
# ==============================================================================
def test_embedding_evaluator_with_mock_embedder():
    """EmbeddingEvaluator evaluates semantic pairs, ROC-AUC, and threshold metrics."""
    mock_embedder = MagicMock()
    mock_embedder.config.embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    mock_embedder.config.embedding_dimension = 384
    mock_embedder.encode_numpy.return_value = [0.1] * 384  # dummy normalized

    # Mock similarity scores: pair 0 (high) -> 0.90, pair 1 (low) -> 0.30
    mock_embedder.similarity.side_effect = [
        1.0,  # self similarity check
        0.90, 0.90,  # pair 0: sim(a,b), sim(b,a)
        0.30, 0.30,  # pair 1: sim(a,b), sim(b,a)
    ]

    pairs = (
        SemanticPair(
            pair_id="p1",
            text_a="Warehouse on fire",
            text_b="Fire inside warehouse",
            category="high_similarity",
            domain="fire",
            description="Paraphrased fire",
        ),
        SemanticPair(
            pair_id="p2",
            text_a="Warehouse on fire",
            text_b="Hospital heart patient",
            category="lower_similarity",
            domain="cross_domain",
            description="Distinct crisis",
        ),
    )

    evaluator = EmbeddingEvaluator(embedder=mock_embedder, default_threshold=0.75)
    res = evaluator.evaluate(pairs=pairs, self_texts=["Warehouse on fire"], threshold=0.75)

    assert isinstance(res, EmbeddingEvaluationResult)
    assert res.total_pairs_evaluated == 2
    assert res.positive_pair_count == 1
    assert res.negative_pair_count == 1
    assert res.roc_auc == 1.0  # Perfect separation (0.90 > 0.30)
    assert res.metrics_at_threshold.tp == 1
    assert res.metrics_at_threshold.tn == 1
    assert res.metrics_at_threshold.precision == 1.0
    assert res.metrics_at_threshold.recall == 1.0
    assert res.configured_threshold == 0.75


# ==============================================================================
# 5. Performance Evaluator Tests
# ==============================================================================
def test_performance_evaluator_mock_execution():
    """PerformanceEvaluator measures cold-start and warm latency distribution."""
    mock_engine = MagicMock()
    mock_engine.config = MagicMock()
    mock_engine.config.model_version = "1.0.0"
    mock_engine.config.embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    mock_engine.config.device = "cpu"
    mock_engine.analyze.return_value = {"status": "SUCCESS"}

    evaluator = PerformanceEvaluator(engine=mock_engine)
    res = evaluator.evaluate(
        samples=["Sample report text A", "Sample report text B"],
        warm_trials=5,
        use_subprocess_cold_start=False,
    )

    assert isinstance(res, PerformanceEvaluationResult)
    assert res.warm_latency.sample_count == 5
    assert res.warm_latency.p50_ms >= 0.0
    assert res.warm_latency.p95_ms >= 0.0
    assert res.environment.python_version != ""
    assert res.environment.operating_system != ""
    assert "RSS" in res.memory.methodology
    assert res.cold_start.unit == "milliseconds"


# ==============================================================================
# 6. Full MLEvaluationHarness Integration Test
# ==============================================================================
def test_evaluation_harness_integration_subset(tmp_path: Path):
    """
    Integration test proving MLEvaluationHarness executes across benchmark fixtures
    with the real inference pipeline and exports valid JSON.
    """
    harness = MLEvaluationHarness(
        engine=inference_engine,
        embedding_threshold=0.75,
        performance_samples=2,
    )

    # Use small subset of fixtures to test end-to-end execution quickly
    mini_incident = INCIDENT_BENCHMARK_DATASET[:2]
    mini_ner = NER_BENCHMARK_DATASET[:2]
    mini_urgency = CURATED_URGENCY_BENCHMARK[:2]
    mini_pairs = CURATED_SEMANTIC_PAIRS[:2]

    harness.classification_evaluator.evaluate = lambda **kw: ClassificationEvaluator(
        engine=inference_engine
    ).evaluate(dataset=mini_incident)
    harness.entity_evaluator.evaluate = lambda **kw: EntityEvaluator(
        engine=inference_engine
    ).evaluate(dataset=mini_ner)
    harness.urgency_evaluator.evaluate = lambda **kw: UrgencyEvaluator(
        engine=inference_engine
    ).evaluate(dataset=mini_urgency)
    harness.embedding_evaluator.evaluate = lambda **kw: EmbeddingEvaluator(
        engine=inference_engine
    ).evaluate(pairs=mini_pairs, self_texts=["Fire reported inside warehouse"])
    harness.performance_evaluator.evaluate = lambda **kw: PerformanceEvaluator(
        engine=inference_engine
    ).evaluate(samples=["Minor street flooding near market square"], warm_trials=2, use_subprocess_cold_start=False)

    out_file = tmp_path / "integration_ml_evaluation.json"
    report = harness.run_evaluation(include_performance=True, save_path=out_file)

    assert isinstance(report, EvaluationReport)
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["evaluation_version"] == "1.0.0"
    assert "classification" in data
    assert "entity_extraction" in data
    assert "urgency" in data
    assert "embeddings" in data
    assert "performance" in data
    assert "findings" in data
    assert len(data["findings"]) > 0

    # Verify summary string formats cleanly
    summary_text = report.format_human_readable_summary()
    assert "Karen's Ear — Machine Learning Evaluation Report" in summary_text


# ==============================================================================
# 7. CLI Argument Parsing Tests
# ==============================================================================
def test_cli_argument_parsing():
    """Validates CLI arguments for python -m ml.evaluation."""
    # Defaults
    args_default = parse_args([])
    assert args_default.threshold == 0.75
    assert "ml_evaluation.json" in args_default.output
    assert args_default.performance_samples == 25
    assert args_default.warmup_samples == 2
    assert args_default.skip_performance is False
    assert args_default.quiet is False

    # Custom options
    args_custom = parse_args([
        "--threshold", "0.82",
        "--output", "custom_results/report.json",
        "--performance-samples", "50",
        "--warmup-samples", "4",
        "--skip-performance",
        "--quiet",
    ])
    assert args_custom.threshold == 0.82
    assert args_custom.output == "custom_results/report.json"
    assert args_custom.performance_samples == 50
    assert args_custom.warmup_samples == 4
    assert args_custom.skip_performance is True
    assert args_custom.quiet is True


# ==============================================================================
# 8. Cold-Start Measurement Integrity & Methodology Tests
# ==============================================================================
def test_cold_start_executes_in_isolated_subprocess():
    """Proves that cold-start measurement executes in an isolated fresh Python process."""
    evaluator = PerformanceEvaluator(engine=inference_engine)
    cold_metrics = evaluator._run_cold_start_subprocess("Power lines down on Elm Street.")

    assert isinstance(cold_metrics, ColdStartMetrics)
    assert cold_metrics.methodology == "fresh subprocess first full inference"
    assert cold_metrics.subprocess_pid is not None
    assert cold_metrics.subprocess_pid != os.getpid(), "Subprocess PID must differ from parent process PID"
    assert cold_metrics.latency_ms > 0.0
    assert cold_metrics.unit == "milliseconds"
    assert cold_metrics.memory.initial_rss_mb > 0.0
    assert cold_metrics.memory.post_inference_rss_mb >= cold_metrics.memory.initial_rss_mb


def test_parent_process_preloading_does_not_contaminate_cold_start():
    """Proves embedding model loading in parent process cannot contaminate the cold-start measurement."""
    # Preload models in the parent process via full inference
    _ = inference_engine.analyze("Test warming query in parent process")

    import psutil
    parent_rss_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    assert parent_rss_mb > 100.0, "Parent process should have significant memory with models loaded"

    evaluator = PerformanceEvaluator(engine=inference_engine)
    cold_metrics = evaluator._run_cold_start_subprocess("Vehicle accident blocking traffic lane.")

    # The fresh subprocess MUST start with a bare process RSS, completely unaffected by parent process memory
    assert cold_metrics.memory.initial_rss_mb < 120.0, (
        f"Subprocess initial RSS ({cold_metrics.memory.initial_rss_mb} MB) was contaminated by parent process ({parent_rss_mb} MB)"
    )
    assert cold_metrics.memory.rss_delta_mb > 50.0, "Subprocess should experience meaningful memory growth from loading models"


def test_cold_start_result_explicit_units():
    """Proves cold-start result contains explicit units."""
    evaluator = PerformanceEvaluator(engine=inference_engine)
    res = evaluator.evaluate(
        samples=["Tree fallen on road."],
        warm_trials=2,
        warmup_trials=0,
        use_subprocess_cold_start=False,
    )
    assert res.cold_start.unit == "milliseconds"
    assert res.warm_latency.unit == "milliseconds"

    res_dict = res.to_dict()
    assert res_dict["cold_start"]["unit"] == "milliseconds"
    assert isinstance(res_dict["cold_start"]["latency_ms"], (int, float))
    assert res_dict["cold_start"]["latency_ms"] >= 0.0


def test_memory_result_explicit_measurement_methodology():
    """Proves memory result contains explicit measurement methodology and limitations."""
    evaluator = PerformanceEvaluator(engine=inference_engine)
    res = evaluator.evaluate(
        samples=["Gas leak near school."],
        warm_trials=2,
        warmup_trials=0,
        use_subprocess_cold_start=False,
    )
    mem = res.cold_start.memory
    assert "Resident Set Size (RSS)" in mem.methodology
    assert "psutil" in mem.methodology
    assert "virtual memory pages resident in RAM" in mem.limitation_notice
    assert "isolated model tensor" in mem.limitation_notice or "isolated neural-network parameter" in mem.limitation_notice
    assert mem.initial_rss_mb >= 0.0
    assert mem.post_inference_rss_mb >= 0.0
    assert mem.rss_delta_mb >= 0.0


def test_warm_latency_remains_separate_from_cold_latency():
    """Proves warm latency remains separate from cold latency and percentiles are isolated."""
    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.config = MagicMock()
    mock_engine.config.model_version = "1.0.0"
    mock_engine.analyze.side_effect = [
        {"status": "COLD"},
        {"status": "WARMUP_1"},
        {"status": "WARMUP_2"},
        {"status": "WARM_1"},
        {"status": "WARM_2"},
        {"status": "WARM_3"},
    ]
    evaluator = PerformanceEvaluator(engine=mock_engine)
    res = evaluator.evaluate(
        samples=["Sample 1", "Sample 2"],
        warm_trials=3,
        warmup_trials=2,
        use_subprocess_cold_start=False,
    )
    # Warm latency only contains the 3 warm samples
    assert res.warm_latency.timed_samples == 3
    assert res.warm_latency.warmup_samples == 2
    assert mock_engine.analyze.call_count == 6  # 1 cold + 2 warmup + 3 warm
    assert res.cold_start.latency_ms >= 0.0



def test_entity_matching_methodology_naming_accuracy():
    """Proves entity matching methodology name accurately describes the implementation."""
    mock_engine = MagicMock(spec=InferenceEngine)
    # Predict "Rasulgarh" when expected is "Rasulgarh Flyover"
    mock_engine.analyze.return_value = {
        "location": {"text": "Rasulgarh", "precision": "approximate", "confidence": 0.85},
        "entities": [],
    }

    sample = NERBenchmarkSample(
        sample_id="test-subspan-01",
        text="Accident on Rasulgarh Flyover",
        expected_location="Rasulgarh Flyover",
        expected_precision="approximate",
        expected_entities=(),
        is_negative=False,
    )

    evaluator = EntityEvaluator(engine=mock_engine)
    res = evaluator.evaluate(dataset=[sample])

    # 1. Under "normalized sub-span containment", "Rasulgarh" matches "Rasulgarh Flyover"
    assert res.location_subspan_metrics.matching_rule == "normalized sub-span containment"
    assert res.location_subspan_metrics.tp == 1
    assert res.location_subspan_metrics.fn == 0
    assert res.location_subspan_metrics.f1 == 1.0

    # 2. Under "exact_normalized", "Rasulgarh" != "Rasulgarh Flyover" -> MISMATCH!
    assert res.location_exact_metrics.matching_rule == "exact_normalized"
    assert res.location_exact_metrics.tp == 0
    assert res.location_exact_metrics.fn == 1
    assert res.location_exact_metrics.f1 == 0.0


# ==============================================================================
# 9. Warm-Up Methodology & Outlier Integrity Tests
# ==============================================================================
def test_warmup_inference_happens_before_timing():
    """Proves that untimed warm-up calls execute prior to starting the timed warm-latency loop."""
    call_log: list[str] = []

    def mock_analyze(text: str, report_id: str | None = None) -> dict[str, Any]:
        call_log.append(report_id or "unknown")
        return {"status": "SUCCESS"}

    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.config = MagicMock()
    mock_engine.config.model_version = "1.0.0"
    mock_engine.analyze.side_effect = mock_analyze

    evaluator = PerformanceEvaluator(engine=mock_engine)
    res = evaluator.evaluate(
        samples=["Sample text"],
        warm_trials=3,
        warmup_trials=2,
        use_subprocess_cold_start=False,
    )

    # Call sequence must be:
    # 1. cold start: "perf-cold-01"
    # 2. warm-up: "perf-warmup-000", "perf-warmup-001"
    # 3. timed warm: "perf-warm-000", "perf-warm-001", "perf-warm-002"
    assert call_log == [
        "perf-cold-01",
        "perf-warmup-000",
        "perf-warmup-001",
        "perf-warm-000",
        "perf-warm-001",
        "perf-warm-002",
    ]
    warmup_indices = [i for i, cid in enumerate(call_log) if cid.startswith("perf-warmup-")]
    timed_indices = [i for i, cid in enumerate(call_log) if cid.startswith("perf-warm-")]
    assert max(warmup_indices) < min(timed_indices), "Untimed warm-up must execute BEFORE timed warm iterations"
    assert res.warm_latency.warmup_samples == 2
    assert res.warm_latency.timed_samples == 3


def test_warmup_samples_excluded_from_timed_latency_statistics():
    """Proves that slow warm-up samples are completely excluded from timed statistics and percentiles."""
    import time

    def mock_analyze(text: str, report_id: str | None = None) -> dict[str, Any]:
        # Simulate a 100ms slow initialization on warmup, and fast 1ms on warm
        if report_id and "warmup" in report_id:
            time.sleep(0.08)
        else:
            time.sleep(0.001)
        return {"status": "SUCCESS"}

    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.config = MagicMock()
    mock_engine.config.model_version = "1.0.0"
    mock_engine.analyze.side_effect = mock_analyze

    evaluator = PerformanceEvaluator(engine=mock_engine)
    res = evaluator.evaluate(
        samples=["Sample text"],
        warm_trials=4,
        warmup_trials=2,
        use_subprocess_cold_start=False,
    )

    # Timed metrics should reflect ~1ms inferences, not the 80ms warm-up
    assert res.warm_latency.warmup_samples == 2
    assert res.warm_latency.timed_samples == 4
    assert res.warm_latency.max_ms < 50.0, f"Warm max_ms ({res.warm_latency.max_ms}) was contaminated by warm-up!"
    assert res.warm_latency.mean_ms < 50.0
    assert res.warm_latency.p99_ms < 50.0


def test_timed_samples_exact_configured_count():
    """Proves timed samples exactly match the configured sample count."""
    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.config = MagicMock()
    mock_engine.config.model_version = "1.0.0"
    mock_engine.analyze.return_value = {"status": "SUCCESS"}

    evaluator = PerformanceEvaluator(engine=mock_engine)
    for requested_count in [1, 7, 13]:
        res = evaluator.evaluate(
            samples=["Sample 1", "Sample 2"],
            warm_trials=requested_count,
            warmup_trials=2,
            use_subprocess_cold_start=False,
        )
        assert res.warm_latency.timed_samples == requested_count
        assert res.warm_latency.sample_count == requested_count


def test_throughput_calculated_from_timed_warm_samples():
    """Proves throughput is derived purely from timed warm iterations, not contaminated by warm-up."""
    import time

    def mock_analyze(text: str, report_id: str | None = None) -> dict[str, Any]:
        # Heavy delay on warm-up calls
        if report_id and "warmup" in report_id:
            time.sleep(0.08)
        else:
            time.sleep(0.005)
        return {"status": "SUCCESS"}

    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.config = MagicMock()
    mock_engine.config.model_version = "1.0.0"
    mock_engine.analyze.side_effect = mock_analyze

    evaluator = PerformanceEvaluator(engine=mock_engine)
    res = evaluator.evaluate(
        samples=["Sample A"],
        warm_trials=5,
        warmup_trials=2,
        use_subprocess_cold_start=False,
    )

    # From timed samples alone (5ms * 5 = 25ms), throughput is ~5 / 0.025 ≈ 200 items/sec.
    # If warm-up (80ms * 2 = 160ms) was included, throughput would drop below 30 reports/sec.
    assert res.warm_latency.throughput_items_per_sec > 40.0


def test_no_arbitrary_outlier_filtering():
    """Proves no arbitrary outlier filtering is performed and all timed calls are preserved."""
    import time

    def mock_analyze(text: str, report_id: str | None = None) -> dict[str, Any]:
        # One sample is noticeably slower (e.g. 20ms vs 2ms)
        if report_id == "perf-warm-002":
            time.sleep(0.02)
        else:
            time.sleep(0.002)
        return {"status": "SUCCESS"}

    mock_engine = MagicMock(spec=InferenceEngine)
    mock_engine.config = MagicMock()
    mock_engine.config.model_version = "1.0.0"
    mock_engine.analyze.side_effect = mock_analyze

    evaluator = PerformanceEvaluator(engine=mock_engine)
    res = evaluator.evaluate(
        samples=["Sample A", "Sample B", "Sample C"],
        warm_trials=3,
        warmup_trials=1,
        use_subprocess_cold_start=False,
    )

    # Exactly 3 samples must be present
    assert res.warm_latency.timed_samples == 3
    # The slower sample (>= 20ms) must NOT have been discarded as an outlier
    assert res.warm_latency.max_ms >= 18.0

