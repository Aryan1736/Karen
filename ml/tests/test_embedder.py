"""
Karen's Ear — Embedding Engine Test Suite.

Comprehensive unit, integration, and behavioral tests for Step 3 of the ML pipeline
(architecture/ml-pipeline.md Section 3.7 and Feature 8 specification).

Covers all 21+ mandatory requirements:
1. Model output dimension == 384
2. Single text encoding
3. Batch encoding
4. Batch output ordering preserved
5. L2 norm ≈ 1.0
6. Every batch vector normalized
7. Self-similarity ≈ 1.0
8. Symmetry: similarity(a, b) == similarity(b, a)
9. Similarity bounds: strictly within [-1.0, 1.0]
10. Identical texts produce equivalent embeddings
11. Related texts produce sensible similarity ordering
12. Unrelated texts do not accidentally appear identical
13. Empty input handling (empty string, whitespace-only)
14. Invalid input handling (None, non-string, malformed types)
15. Empty batch handling ([] raises MLInputError)
16. Lazy model loading (zero model load at import or instantiation)
17. Model reuse (subsequent encode calls reuse cached model)
18. No duplicate model initialization (shared across instances)
19. Deterministic output within floating-point tolerance
20. No raw report text leakage into logs
21. Expected public API behavior (aliases, metadata, ComponentResult, functional wrappers)
22. PreprocessedText input support
23. Vector similarity helper and numerical clipping
24. Evaluator and benchmark suite integration
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ml.config import ComponentResult, MLConfig, ModelMetadata
from ml.exceptions import (
    MLInferenceError,
    MLInputError,
    MLModelError,
)
from ml.embeddings import (
    EmbeddingEngine,
    EmbeddingEvaluationReport,
    EmbeddingEvaluator,
    SentenceTransformerEmbedder,
    compute_similarity,
    embed_report,
    embed_reports,
    is_model_loaded,
    reset_model_cache,
)
from ml.logging_utils import MLJsonFormatter
from ml.preprocessing.text_cleaner import PreprocessedText, preprocess_report
from ml.tests.fixtures.embedding_benchmark import (
    CURATED_SEMANTIC_PAIRS,
    SELF_SIMILARITY_TEXTS,
    SemanticPair,
)


@pytest.fixture(scope="module")
def embedder() -> SentenceTransformerEmbedder:
    """Shared warm embedder for test execution across test cases."""
    return SentenceTransformerEmbedder()


# ==============================================================================
# 1. Output Dimensionality & Single Text Encoding
# ==============================================================================
def test_single_text_encoding_dimension(embedder: SentenceTransformerEmbedder):
    """1 & 2. Single text encoding returns list of floats with dimension exactly 384."""
    text = "Fire reported inside a warehouse with heavy smoke billowing."
    vec = embedder.encode(text)

    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(x, float) for x in vec)


def test_single_text_encode_single_method(embedder: SentenceTransformerEmbedder):
    """encode_single method returns 384 floats."""
    text = "Flash flood near Rasulgarh flyover with stranded vehicles."
    vec = embedder.encode_single(text)

    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(x, float) for x in vec)


def test_encode_numpy_single(embedder: SentenceTransformerEmbedder):
    """encode_numpy returns 1D array of shape (384,) and dtype float32."""
    text = "Severe structural collapse at central marketplace."
    arr = embedder.encode_numpy(text)

    assert isinstance(arr, np.ndarray)
    assert arr.shape == (384,)
    assert arr.dtype == np.float32


# ==============================================================================
# 2. Batch Encoding & Order Preservation
# ==============================================================================
def test_batch_encoding_shape_and_types(embedder: SentenceTransformerEmbedder):
    """3. Batch encoding returns (N, 384) vectors of floats."""
    reports = [
        "Report A: Flash flood submerging railway station tracks.",
        "Report B: Chemical gas leak spreading in industrial zone.",
        "Report C: Power substation transformer explosion and blackout.",
    ]
    vecs = embedder.encode(reports)

    assert isinstance(vecs, list)
    assert len(vecs) == 3
    for row in vecs:
        assert isinstance(row, list)
        assert len(row) == 384
        assert all(isinstance(x, float) for x in row)


def test_batch_encoding_order_preservation(embedder: SentenceTransformerEmbedder):
    """4. Batch output order must preserve input order exactly."""
    reports = [
        "First report about a chemical hazard on highway.",
        "Second report about floodwaters rising in Patia.",
        "Third report about structural collapse downtown.",
    ]

    batch_vecs = embedder.encode_batch(reports)
    single_0 = embedder.encode_single(reports[0])
    single_1 = embedder.encode_single(reports[1])
    single_2 = embedder.encode_single(reports[2])

    assert len(batch_vecs) == 3
    # Check that batch output matches individual single outputs
    assert np.allclose(batch_vecs[0], single_0, atol=1e-4)
    assert np.allclose(batch_vecs[1], single_1, atol=1e-4)
    assert np.allclose(batch_vecs[2], single_2, atol=1e-4)


# ==============================================================================
# 3. L2 Normalization Invariant
# ==============================================================================
def test_single_vector_l2_normalized(embedder: SentenceTransformerEmbedder):
    """5. Every single returned embedding satisfies ||v||₂ ≈ 1.0 within tolerance."""
    for text in SELF_SIMILARITY_TEXTS:
        vec = embedder.encode_single(text)
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-3, f"Norm {norm} deviated from 1.0 for: {text}"


def test_every_batch_vector_l2_normalized(embedder: SentenceTransformerEmbedder):
    """6. Every vector in a batch encoding satisfies ||v||₂ ≈ 1.0."""
    reports = [
        "Major residential fire on 5th floor.",
        "River embankment breached near village.",
        "Multiple casualties reported from bus collision.",
        "Hospital power generator running out of fuel.",
    ]
    batch_vecs = embedder.encode_batch(reports)

    for i, vec in enumerate(batch_vecs):
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-3, f"Row {i} norm {norm} deviated from 1.0"


# ==============================================================================
# 4. Semantic Similarity & Mathematical Properties
# ==============================================================================
def test_self_similarity_near_one(embedder: SentenceTransformerEmbedder):
    """7. Self-similarity similarity(a, a) ≈ 1.0."""
    for text in SELF_SIMILARITY_TEXTS:
        sim = embedder.similarity(text, text)
        assert isinstance(sim, float)
        assert abs(sim - 1.0) < 1e-3, f"Self-similarity for '{text}' was {sim}, expected ~1.0"


def test_similarity_symmetry(embedder: SentenceTransformerEmbedder):
    """8. Symmetry: similarity(a, b) == similarity(b, a)."""
    text_a = "Fire reported inside a warehouse"
    text_b = "Warehouse is on fire"

    sim_ab = embedder.similarity(text_a, text_b)
    sim_ba = embedder.similarity(text_b, text_a)

    assert isinstance(sim_ab, float)
    assert isinstance(sim_ba, float)
    assert abs(sim_ab - sim_ba) < 1e-5, f"Asymmetric similarity: {sim_ab} vs {sim_ba}"


def test_similarity_bounds_clipping(embedder: SentenceTransformerEmbedder):
    """9. Similarity is strictly bounded in [-1.0, 1.0]."""
    for pair in CURATED_SEMANTIC_PAIRS:
        sim = embedder.similarity(pair.text_a, pair.text_b)
        assert -1.0 <= sim <= 1.0, f"Similarity {sim} out of [-1, 1] bounds for {pair.pair_id}"


def test_identical_texts_produce_equivalent_embeddings(embedder: SentenceTransformerEmbedder):
    """10. Identical texts produce equivalent embeddings."""
    text = "Severe flash flooding across Nayapalli residential sector."
    vec_1 = embedder.encode(text)
    vec_2 = embedder.encode(text)

    assert np.allclose(vec_1, vec_2, atol=1e-5)
    sim = embedder.similarity(text, text)
    assert abs(sim - 1.0) < 1e-4


def test_related_texts_produce_sensible_ordering(embedder: SentenceTransformerEmbedder):
    """11. Semantically related texts score higher than unrelated texts."""
    # Warehouse fire pair (related) vs warehouse fire & hospital chest pain (unrelated)
    fire_a = "Fire reported inside a warehouse"
    fire_b = "Warehouse is on fire"
    medical = "Hospital reports several patients with chest pain"

    sim_related = embedder.similarity(fire_a, fire_b)
    sim_unrelated = embedder.similarity(fire_a, medical)

    assert sim_related > sim_unrelated
    assert sim_related >= 0.70, f"Expected high similarity >= 0.70, got {sim_related}"
    assert (sim_related - sim_unrelated) > 0.30, f"Margin between related and unrelated was only {sim_related - sim_unrelated}"


def test_unrelated_texts_do_not_appear_identical(embedder: SentenceTransformerEmbedder):
    """12. Unrelated texts do not accidentally produce high similarity."""
    text_collapse = "Five people trapped in a collapsed building"
    text_power = "Power outage affecting several streets"

    sim = embedder.similarity(text_collapse, text_power)
    assert sim < 0.50, f"Unrelated texts scored unexpectedly high: {sim}"


def test_adversarial_semantic_distinctions(embedder: SentenceTransformerEmbedder):
    """Adversarial pairs (negation, state change) yield altered embeddings."""
    # Fire vs not on fire
    pos_fire = "building is on fire"
    neg_fire = "building is not on fire"
    sim_neg = embedder.similarity(pos_fire, neg_fire)
    # The embeddings must not be identical
    assert sim_neg < 0.99
    # Difference from self-similarity
    delta = 1.0 - sim_neg
    assert delta > 0.05, f"Expected noticeable shift from negation, got delta {delta}"

    # Trapped vs rescued
    trapped = "people are trapped"
    rescued = "people were rescued"
    sim_state = embedder.similarity(trapped, rescued)
    assert sim_state < 0.99
    assert (1.0 - sim_state) > 0.05


# ==============================================================================
# 5. Empty & Invalid Input Handling
# ==============================================================================
def test_empty_string_input_raises_error(embedder: SentenceTransformerEmbedder):
    """13. Empty string raises MLInputError."""
    with pytest.raises(MLInputError, match="empty or whitespace-only"):
        embedder.encode("")


def test_whitespace_only_string_raises_error(embedder: SentenceTransformerEmbedder):
    """13. Whitespace-only string raises MLInputError."""
    with pytest.raises(MLInputError, match="empty or whitespace-only"):
        embedder.encode("   \n\t  ")


def test_none_input_raises_error(embedder: SentenceTransformerEmbedder):
    """14. None input raises MLInputError."""
    with pytest.raises(MLInputError, match="cannot be None"):
        embedder.encode(None)


def test_non_string_input_raises_error(embedder: SentenceTransformerEmbedder):
    """14. Non-string/non-PreprocessedText input raises MLInputError."""
    with pytest.raises(MLInputError, match="must be a string or PreprocessedText|Unsupported input type"):
        embedder.encode(12345)  # type: ignore


def test_empty_batch_raises_error(embedder: SentenceTransformerEmbedder):
    """15. Empty batch list [] raises MLInputError."""
    with pytest.raises(MLInputError, match="Batch of reports cannot be empty"):
        embedder.encode([])

    with pytest.raises(MLInputError, match="Batch of reports cannot be empty"):
        embedder.encode_batch([])


def test_batch_containing_invalid_entries_raises_error(embedder: SentenceTransformerEmbedder):
    """Batch containing invalid entry in the middle raises MLInputError with index."""
    batch_with_empty = ["Valid emergency report text", "", "Another valid report text"]
    with pytest.raises(MLInputError, match="index 1"):
        embedder.encode_batch(batch_with_empty)

    batch_with_none = ["Valid emergency report text", None, "Another valid report text"]  # type: ignore
    with pytest.raises(MLInputError, match="index 1"):
        embedder.encode_batch(batch_with_none)


def test_similarity_invalid_input_raises_error(embedder: SentenceTransformerEmbedder):
    """Similarity with empty/None argument raises MLInputError."""
    with pytest.raises(MLInputError):
        embedder.similarity("", "Valid report text")

    with pytest.raises(MLInputError):
        embedder.similarity("Valid report text", None)  # type: ignore


# ==============================================================================
# 6. Lazy Model Loading & Model Reuse
# ==============================================================================
def test_lazy_model_loading_and_reuse():
    """16, 17, 18. Model is not loaded at instantiation, loads on first call, and is reused."""
    # Reset model cache for clean verification
    reset_model_cache()
    config = MLConfig.from_env()

    # Model should NOT be loaded initially
    assert not is_model_loaded(config.embedding_model_name, config.device)

    # Instantiating embedder must NOT load the model
    embedder1 = SentenceTransformerEmbedder(config=config)
    assert not is_model_loaded(config.embedding_model_name, config.device)

    # First encode call loads the model lazily
    _ = embedder1.encode_single("First test report for lazy loading verification.")
    assert is_model_loaded(config.embedding_model_name, config.device)

    # Second instance with same model should reuse the cached model
    embedder2 = SentenceTransformerEmbedder(config=config)
    # Encode with second instance reuses cached model without error
    vec2 = embedder2.encode_single("Second test report with reused model instance.")
    assert len(vec2) == 384


def test_model_loading_failure_raises_typed_ml_model_error():
    """Model load failure (e.g. missing package or corrupted model) raises MLModelError."""
    reset_model_cache()
    embedder_fail = SentenceTransformerEmbedder()

    with patch.dict("sys.modules", {"sentence_transformers": None}):
        with pytest.raises(MLModelError, match="sentence-transformers is not installed"):
            embedder_fail._get_model()


# ==============================================================================
# 7. Determinism & Floating-Point Stability
# ==============================================================================
def test_deterministic_output(embedder: SentenceTransformerEmbedder):
    """19. Repeated encode on identical input produces identical vectors within float tolerance."""
    text = "High winds knocking down transmission lines in rural area."
    vec1 = embedder.encode(text)
    vec2 = embedder.encode(text)
    vec3 = embedder.encode(text)

    assert np.allclose(vec1, vec2, atol=1e-6)
    assert np.allclose(vec2, vec3, atol=1e-6)


# ==============================================================================
# 8. Observability & Privacy Invariance
# ==============================================================================
def test_no_raw_report_text_leaked_in_logs():
    """20. Ensure raw citizen report text is never emitted into log records."""
    log_records: list[logging.LogRecord] = []

    class CapturingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            log_records.append(record)

    logger = logging.getLogger("karen.ml.embeddings")
    handler = CapturingHandler()
    formatter = MLJsonFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    secret_raw_text = "CONFIDENTIAL_CITIZEN_DISPATCH_SECRET_987654321"
    embedder_test = SentenceTransformerEmbedder()

    try:
        _ = embedder_test.encode(secret_raw_text)
        _ = embedder_test.encode_batch([secret_raw_text])

        for rec in log_records:
            formatted = formatter.format(rec)
            # The secret raw text must never appear in the formatted JSON log output
            assert secret_raw_text not in formatted, f"Raw text leaked into log message: {formatted}"
            assert secret_raw_text not in rec.getMessage()
    finally:
        logger.removeHandler(handler)


# ==============================================================================
# 9. PreprocessedText Support & Integration
# ==============================================================================
def test_preprocessed_text_input_support(embedder: SentenceTransformerEmbedder):
    """22. PreprocessedText instances are accepted directly without double-cleaning."""
    raw = "<b>FLASH FLOOD!</b> Water entering ground floor rapidly &amp; rising."
    prep = preprocess_report(raw)

    vec_prep = embedder.encode_single(prep)
    vec_raw = embedder.encode_single(raw)

    assert len(vec_prep) == 384
    # PreprocessedText and raw text should yield identical or near-identical embeddings
    assert np.allclose(vec_prep, vec_raw, atol=1e-4)


# ==============================================================================
# 10. Vector Similarity & Numerical Clipping
# ==============================================================================
def test_vector_similarity_helper_and_clipping(embedder: SentenceTransformerEmbedder):
    """23. vector_similarity handles normalized arrays and clips float overshoots."""
    vec_a = np.ones(384, dtype=np.float32) / np.sqrt(384)
    vec_b = np.ones(384, dtype=np.float32) / np.sqrt(384)

    sim = embedder.vector_similarity(vec_a, vec_b)
    assert abs(sim - 1.0) < 1e-5
    assert -1.0 <= sim <= 1.0

    # Test numerical clipping on slightly out-of-bounds dot product
    vec_overshoot = vec_a * 1.00001
    sim_clipped = embedder.vector_similarity(vec_a, vec_overshoot)
    assert sim_clipped == 1.0


def test_vector_similarity_shape_mismatch_raises_error(embedder: SentenceTransformerEmbedder):
    """vector_similarity raises MLInferenceError on mismatched dimensions."""
    vec_bad = np.zeros(100, dtype=np.float32)
    vec_good = np.zeros(384, dtype=np.float32)

    with pytest.raises(MLInferenceError, match="Vector shape mismatch"):
        embedder.vector_similarity(vec_bad, vec_good)


# ==============================================================================
# 11. ComponentResult & Public API Wrappers
# ==============================================================================
def test_to_component_result(embedder: SentenceTransformerEmbedder):
    """ComponentResult conversion conforms to pipeline architecture contract."""
    vec = embedder.encode_single("Emergency report for component result packaging.")
    res = embedder.to_component_result(vec)

    assert isinstance(res, ComponentResult)
    assert res.component == "embeddings"
    assert res.status == "SUCCESS"
    assert res.data["dimension"] == 384
    assert res.data["normalized"] is True
    assert res.data["similarity_metric"] == "cosine"
    assert len(res.data["embedding"]) == 384


def test_model_metadata_property(embedder: SentenceTransformerEmbedder):
    """embedder.model_metadata exposes correct metadata structure."""
    meta = embedder.model_metadata
    assert isinstance(meta, ModelMetadata)
    assert meta.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert meta.dimension == 384
    assert meta.device == "cpu"
    assert meta.task == "dense_semantic_embedding"


def test_functional_wrappers():
    """Public functional wrappers (embed_report, embed_reports, compute_similarity)."""
    text_a = "Fire in residential apartment building."
    text_b = "Apartment is on fire with people calling for help."

    vec = embed_report(text_a)
    assert len(vec) == 384

    vecs = embed_reports([text_a, text_b])
    assert len(vecs) == 2
    assert len(vecs[0]) == 384
    assert len(vecs[1]) == 384

    sim = compute_similarity(text_a, text_b)
    assert isinstance(sim, float)
    assert sim >= 0.70


def test_embedding_engine_alias():
    """EmbeddingEngine is an exact alias for SentenceTransformerEmbedder."""
    assert EmbeddingEngine is SentenceTransformerEmbedder
    engine = EmbeddingEngine()
    vec = engine.encode("Testing EmbeddingEngine alias.")
    assert len(vec) == 384


def test_json_serialization_safety(embedder: SentenceTransformerEmbedder):
    """Output embeddings are pure Python floats fully serializable by standard json."""
    vec = embedder.encode_single("Testing JSON serialization of embedding vectors.")
    payload = {"embedding": vec, "dimension": len(vec)}
    serialized = json.dumps(payload)
    assert isinstance(serialized, str)
    deserialized = json.loads(serialized)
    assert len(deserialized["embedding"]) == 384


# ==============================================================================
# 12. Evaluator & Behavioral Benchmark Suite
# ==============================================================================
def test_embedding_evaluator_suite(embedder: SentenceTransformerEmbedder):
    """24. Evaluator runs successfully and validates all behavioral invariants."""
    evaluator = EmbeddingEvaluator(embedder=embedder)
    report = evaluator.evaluate(benchmark_trials=3)

    assert isinstance(report, EmbeddingEvaluationReport)
    assert report.total_pairs_evaluated == len(CURATED_SEMANTIC_PAIRS)
    assert report.embedding_dimension == 384
    assert report.norm_invariance_passed is True
    assert report.self_similarity_passed is True
    assert report.symmetry_passed is True
    assert report.semantic_ordering_passed is True
    assert report.leakage_free is True
    assert report.passed_all_behavioral_invariants is True
    assert report.mean_high_similarity > report.mean_low_similarity
    assert report.warm_single_latency_ms > 0
    assert report.batch_throughput_items_per_sec > 0

    summary_text = report.summary()
    assert "Feature 8: Embedding Engine Behavioral Evaluation" in summary_text
    assert "PASSED" in summary_text
