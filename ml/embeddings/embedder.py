"""
Karen's Ear — Dense Semantic Embedding Engine.

Step 3 of the ML pipeline (architecture/ml-pipeline.md Section 3.7).
Generates unit L2-normalized 384-dimensional dense semantic vectors using
sentence-transformers/all-MiniLM-L6-v2 to power backend incident correlation,
deduplication, and corroboration triangulation.

Architectural Principles & Boundaries:
1. Pure Semantic Representation: Converts emergency report text into a normalized
   384-dimensional vector and calculates cosine similarity (dot product of unit vectors).
2. Boundary Discipline (ML vs. Backend):
   - Aryan / ML: Text -> Vector -> Semantic similarity signal in [-1.0, 1.0].
   - Daksh / Backend: Similarity signal + Spatial proximity + Temporal proximity +
     Incident metadata -> Incident clustering / fusion / deduplication decision.
   - The embedding engine NEVER creates incident IDs, decides whether two reports are
     duplicates, merges reports, or applies backend priority/urgency.
3. Lazy Loading & Resource Sharing: Zero model loading at module import time.
   Loaded lazily on first inference and safely reused across instances and calls.
4. Normalization Invariant: Every emitted embedding strictly satisfies ||v||₂ ≈ 1.0.
5. Determinism: Identical text and configuration always produces identical vector embeddings.
6. Privacy & Observability: Adheres to get_ml_logger; never leaks raw emergency report content.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Sequence

import numpy as np

from ml.config import (
    ComponentResult,
    MLConfig,
    ModelMetadata,
    get_ml_config,
)
from ml.exceptions import (
    MLInferenceError,
    MLInputError,
    MLModelError,
)
from ml.logging_utils import get_ml_logger
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner

# ==============================================================================
# Model Cache & Thread Safety
# ==============================================================================
# Process-level registry caching loaded transformer models by (model_name, device)
_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_MODEL_LOCK = threading.Lock()


def reset_model_cache() -> None:
    """
    Clears cached transformer models from memory.
    Primarily utilized in test suites to verify lazy-loading and reload behavior.
    """
    with _MODEL_LOCK:
        _MODEL_CACHE.clear()


def is_model_loaded(model_name: str, device: str = "cpu") -> bool:
    """Returns True if the specified model is currently loaded in the cache."""
    with _MODEL_LOCK:
        return (model_name, device.lower()) in _MODEL_CACHE


# ==============================================================================
# Sentence Transformer Embedder
# ==============================================================================
class SentenceTransformerEmbedder:
    """
    Production-grade semantic embedding engine for Karen's Ear emergency reports.

    Uses sentence-transformers/all-MiniLM-L6-v2 to produce 384-dimensional,
    unit L2-normalized vector representations.

    Public API:
        embedding = embedder.encode(text)                    # List[float], len=384
        embeddings = embedder.encode(list_of_reports)        # List[List[float]], shape=(N, 384)
        similarity = embedder.similarity(text_a, text_b)     # float in [-1.0, 1.0]
    """

    def __init__(
        self,
        config: MLConfig | None = None,
        clean_text: bool = True,
        batch_size: int = 32,
    ) -> None:
        self.config = config or get_ml_config()
        self.clean_text = bool(clean_text)
        self.default_batch_size = int(batch_size)

        self.logger = get_ml_logger(
            name="karen.ml.embeddings",
            component="embeddings",
            model_version=self.config.model_version,
        )

        # Preprocessor reuse (canonical Feature 2 text preparation)
        self._cleaner = TextCleaner(config=self.config)

    @property
    def model_metadata(self) -> ModelMetadata:
        """Lightweight metadata descriptor for the active embedding model."""
        return ModelMetadata(
            model_name=self.config.embedding_model_name,
            version="all-MiniLM-L6-v2",
            task="dense_semantic_embedding",
            device=self.config.device,
            dimension=self.config.embedding_dimension,
        )

    def _get_model(self) -> Any:
        """
        Lazily loads the SentenceTransformer model on first invocation.
        Guarantees zero heavyweight ML loading during package or module import.
        Thread-safe via _MODEL_LOCK and cached for subsequent calls.
        """
        cache_key = (self.config.embedding_model_name, self.config.device.lower())

        if self.config.lightweight_mode:
            raise MLModelError(
                "Dense embedding neural runtime is disabled in lightweight mode (ML_LIGHTWEIGHT_MODE=true)",
                details={"library": "sentence-transformers", "lightweight_mode": True},
            )

        # Fast read outside lock
        if cache_key in _MODEL_CACHE:
            return _MODEL_CACHE[cache_key]

        with _MODEL_LOCK:
            # Double-check inside lock
            if cache_key in _MODEL_CACHE:
                return _MODEL_CACHE[cache_key]

            self.logger.info(
                "Initializing lazy SentenceTransformer model...",
                extra={
                    "model_name": self.config.embedding_model_name,
                    "device": self.config.device,
                },
            )

            load_start = time.time()
            try:
                from sentence_transformers import SentenceTransformer  # Lazy import
            except ImportError as exc:
                self.logger.error("Required ML library sentence-transformers is missing", exc_info=True)
                raise MLModelError(
                    f"sentence-transformers is not installed or unavailable: {exc}",
                    details={"error_type": "ImportError", "model_name": self.config.embedding_model_name},
                ) from exc

            try:
                model = SentenceTransformer(
                    self.config.embedding_model_name,
                    device=self.config.device,
                )
            except Exception as exc:
                self.logger.error(
                    "Failed to instantiate SentenceTransformer model",
                    extra={"model_name": self.config.embedding_model_name, "error_type": type(exc).__name__},
                    exc_info=True,
                )
                raise MLModelError(
                    f"Failed to load embedding model '{self.config.embedding_model_name}': {exc}",
                    details={"model_name": self.config.embedding_model_name, "error_type": type(exc).__name__},
                ) from exc

            load_ms = round((time.time() - load_start) * 1000, 2)
            _MODEL_CACHE[cache_key] = model

            self.logger.info(
                "SentenceTransformer model loaded successfully",
                extra={
                    "model_name": self.config.embedding_model_name,
                    "device": self.config.device,
                    "load_latency_ms": load_ms,
                    "target_dimension": self.config.embedding_dimension,
                },
            )
            return model

    # ==========================================================================
    # Text Preparation Helpers
    # ==========================================================================
    def _validate_and_prepare_single(
        self,
        text: str | PreprocessedText,
        report_id: str | None = None,
    ) -> str:
        """
        Validates a single input report text and returns the prepared string.
        Adheres to project input constraints and ensures meaningful emergency signals are preserved.
        """
        if text is None:
            raise MLInputError(
                "Input report text cannot be None",
                details={"report_id": report_id, "error_code": "NULL_INPUT"},
            )

        if not isinstance(text, (str, PreprocessedText)):
            raise MLInputError(
                f"Input report text must be a string or PreprocessedText, got {type(text).__name__}",
                details={"report_id": report_id, "type": type(text).__name__},
            )

        if isinstance(text, PreprocessedText):
            return text.normalized_text

        # Raw string validation
        if not text or not text.strip():
            raise MLInputError(
                "Report text cannot be empty or whitespace-only",
                details={"report_id": report_id, "length": len(text)},
            )

        if self.clean_text:
            cleaned_obj = self._cleaner.clean(text, report_id=report_id)
            return cleaned_obj.normalized_text

        return text

    def _validate_and_prepare_batch(
        self,
        texts: Sequence[str | PreprocessedText],
        report_ids: Sequence[str | None] | None = None,
    ) -> list[str]:
        """
        Validates a sequence of input report texts and returns prepared strings.
        Ensures strict rejection of invalid or empty entries.
        """
        if texts is None:
            raise MLInputError(
                "Batch of reports cannot be None",
                details={"error_code": "NULL_BATCH"},
            )

        if isinstance(texts, (str, bytes, PreprocessedText)):
            raise MLInputError(
                f"Batch input must be a list or sequence of texts, not a single {type(texts).__name__}",
                details={"type": type(texts).__name__},
            )

        if not isinstance(texts, (list, tuple)):
            try:
                texts = list(texts)
            except Exception as exc:
                raise MLInputError(
                    f"Batch input could not be converted to a sequence: {exc}",
                    details={"type": type(texts).__name__},
                ) from exc

        if len(texts) == 0:
            raise MLInputError(
                "Batch of reports cannot be empty. At least one report text is required for embedding.",
                details={"batch_size": 0},
            )

        ids = list(report_ids) if report_ids is not None else [None] * len(texts)
        if len(ids) != len(texts):
            raise MLInputError(
                f"Length of report_ids ({len(ids)}) must match length of texts ({len(texts)})",
                details={"texts_len": len(texts), "ids_len": len(ids)},
            )

        prepared_texts: list[str] = []
        for idx, (item, rep_id) in enumerate(zip(texts, ids)):
            if item is None:
                raise MLInputError(
                    f"Report text at index {idx} cannot be None",
                    details={"index": idx, "report_id": rep_id},
                )
            if not isinstance(item, (str, PreprocessedText)):
                raise MLInputError(
                    f"Report text at index {idx} must be a string or PreprocessedText, got {type(item).__name__}",
                    details={"index": idx, "type": type(item).__name__, "report_id": rep_id},
                )
            if isinstance(item, str) and not item.strip():
                raise MLInputError(
                    f"Report text at index {idx} cannot be empty or whitespace-only",
                    details={"index": idx, "length": len(item), "report_id": rep_id},
                )

            prepared = self._validate_and_prepare_single(item, report_id=rep_id)
            prepared_texts.append(prepared)

        return prepared_texts

    # ==========================================================================
    # Verification & Numerical Invariants
    # ==========================================================================
    def _verify_and_normalize(self, arr: np.ndarray) -> np.ndarray:
        """
        Verifies dimensionality and unit L2 normalization of embedding vectors.
        Ensures ||v||₂ ≈ 1.0 within numerical tolerance and enforces expected dimension.
        """
        expected_dim = self.config.embedding_dimension
        actual_dim = arr.shape[-1]
        if actual_dim != expected_dim:
            raise MLInferenceError(
                f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim}",
                details={"expected_dimension": expected_dim, "actual_dimension": actual_dim},
            )

        if arr.ndim == 1:
            norm = float(np.linalg.norm(arr))
            if abs(norm - 1.0) > 1e-3:
                # If slightly off due to float32 representation, re-normalize
                arr = arr / (norm + 1e-12)
                norm = float(np.linalg.norm(arr))
                if abs(norm - 1.0) > 1e-3:
                    raise MLInferenceError(
                        f"L2 normalization invariant violated: vector norm is {norm:.6f} (expected ~1.0)",
                        details={"norm": norm},
                    )
        elif arr.ndim == 2:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            deviations = np.abs(norms - 1.0)
            if np.any(deviations > 1e-3):
                arr = arr / (norms + 1e-12)
                norms = np.linalg.norm(arr, axis=1, keepdims=True)
                if np.any(np.abs(norms - 1.0) > 1e-3):
                    raise MLInferenceError(
                        "L2 normalization invariant violated in batch embeddings",
                        details={"max_deviation": float(np.max(np.abs(norms - 1.0)))},
                    )

        return arr

    # ==========================================================================
    # Public Encoding API
    # ==========================================================================
    def encode_single(
        self,
        text: str | PreprocessedText,
        report_id: str | None = None,
    ) -> list[float]:
        """
        Encodes a single emergency report into a unit L2-normalized 384-dimensional vector.

        Args:
            text: Emergency report text string or PreprocessedText object.
            report_id: Optional tracking identifier for logging and tracing.

        Returns:
            List of 384 Python floats representing the normalized embedding vector.

        Raises:
            MLInputError: On empty, None, or invalid text input.
            MLModelError: If model initialization or weights cannot be loaded.
            MLInferenceError: If dimensionality or normalization invariant fails.
        """
        clean_text_str = self._validate_and_prepare_single(text, report_id=report_id)
        model = self._get_model()

        t0 = time.time()
        try:
            raw_embs = model.encode(
                [clean_text_str],
                device=self.config.device,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            self.logger.error(
                "Model inference failed during single text embedding",
                extra={"report_id": report_id, "error_type": type(exc).__name__},
                exc_info=True,
            )
            raise MLInferenceError(
                f"Embedding inference failed: {exc}",
                details={"report_id": report_id, "error_type": type(exc).__name__},
            ) from exc

        elapsed_ms = round((time.time() - t0) * 1000, 2)
        vec = self._verify_and_normalize(raw_embs[0])

        self.logger.info(
            "Text embedding generated successfully",
            extra={
                "batch_size": 1,
                "embedding_dimension": len(vec),
                "latency_ms": elapsed_ms,
                "processing_status": "SUCCESS",
                "report_id": report_id,
            },
        )

        return [float(x) for x in vec]

    def encode_batch(
        self,
        texts: Sequence[str | PreprocessedText],
        batch_size: int | None = None,
        report_ids: Sequence[str | None] | None = None,
    ) -> list[list[float]]:
        """
        Encodes a batch of emergency reports into unit L2-normalized 384-dimensional vectors.
        Preserves input ordering exactly.

        Args:
            texts: Sequence of report texts or PreprocessedText instances.
            batch_size: Optional chunk size for SentenceTransformers batch processing.
            report_ids: Optional list of identifiers matching texts.

        Returns:
            List of N lists, each containing 384 Python floats.

        Raises:
            MLInputError: On empty batch, mismatched IDs, or invalid text entries.
            MLModelError: If model loading fails.
            MLInferenceError: If dimensionality or normalization invariant fails.
        """
        prepared_texts = self._validate_and_prepare_batch(texts, report_ids=report_ids)
        effective_batch_size = int(batch_size) if batch_size is not None else self.default_batch_size
        model = self._get_model()

        t0 = time.time()
        try:
            raw_embs = model.encode(
                prepared_texts,
                batch_size=effective_batch_size,
                device=self.config.device,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            self.logger.error(
                "Model inference failed during batch text embedding",
                extra={"batch_size": len(prepared_texts), "error_type": type(exc).__name__},
                exc_info=True,
            )
            raise MLInferenceError(
                f"Batch embedding inference failed: {exc}",
                details={"batch_size": len(prepared_texts), "error_type": type(exc).__name__},
            ) from exc

        elapsed_ms = round((time.time() - t0) * 1000, 2)
        arr = self._verify_and_normalize(raw_embs)

        self.logger.info(
            "Batch text embeddings generated successfully",
            extra={
                "batch_size": len(prepared_texts),
                "embedding_dimension": arr.shape[1],
                "latency_ms": elapsed_ms,
                "processing_status": "SUCCESS",
            },
        )

        return [[float(x) for x in row] for row in arr]

    def encode(
        self,
        text: str | PreprocessedText | Sequence[str | PreprocessedText],
        batch_size: int | None = None,
        report_id: str | None = None,
    ) -> list[float] | list[list[float]]:
        """
        Unified public entry point for encoding text.
        Accepts either a single report text or a sequence of reports.

        If input is a single text string / PreprocessedText:
            returns List[float] of length 384.
        If input is a sequence of texts:
            returns List[List[float]] of shape (N, 384).
        """
        if isinstance(text, (str, PreprocessedText)):
            return self.encode_single(text, report_id=report_id)
        if isinstance(text, (list, tuple)):
            return self.encode_batch(text, batch_size=batch_size)
        if text is None:
            raise MLInputError("Input text cannot be None", details={"error_code": "NULL_INPUT"})
        raise MLInputError(
            f"Unsupported input type for encode: {type(text).__name__}. Expected str, PreprocessedText, or sequence.",
            details={"type": type(text).__name__},
        )

    def encode_numpy(
        self,
        text: str | PreprocessedText | Sequence[str | PreprocessedText],
        batch_size: int | None = None,
    ) -> np.ndarray:
        """
        Encodes report(s) directly to a NumPy float32 array for high-performance operations.
        Returns shape (384,) for single text or (N, 384) for sequence.
        """
        if isinstance(text, (str, PreprocessedText)):
            prepared = self._validate_and_prepare_single(text)
            model = self._get_model()
            raw = model.encode([prepared], device=self.config.device, normalize_embeddings=True, convert_to_numpy=True)
            return self._verify_and_normalize(raw[0]).astype(np.float32)

        if isinstance(text, (list, tuple)):
            prepared_batch = self._validate_and_prepare_batch(text)
            model = self._get_model()
            effective_bs = batch_size or self.default_batch_size
            raw = model.encode(prepared_batch, batch_size=effective_bs, device=self.config.device, normalize_embeddings=True, convert_to_numpy=True)
            return self._verify_and_normalize(raw).astype(np.float32)

        raise MLInputError(f"Unsupported input type: {type(text).__name__}")

    # ==========================================================================
    # Semantic Similarity API
    # ==========================================================================
    def similarity(
        self,
        text_a: str | PreprocessedText,
        text_b: str | PreprocessedText,
    ) -> float:
        """
        Computes cosine semantic similarity between two emergency reports.

        Because embeddings are unit L2-normalized:
            CosineSimilarity(u, v) = u · v

        Expected Mathematical Invariants:
        - Self-similarity: similarity(a, a) ≈ 1.0
        - Symmetry: similarity(a, b) == similarity(b, a)
        - Bounded range: scalar float in [-1.0, 1.0]

        IMPORTANT ARCHITECTURAL RULE:
        Does NOT decide whether reports are duplicates, assign priority, or create incidents.
        Returns the raw semantic similarity signal only.

        Args:
            text_a: First report text.
            text_b: Second report text.

        Returns:
            Scalar float in [-1.0, 1.0].
        """
        vec_a = self.encode_numpy(text_a)
        vec_b = self.encode_numpy(text_b)
        return self.vector_similarity(vec_a, vec_b)

    def vector_similarity(
        self,
        vec_a: Sequence[float] | np.ndarray,
        vec_b: Sequence[float] | np.ndarray,
    ) -> float:
        """
        Low-level cosine similarity helper for two normalized vectors.
        Computes dot product and safely clips numerical artifacts to [-1.0, 1.0].
        """
        a = np.asarray(vec_a, dtype=np.float32)
        b = np.asarray(vec_b, dtype=np.float32)

        if a.shape != b.shape or a.shape[-1] != self.config.embedding_dimension:
            raise MLInferenceError(
                f"Vector shape mismatch: {a.shape} vs {b.shape} (expected dimension {self.config.embedding_dimension})",
                details={"shape_a": list(a.shape), "shape_b": list(b.shape)},
            )

        dot = float(np.dot(a, b))
        # Strictly clip numerical floating-point artifacts outside [-1.0, 1.0]
        clipped = float(np.clip(dot, -1.0, 1.0))
        return clipped

    # ==========================================================================
    # Canonical Pipeline Component Result Packaging
    # ==========================================================================
    def to_component_result(
        self,
        embedding: Sequence[float],
        report_id: str | None = None,
        warnings: list[str] | None = None,
    ) -> ComponentResult:
        """Packages embedding into standard internal ComponentResult."""
        emb_list = [float(x) for x in embedding]
        return ComponentResult(
            component="embeddings",
            status="SUCCESS",
            data={
                "embedding": emb_list,
                "dimension": len(emb_list),
                "normalized": True,
                "similarity_metric": "cosine",
                "model_name": self.config.embedding_model_name,
            },
            warnings=list(warnings or []),
        )


# ==============================================================================
# Architectural Alias
# ==============================================================================
EmbeddingEngine = SentenceTransformerEmbedder


# ==============================================================================
# Public Functional Interfaces
# ==============================================================================
def embed_report(
    text: str | PreprocessedText,
    config: MLConfig | None = None,
    report_id: str | None = None,
) -> list[float]:
    """
    Public functional interface to embed a single emergency report.
    Convenience wrapper around SentenceTransformerEmbedder.encode_single().
    """
    embedder = SentenceTransformerEmbedder(config=config)
    return embedder.encode_single(text=text, report_id=report_id)


def embed_reports(
    texts: Sequence[str | PreprocessedText],
    config: MLConfig | None = None,
    batch_size: int = 32,
    report_ids: Sequence[str | None] | None = None,
) -> list[list[float]]:
    """
    Public functional interface to embed a batch of emergency reports.
    Convenience wrapper around SentenceTransformerEmbedder.encode_batch().
    """
    embedder = SentenceTransformerEmbedder(config=config, batch_size=batch_size)
    return embedder.encode_batch(texts=texts, batch_size=batch_size, report_ids=report_ids)


def compute_similarity(
    text_a: str | PreprocessedText,
    text_b: str | PreprocessedText,
    config: MLConfig | None = None,
) -> float:
    """
    Public functional interface to compute semantic similarity between two reports.
    Convenience wrapper around SentenceTransformerEmbedder.similarity().
    """
    embedder = SentenceTransformerEmbedder(config=config)
    return embedder.similarity(text_a=text_a, text_b=text_b)
